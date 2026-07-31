from __future__ import annotations

import hmac
import json
import logging
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from banhelper.domain.models import BanEvent
from banhelper.domain.validation import PROTOCOL_VERSION, ValidationError

MAX_BODY_BYTES = 64 * 1024
ActionHandler = Callable[[str, object | None], bool]


class ListenerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"
    allow_reuse_port = False
    request_queue_size = 128

    def server_bind(self) -> None:
        # On Windows SO_REUSEADDR permits another process to bind the same
        # address, which can silently split requests between listeners.
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class FabricListener:
    """Loopback HTTP ingress for Fabric events and trusted OpenDeck actions."""

    def __init__(
        self,
        host: str,
        port: int,
        token: str,
        submit: Callable[[BanEvent], bool],
        on_log: Callable[[str, str], None] | None = None,
        fallback_mode: str = "FT",
        on_action: ActionHandler | None = None,
    ):
        normalized_host = str(host or "127.0.0.1").strip()
        if normalized_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Fabric listener may bind only to loopback")
        self.host = normalized_host
        self.port = int(port)
        self.token = str(token)
        self.submit = submit
        self.on_log = on_log
        self.on_action = on_action
        self.fallback_mode = "RW" if str(fallback_mode).upper() == "RW" else "FT"
        self._server: ListenerServer | None = None
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger("banhelper.fabric")
        self.last_event_at = 0.0
        self.received = 0
        self.rejected = 0
        self.actions_received = 0

    def report(self, level: str, message: str) -> None:
        getattr(self._logger, level.lower(), self._logger.info)(message)
        if self.on_log:
            self.on_log(level, message)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "BanHelper/2.2"

            def cors(self) -> None:
                # OpenDeck hosts web plugins on another localhost port, so the
                # browser requires an explicit CORS response and preflight.
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-BanHelper-Token")
                self.send_header("Access-Control-Max-Age", "600")

            def reply(self, status: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.cors()
                self.end_headers()
                self.wfile.write(body)

            def read_payload(self) -> dict | None:
                raw_length = self.headers.get("Content-Length")
                if raw_length is None:
                    self.reply(411, {"ok": False, "error": "content_length_required"})
                    return None
                try:
                    length = int(raw_length)
                except ValueError:
                    self.reply(400, {"ok": False, "error": "invalid_content_length"})
                    return None
                if length <= 0:
                    self.reply(400, {"ok": False, "error": "empty_body"})
                    return None
                if length > MAX_BODY_BYTES:
                    owner.rejected += 1
                    owner.report("WARNING", "HTTP запрос отклонён: тело слишком большое")
                    self.reply(413, {"ok": False, "error": "body_too_large"})
                    return None
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    owner.rejected += 1
                    owner.report("WARNING", "HTTP запрос отклонён: некорректный JSON")
                    self.reply(400, {"ok": False, "error": "invalid_json"})
                    return None
                if not isinstance(payload, dict):
                    self.reply(400, {"ok": False, "error": "json_object_required"})
                    return None
                return payload

            def authorized(self, payload: dict | None = None) -> bool:
                supplied = self.headers.get(
                    "X-BanHelper-Token",
                    str((payload or {}).get("token", "")),
                )
                if owner.token and not hmac.compare_digest(str(supplied), owner.token):
                    owner.rejected += 1
                    owner.report("WARNING", "HTTP запрос отклонён: неверный токен")
                    self.reply(401, {"ok": False, "error": "invalid_token"})
                    return False
                return True

            def do_OPTIONS(self):  # noqa: N802
                if self.path not in {"/ban", "/opendeck/action", "/opendeck/status"}:
                    self.reply(404, {"ok": False, "error": "not_found"})
                    return
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.cors()
                self.end_headers()

            def do_GET(self):  # noqa: N802
                if self.path == "/status":
                    self.reply(
                        200,
                        {
                            "ok": True,
                            "service": "BanHelper",
                            "protocol_version": PROTOCOL_VERSION,
                            "queue_capacity": True,
                        },
                    )
                    return
                if self.path == "/opendeck/status":
                    if not self.authorized():
                        return
                    self.reply(
                        200,
                        {
                            "ok": True,
                            "service": "BanHelper",
                            "integration": "OpenDeck",
                            "api_version": 1,
                            "actions": ["mode", "reason", "confirm", "copy", "skip"],
                        },
                    )
                    return
                self.reply(404, {"ok": False, "error": "not_found"})

            def do_POST(self):  # noqa: N802
                started = time.time()
                if self.path not in {"/ban", "/opendeck/action"}:
                    self.reply(404, {"ok": False, "error": "not_found"})
                    return
                payload = self.read_payload()
                if payload is None or not self.authorized(payload):
                    return

                if self.path == "/opendeck/action":
                    action = str(payload.get("action", "")).strip().lower()
                    if not action:
                        self.reply(422, {"ok": False, "error": "action_required"})
                        return
                    if owner.on_action is None:
                        self.reply(503, {"ok": False, "error": "opendeck_unavailable", "retryable": True})
                        return
                    try:
                        accepted = owner.on_action(action, payload.get("value"))
                    except (TypeError, ValueError) as exc:
                        owner.rejected += 1
                        self.reply(422, {"ok": False, "error": str(exc) or "invalid_action"})
                        return
                    if not accepted:
                        owner.rejected += 1
                        self.reply(503, {"ok": False, "error": "queue_full", "retryable": True})
                        return
                    owner.actions_received += 1
                    owner.report("INFO", f"OpenDeck: принято действие {action}")
                    self.reply(202, {"ok": True, "accepted": True, "action": action})
                    return

                try:
                    supplied_mode = str(payload.get("server_mode", "")).upper()
                    if supplied_mode not in {"FT", "RW"}:
                        payload = dict(payload)
                        payload["server_mode"] = owner.fallback_mode
                        owner.report("WARNING", f"Fabric не передал режим; использован fallback {owner.fallback_mode}")
                    event = BanEvent.from_payload(payload, received_at=started)
                    if not owner.submit(event):
                        owner.rejected += 1
                        self.reply(503, {"ok": False, "error": "queue_full", "retryable": True})
                        return
                    owner.received += 1
                    owner.last_event_at = started
                    self.reply(202, {"ok": True, "accepted": True, "event_id": event.event_id})
                except ValidationError as exc:
                    owner.rejected += 1
                    owner.report("WARNING", f"Fabric запрос не прошёл валидацию: {exc.field}")
                    status = 409 if exc.field == "protocol_version" else 422
                    self.reply(status, {"ok": False, "error": str(exc), "field": exc.field})
                except (TypeError, ValueError):
                    owner.rejected += 1
                    self.reply(400, {"ok": False, "error": "invalid_request"})

            def log_message(self, *_args):
                return

        self._server = ListenerServer((self.host, self.port), Handler)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.1},
            name="FabricHTTP",
            daemon=False,
        )
        self._thread.start()
        self.report("INFO", f"Fabric/OpenDeck listener запущен на {self.host}:{self.port}")

    def request_stop(self) -> None:
        server = self._server
        if server:
            threading.Thread(target=server.shutdown, name="FabricHTTPStop", daemon=True).start()

    def wait(self, timeout: float = 3.0) -> bool:
        thread = self._thread
        if thread:
            thread.join(timeout)
        if self._server:
            self._server.server_close()
        stopped = not thread or not thread.is_alive()
        if stopped:
            self.report("INFO", "Fabric/OpenDeck listener остановлен")
            self._server = None
            self._thread = None
        return stopped
