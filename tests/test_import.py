import json

from banhelper.app.paths import AppPaths
from banhelper.infrastructure.database import Database
from banhelper.infrastructure.repositories import BanRepository
from banhelper.services.import_service import LegacyImportService


def test_legacy_import_is_transactional_idempotent_and_ignores_cloud(tmp_path):
    legacy = tmp_path / "legacy"
    (legacy / "data").mkdir(parents=True)
    (legacy / "data_v2").mkdir()
    (legacy / "data" / "bans.json").write_text(json.dumps([
        {"id": "old-1", "player": "Player_1", "rule": "5.5", "server_mode": "FT", "timestamp": "2026-07-01T12:00:00", "report": "Player_1\n5.5\n10/2", "cloud": {"s3": "secret"}},
        {"id": "old-2", "player": "Player_2", "rule": "Выход с проверки", "server_mode": "FT", "timestamp": "2026-07-01T12:01:00"},
        {"id": "broken", "player": "bad player", "rule": "5.5"},
    ]), encoding="utf-8")
    (legacy / "data_v2" / "queue.json").write_text(json.dumps([
        {"player": "Queued_1", "reason": "4.3.1", "mode": "RW"}
    ]), encoding="utf-8")
    (legacy / "data_v2" / "settings.json").write_text(json.dumps({"admin": "Admin_1", "mode": "RW", "weekly_target": 100, "fabric": {"port": 8877, "token": "local-token"}, "counters": {"total": 12, "week": 3}}), encoding="utf-8")
    paths = AppPaths.temporary(tmp_path / "new")
    connection = Database(paths.database).connect(); repo = BanRepository(connection)
    importer = LegacyImportService(repo, paths.backups_dir)
    first = importer.run(legacy)
    first_settings = repo.settings()
    second = importer.run(legacy)
    assert first.added == 3 and first.damaged == 1
    assert second.added == 0
    assert repo.history_page()[1] == 2
    assert {row.reason for row in repo.history_page()[0]} == {"5.5", "LIV"}
    current, queue = repo.pending_snapshot()
    assert current.player == "Queued_1" and queue == ()
    assert repo.settings()["weekly_target"] == 100
    assert repo.settings()["admin_name"] == "Admin_1" and repo.settings()["manual_mode"] == "RW"
    assert repo.settings()["listener_port"] == 8877 and repo.settings()["listener_token"] == "local-token"
    assert repo.settings()["total_offset"] == first_settings["total_offset"]
    assert repo.settings()["week_offset"] == first_settings["week_offset"]
    assert connection.execute("SELECT COUNT(*) FROM import_sources").fetchone()[0] == 3
    row = connection.execute("SELECT raw_message FROM events WHERE event_id LIKE 'legacy-%'").fetchone()
    assert row[0] == ""
    assert list(paths.backups_dir.rglob("bans.json"))
    connection.close()


def test_corrupt_json_does_not_crash_whole_import(tmp_path):
    legacy = tmp_path / "legacy"; (legacy / "data").mkdir(parents=True)
    (legacy / "data" / "bans.json").write_text("{broken", encoding="utf-8")
    paths = AppPaths.temporary(tmp_path / "new")
    connection = Database(paths.database).connect(); repo = BanRepository(connection)
    report = LegacyImportService(repo, paths.backups_dir).run(legacy)
    assert report.damaged == 1 and report.added == 0
    connection.close()
