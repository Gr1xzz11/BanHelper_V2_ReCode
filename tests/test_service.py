from __future__ import annotations

import csv
import time

from banhelper.app.paths import AppPaths
from banhelper.domain.models import BanEvent
from banhelper.infrastructure.database import Database
from banhelper.infrastructure.repositories import BanRepository
from banhelper.services.ban_service import BanService


def event(index: int) -> BanEvent:
    return BanEvent.from_payload({
        "protocol_version": 2, "event_id": f"event-{index:04d}", "event_type": "ban",
        "player": f"Player_{index}", "moderator": "Admin", "reason": "5.5", "server_mode": "FT",
    }, received_at=time.time())


def wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("background operation timed out")


def test_history_export_runs_on_background_service(tmp_path):
    service = BanService(AppPaths.temporary(tmp_path))
    service.start()
    try:
        assert service.submit_event(event(1))
        wait_until(lambda: service.accepted == 1)
        assert service.command("confirm")
        target = tmp_path / "history.csv"
        assert service.command("export_history", (target, {}))
        wait_until(target.exists)
        wait_until(lambda: target.stat().st_size > 20)
        with target.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        assert rows[0][0:4] == ["event_id", "player", "reason", "mode"]
        assert rows[1][0:4] == ["event-0001", "Player_1", "5.5", "FT"]
    finally:
        service.request_stop()
        assert service.wait(3)


def test_shutdown_flushes_final_layout_write(tmp_path):
    paths = AppPaths.temporary(tmp_path)
    service = BanService(paths); service.start()
    assert service.command("save_layout", ("Final", b"geometry", b"state", True))
    service.request_stop(); assert service.wait(3)
    connection = Database(paths.database).connect(); repo = BanRepository(connection)
    assert repo.load_layout("Final") == (b"geometry", b"state", True)
    connection.close()
