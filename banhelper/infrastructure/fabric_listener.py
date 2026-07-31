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


class ListenerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"
    allow_reuse_port = False
    request_queue_size = 128

    def server_bind(self) -> None:
        # On Windows SO_REUSEADDR permits another process to bind the same
        # address, which can silently split Fabric requests between listeners.
        # Require exclusive ownership there; keep fast restart semantics on
        # POSIX where SO_REUSEADDR does not allow a second live listener.
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class FabricListener:
    """Local HTTP ingress. It never waits for SQLite or the GUI."""

    def __init__(
        self, host: str, port: int, token: str, submit: Callable[[BanEvent], bool],
        on_log: Callable[[str, str], None] | None = None, fallback_mode: str = "FT",
    ):
        normalized_host = str(host or "127.0.0.1").strip()
        if normalized_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Fabric listener may bind only to loopback")
        self.host = normalized_host
        self.port = int(port)
        self.token = str(token)
        self.submit = submit
        self.on_log = on_log
        self.fallback_mode = "RW" if str(fallback_mode).upper() == "RW" else "FT"
        self._server: ListenerServer | None = None
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger("banhelper.fabric")
        self.last_event_at = 0.0
        self.received = 0
        self.rejected = 0

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
            server_version = "BanHelper/2"

            def reply(self, status: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                if self.path != "/status":
                    self.reply(404, {"ok": False, "error": "not_found"})
                    return
                self.reply(200, {
                    "ok": True, "service": "BanHelper", "protocol_version": PROTOCOL_VERSION,
                    "queue_capacity": True,
                })

            def do_POST(self):  # noqa: N802
                started = time.time()
                if self.path != "/ban":
                    self.reply(404, {"ok": False, "error": "not_found"})
                    return
                try:
                    raw_length = self.headers.get("Content-Length")
                    if raw_length is None:
                        self.reply(411, {"ok": False, "error": "content_length_required"})
                        return
                    length = int(raw_length)
                    if length <= 0:
                        self.reply(400, {"ok": False, "error": "empty_body"})
                        return
                    if length > MAX_BODY_BYTES:
                        owner.rejected += 1
                        owner.report("WARNING", "Fabric запрос отклонён: тело слишком большое")
                        self.reply(413, {"ok": False, "error": "body_too_large"})
                        return
                    raw = self.rfile.read(length)
                    try:
                        payload = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        owner.rejected += 1
                        owner.report("WARNING", "Fabric запрос отклонён: некорректный JSON")
                        self.reply(400, {"ok": False, "error": "invalid_json"})
                        return
                    supplied = self.headers.get("X-BanHelper-Token", payload.get("token", "") if isinstance(payload, dict) else "")
                    if owner.token and not hmac.compare_digest(str(supplied), owner.token):
                        owner.rejected += 1
                        owner.report("WARNING", "Fabric запрос отклонён: неверный токен")
                        self.reply(401, {"ok": False, "error": "invalid_token"})
                        return
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
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.1}, name="FabricHTTP", daemon=False)
        self._thread.start()
        self.report("INFO", f"Fabric listener запущен на {self.host}:{self.port}")

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
            self.report("INFO", "Fabric listener остановлен")
            self._server = None
            self._thread = None
        return stopped
