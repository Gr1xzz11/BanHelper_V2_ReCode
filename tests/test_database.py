import time

from banhelper.domain.models import BanEvent
from banhelper.infrastructure.database import Database
from banhelper.infrastructure.repositories import BanRepository


def event(index: int, *, mode="FT", reason="5.5") -> BanEvent:
    return BanEvent.from_payload(
        {
            "protocol_version": 2,
            "event_id": f"event-{index:04d}",
            "event_type": "ban",
            "player": f"Player_{index}",
            "moderator": "Admin",
            "reason": reason,
            "server_mode": mode,
        },
        received_at=time.time(),
    )


def repository(tmp_path):
    connection = Database(tmp_path / "data.sqlite3").connect()
    return connection, BanRepository(connection)


def test_migration_enables_wal_and_foreign_keys(tmp_path):
    connection, _repo = repository(tmp_path)
    assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 1
    connection.close()


def test_persistent_deduplication_and_queue(tmp_path):
    connection, repo = repository(tmp_path)
    first = repo.process_event(event(1))
    second = repo.process_event(event(2, mode="RW"))
    duplicate = repo.process_event(event(1))
    assert first.current.player == "Player_1"
    assert [item.player for item in second.queue] == ["Player_2"]
    assert duplicate.duplicate and not duplicate.accepted
    connection.close()

    reopened = Database(tmp_path / "data.sqlite3").connect()
    restored = BanRepository(reopened)
    assert restored.process_event(event(1)).duplicate
    current, queue = restored.pending_snapshot()
    assert current.player == "Player_1" and queue[0].server_mode == "RW"
    reopened.close()


def test_confirmation_is_one_transaction_and_promotes_next(tmp_path):
    connection, repo = repository(tmp_path)
    repo.process_event(event(1))
    repo.process_event(event(2, mode="RW", reason="4.3.1"))
    record, current, queue, stats = repo.confirm_current()
    assert record.report == "Player_1\n5.5\n1/1"
    assert current.player == "Player_2" and queue == ()
    assert stats.total == stats.week == 1
    second, current, queue, stats = repo.confirm_current()
    assert second.report == "Player_2 (RW)\n4.3.1\n2/2"
    assert current is None and queue == () and stats.rw == 1
    connection.close()


def test_reset_epochs_do_not_delete_history(tmp_path):
    connection, repo = repository(tmp_path)
    repo.process_event(event(1))
    repo.confirm_current()
    assert repo.reset_week().week == 0
    assert repo.reset_promotion().total == 0
    records, total = repo.history_page()
    assert total == 1 and records[0].player == "Player_1"
    connection.close()


def test_manual_statistics_adjustment_preserves_history_and_future_counts(tmp_path):
    connection, repo = repository(tmp_path)
    repo.process_event(event(1)); repo.confirm_current()
    adjusted = repo.set_statistics_counts(250, 48)
    assert adjusted.total == 250 and adjusted.week == 48
    records, history_total = repo.history_page()
    assert history_total == 1 and records[0].player == "Player_1"
    repo.process_event(event(2)); _record, _current, _queue, updated = repo.confirm_current()
    assert updated.total == 251 and updated.week == 49
    connection.close()


def test_layout_profiles_round_trip(tmp_path):
    connection, repo = repository(tmp_path)
    repo.save_layout("Gaming", b"geometry", b"state", True)
    assert repo.load_layout("Gaming") == (b"geometry", b"state", True)
    assert repo.rename_layout("Gaming", "Main")
    assert repo.layout_names() == ["Main"]
    assert repo.delete_layout("Main")
    connection.close()


def test_selecting_waiting_item_swaps_current_without_loss(tmp_path):
    connection, repo = repository(tmp_path)
    for index in range(1, 4):
        repo.process_event(event(index))
    current, queue = repo.activate_queued("event-0003")
    assert current and current.event_id == "event-0003"
    assert [item.event_id for item in queue] == ["event-0002", "event-0001"]
    assert connection.execute("SELECT COUNT(*) FROM pending_queue").fetchone()[0] == 3
    connection.close()


def test_manually_selected_reason_survives_skip(tmp_path):
    connection, repo = repository(tmp_path)
    repo.process_event(event(1, reason="")); repo.process_event(event(2))
    assert repo.update_pending_reason("event-0001", "4.3.2")
    current, queue = repo.skip_current()
    assert current and current.event_id == "event-0002"
    assert queue[0].event_id == "event-0001" and queue[0].reason == "4.3.2"
    connection.close()


def test_history_filters_dates_and_sql_sorting(tmp_path):
    connection, repo = repository(tmp_path)
    repo.process_event(event(1, mode="FT", reason="5.5")); repo.confirm_current()
    repo.process_event(event(2, mode="RW", reason="LIV")); repo.confirm_current()
    now = time.time()
    connection.execute("UPDATE confirmed_bans SET confirmed_at=? WHERE event_id='event-0001'", (now - 10 * 86400,))
    connection.commit()
    recent, total = repo.history_page(from_ts=now - 86400, mode="RW")
    assert total == 1 and recent[0].event_id == "event-0002"
    ordered, total = repo.history_page(sort_by="player", sort_desc=False)
    assert total == 2 and [row.player for row in ordered] == ["Player_1", "Player_2"]
    connection.close()
