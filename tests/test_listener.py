from __future__ import annotations

import http.client
import json

import pytest

from banhelper.infrastructure.fabric_listener import MAX_BODY_BYTES, FabricListener


TOKEN = "test-secret"


def request(port: int, method: str, path: str, payload=None, token=TOKEN, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    body = json.dumps(payload).encode() if payload is not None else None
    actual_headers = dict(headers or {})
    if token is not None:
        actual_headers["X-BanHelper-Token"] = token
    if body is not None:
        actual_headers["Content-Type"] = "application/json"
    connection.request(method, path, body=body, headers=actual_headers)
    response = connection.getresponse()
    data = json.loads(response.read().decode())
    connection.close()
    return response.status, data


def payload(index=1, **changes):
    value = {
        "protocol_version": 2,
        "event_id": f"listener-event-{index:04d}",
        "event_type": "ban",
        "player": f"Player_{index}",
        "moderator": "Admin",
        "reason": "5.5",
        "server_mode": "FT",
    }
    value.update(changes)
    return value


@pytest.fixture
def listener():
    events = []
    instance = FabricListener("127.0.0.1", 0, TOKEN, lambda event: events.append(event) or True)
    instance.start()
    yield instance, events
    instance.request_stop()
    assert instance.wait(3)


def test_status(listener):
    instance, _events = listener
    status, data = request(instance.port, "GET", "/status", token=None)
    assert status == 200 and data["protocol_version"] == 2


def test_valid_ban_and_verification_left(listener):
    instance, events = listener
    status, data = request(instance.port, "POST", "/ban", payload())
    assert status == 202 and data["accepted"]
    status, _ = request(instance.port, "POST", "/ban", payload(2, event_type="verification_left", reason="1.21.4"))
    assert status == 202 and [event.reason for event in events] == ["5.5", "LIV"]
    status, _ = request(instance.port, "POST", "/ban", payload(3, reason=""))
    assert status == 202 and events[-1].reason == ""


def test_auth_json_size_and_protocol_errors(listener):
    instance, _events = listener
    assert request(instance.port, "POST", "/ban", payload(), token="wrong")[0] == 401
    connection = http.client.HTTPConnection("127.0.0.1", instance.port, timeout=3)
    connection.request("POST", "/ban", body=b"{broken", headers={"X-BanHelper-Token": TOKEN})
    assert connection.getresponse().status == 400
    connection.close()
    assert request(instance.port, "POST", "/ban", payload(protocol_version=1))[0] == 409
    connection = http.client.HTTPConnection("127.0.0.1", instance.port, timeout=3)
    connection.request("POST", "/ban", headers={"X-BanHelper-Token": TOKEN, "Content-Length": str(MAX_BODY_BYTES + 1)})
    assert connection.getresponse().status == 413
    connection.close()


def test_opendeck_status_actions_auth_and_cors():
    actions: list[tuple[str, object | None]] = []

    def on_action(action: str, value: object | None) -> bool:
        if action == "unknown":
            raise ValueError("unknown action")
        actions.append((action, value))
        return True

    instance = FabricListener(
        "127.0.0.1",
        0,
        TOKEN,
        lambda _event: True,
        on_action=on_action,
    )
    instance.start()
    try:
        status, data = request(instance.port, "GET", "/opendeck/status")
        assert status == 200 and data["integration"] == "OpenDeck"
        assert set(data["actions"]) == {"mode", "reason", "confirm", "copy", "skip"}
        assert request(instance.port, "GET", "/opendeck/status", token="wrong")[0] == 401

        status, data = request(
            instance.port,
            "POST",
            "/opendeck/action",
            {"action": "reason", "value": "5.5"},
        )
        assert status == 202 and data["accepted"]
        assert actions == [("reason", "5.5")]
        assert instance.actions_received == 1
        assert request(
            instance.port,
            "POST",
            "/opendeck/action",
            {"action": "mode", "value": "RW"},
            token="wrong",
        )[0] == 401
        assert request(
            instance.port,
            "POST",
            "/opendeck/action",
            {"action": "unknown"},
        )[0] == 422

        connection = http.client.HTTPConnection("127.0.0.1", instance.port, timeout=3)
        connection.request(
            "OPTIONS",
            "/opendeck/action",
            headers={
                "Origin": "http://localhost:57118",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-banhelper-token",
            },
        )
        response = connection.getresponse()
        response.read()
        assert response.status == 204
        assert response.getheader("Access-Control-Allow-Origin") == "*"
        assert "X-BanHelper-Token" in response.getheader("Access-Control-Allow-Headers")
        connection.close()
    finally:
        instance.request_stop()
        assert instance.wait(3)


def test_opendeck_action_is_unavailable_without_handler(listener):
    instance, _events = listener
    status, data = request(instance.port, "POST", "/opendeck/action", {"action": "confirm"})
    assert status == 503 and data["error"] == "opendeck_unavailable"


def test_unknown_mode_uses_listener_fallback():
    events = []
    instance = FabricListener("127.0.0.1", 0, TOKEN, lambda event: events.append(event) or True, fallback_mode="RW")
    instance.start()
    try:
        status, _ = request(instance.port, "POST", "/ban", payload(server_mode="unknown"))
        assert status == 202 and events[0].server_mode == "RW"
    finally:
        instance.request_stop()
        assert instance.wait(3)


def test_100_sequential_events_are_accepted(listener):
    instance, events = listener
    for index in range(100):
        status, _data = request(instance.port, "POST", "/ban", payload(index))
        assert status == 202
    assert len(events) == 100


def test_occupied_port_is_reported(listener):
    instance, _events = listener
    other = FabricListener("127.0.0.1", instance.port, TOKEN, lambda _event: True)
    try:
        with pytest.raises(OSError):
            other.start()
    finally:
        other.request_stop()
        assert other.wait(3)
