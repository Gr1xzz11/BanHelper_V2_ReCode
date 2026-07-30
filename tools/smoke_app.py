from __future__ import annotations

import http.client
import json
import tempfile
import threading
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from banhelper.app.paths import AppPaths
from banhelper.infrastructure.database import Database
from banhelper.infrastructure.fabric_listener import FabricListener
from banhelper.infrastructure.repositories import BanRepository
from banhelper.services.ban_service import BanService
from banhelper.ui.main_window import MainWindow
from banhelper.ui.theme import build_stylesheet


def post(port: int, index: int) -> None:
    payload = {
        "protocol_version": 2, "event_id": f"smoke-event-{index:04d}",
        "event_type": "ban", "player": f"SmokePlayer_{index}", "moderator": "SmokeAdmin",
        "reason": "5.5" if index != 3 else "LIV", "server_mode": "RW" if index == 2 else "FT",
    }
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    connection.request(
        "POST", "/ban", body=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-BanHelper-Token": "smoke-token"},
    )
    response = connection.getresponse(); response.read(); connection.close()
    if response.status != 202:
        raise RuntimeError(f"listener returned {response.status}")


def wait_loop(app: QApplication, predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("GUI smoke timeout")


def run() -> dict[str, object]:
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion"); app.setStyleSheet(build_stylesheet())
    with tempfile.TemporaryDirectory(prefix="banhelper-smoke-") as root:
        paths = AppPaths.temporary(root); paths.ensure()
        connection = Database(paths.database).connect(); repo = BanRepository(connection)
        repo.set_settings({"listener_token": "smoke-token", "listener_port": 0, "active_layout": "Smoke"})
        connection.close()

        service = BanService(paths); window = MainWindow(service, paths)
        layout_updates: list[list[str]] = []; settings_updates: list[dict] = []
        service.signals.layouts_changed.connect(lambda names: layout_updates.append(list(names)))
        service.signals.settings_changed.connect(lambda values: settings_updates.append(dict(values)))
        listener = FabricListener("127.0.0.1", 0, "smoke-token", service.submit_event)
        service.start(); listener.start(); window.show()
        errors: list[str] = []

        def sender() -> None:
            try:
                for index in range(1, 4):
                    post(listener.port, index)
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(str(exc))

        thread = threading.Thread(target=sender, name="SmokeSender"); thread.start()
        wait_loop(app, lambda: service.accepted == 3 and window.current is not None and len(window.queue_panel.items) == 2)
        assert not errors
        assert window.current.player == "SmokePlayer_1"
        window.current_panel.confirm.click()
        wait_loop(app, lambda: window.statistics.total == 1 and window.current is not None and window.current.player == "SmokePlayer_2")
        assert window.current_panel.report.text().splitlines()[0] == "SmokePlayer_2 (RW)"
        window.active_layout = "Smoke"; window.save_layout()
        service.command("save_settings", {"active_layout": "Smoke"})
        wait_loop(app, lambda: any("Smoke" in names for names in layout_updates) and any(value.get("active_layout") == "Smoke" for value in settings_updates))
        thread.join(2); window.close(); listener.request_stop(); service.request_stop()
        assert listener.wait(3) and service.wait(3)

        connection = Database(paths.database).connect(); repo = BanRepository(connection)
        current, queue = repo.pending_snapshot(); stats = repo.statistics(); layout = repo.load_layout("Smoke")
        assert current and current.player == "SmokePlayer_2" and len(queue) == 1
        assert stats.total == stats.week == 1 and layout and layout[0] and layout[1]
        connection.close()

        restored_service = BanService(paths); restored_window = MainWindow(restored_service, paths)
        restored_service.start(); restored_window.show()
        wait_loop(app, lambda: restored_window.current is not None and restored_window.statistics.total == 1 and restored_window.active_layout == "Smoke")
        assert restored_window.current.player == "SmokePlayer_2"
        assert len(restored_window.queue_panel.items) == 1
        restored_window.close(); restored_service.request_stop(); assert restored_service.wait(3)
        return {
            "http_events": 3, "confirmed": 1, "restored_current": "SmokePlayer_2",
            "restored_queue": 1, "statistics_total": 1, "layout_restored": True,
            "clean_shutdown": True,
        }


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
