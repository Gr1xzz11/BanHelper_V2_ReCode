from __future__ import annotations

import http.client
import json
import statistics
import tempfile
import time

from banhelper.app.paths import AppPaths
from banhelper.infrastructure.fabric_listener import FabricListener
from banhelper.services.ban_service import BanService


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def send(port: int, token: str, index: int) -> int:
    body = json.dumps({
        "protocol_version": 2, "event_id": f"pipeline-{index:06d}",
        "event_type": "ban", "player": f"Load_{index}", "moderator": "Benchmark",
        "reason": "5.5", "server_mode": "RW" if index % 2 else "FT",
    }).encode()
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    connection.request("POST", "/ban", body, {"Content-Type": "application/json", "X-BanHelper-Token": token})
    response = connection.getresponse(); response.read(); status = response.status; connection.close()
    return status


def wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(0.005)
    raise TimeoutError("pipeline did not drain")


def run(count: int = 100) -> dict:
    token = "benchmark-token"
    with tempfile.TemporaryDirectory(prefix="banhelper-pipeline-") as root:
        service = BanService(AppPaths.temporary(root), queue_size=max(2048, count * 3))
        listener = FabricListener("127.0.0.1", 0, token, service.submit_event)
        service.start(); listener.start()
        started = time.perf_counter()
        statuses = [send(listener.port, token, index) for index in range(count)]
        http_ms = (time.perf_counter() - started) * 1000
        wait_until(lambda: service.accepted == count)
        first_latencies = list(service.latencies_ms[:count])
        duplicate_started = time.perf_counter()
        duplicate_statuses = [send(listener.port, token, index) for index in range(count)]
        wait_until(lambda: service.duplicates == count)
        duplicate_ms = (time.perf_counter() - duplicate_started) * 1000
        listener.request_stop(); service.request_stop()
        listener_ok, service_ok = listener.wait(3), service.wait(5)
    return {
        "events": count,
        "minimum_ms": round(min(first_latencies), 3),
        "median_ms": round(statistics.median(first_latencies), 3),
        "p95_ms": round(percentile(first_latencies, 0.95), 3),
        "maximum_ms": round(max(first_latencies), 3),
        "lost": count - service.accepted,
        "duplicates_created": service.accepted - count,
        "duplicates_rejected": service.duplicates,
        "http_accepted": sum(status == 202 for status in statuses),
        "duplicate_http_accepted": sum(status == 202 for status in duplicate_statuses),
        "first_delivery_wall_ms": round(http_ms, 3),
        "duplicate_delivery_wall_ms": round(duplicate_ms, 3),
        "clean_shutdown": listener_ok and service_ok,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
