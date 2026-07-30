from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any

from banhelper.domain.models import BanEvent, ConfirmedBan, PendingBan, ProcessResult, Statistics
from banhelper.domain.reports import build_report
from banhelper.domain.validation import normalize_reason
from banhelper.domain.reasons import FT_REASONS, RW_REASONS


DEFAULT_SETTINGS: dict[str, Any] = {
    "admin_name": "",
    "weekly_target": 0,
    "manual_mode": "FT",
    "listener_host": "127.0.0.1",
    "listener_port": 8765,
    "listener_token": "banhelper-local",
    "listener_autostart": True,
    "theme": "graphite",
    "ui_scale": 1.0,
    "active_layout": "Основная",
    "log_level": "INFO",
    "favorite_reasons_ft": ["LIV", "5.5", "4.3.1", "4.3.2", "3.1"],
    "favorite_reasons_rw": ["LIV", "5.5", "4.3.1", "4.3.2", "3.1"],
    "reasons_ft": [reason.code for reason in FT_REASONS],
    "reasons_rw": [reason.code for reason in RW_REASONS],
    "shortcut_copy": "Ctrl+C",
    "shortcut_confirm": "Ctrl+Return",
    "shortcut_skip": "Ctrl+Shift+S",
    "shortcut_focus": "Ctrl+Shift+B",
    "shortcut_reason_1": "Alt+1",
    "shortcut_reason_2": "Alt+2",
    "shortcut_reason_3": "Alt+3",
    "shortcut_reason_4": "Alt+4",
    "shortcut_reason_5": "Alt+5",
    "backup_directory": "",
    "total_epoch": 0.0,
    "week_reset_epoch": 0.0,
    "total_offset": 0,
    "week_offset": 0,
}


def _pending(row: sqlite3.Row | None) -> PendingBan | None:
    if row is None:
        return None
    return PendingBan(
        event_id=row["event_id"], player=row["player"], reason=row["reason"],
        server_mode=row["server_mode"], source=row["source"],
        received_at=float(row["received_at"]), state=row["state"],
        position=int(row["position"]), event_type=row["event_type"],
    )


class BanRepository:
    """All methods are called by exactly one background worker thread."""

    def __init__(self, connection: sqlite3.Connection):
        self.db = connection
        self._seed_settings()

    def _seed_settings(self) -> None:
        now = time.time()
        self.db.execute("BEGIN")
        try:
            for key, value in DEFAULT_SETTINGS.items():
                self.db.execute(
                    "INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES (?,?,?)",
                    (key, json.dumps(value, ensure_ascii=False), now),
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return default

    def settings(self) -> dict[str, Any]:
        result = dict(DEFAULT_SETTINGS)
        for row in self.db.execute("SELECT key,value FROM settings"):
            try:
                result[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                continue
        return result

    def set_settings(self, values: dict[str, Any]) -> None:
        now = time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for key, value in values.items():
                if key not in DEFAULT_SETTINGS:
                    continue
                self.db.execute(
                    "INSERT INTO settings(key,value,updated_at) VALUES (?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                    (key, json.dumps(value, ensure_ascii=False), now),
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def process_event(self, event: BanEvent) -> ProcessResult:
        accepted, duplicates, current, queue, latencies = self.process_events((event,))
        return ProcessResult(bool(accepted), bool(duplicates), current, queue, latencies[0])

    def process_events(self, events: tuple[BanEvent, ...]) -> tuple[int, int, PendingBan | None, tuple[PendingBan, ...], list[float]]:
        """Persist an ingress burst in one transaction and build one snapshot."""
        if not events:
            current, queue = self.pending_snapshot()
            return 0, 0, current, queue, []
        accepted = duplicates = 0
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current_exists = self.db.execute(
                "SELECT 1 FROM pending_queue WHERE state='current'"
            ).fetchone() is not None
            position = int(self.db.execute("SELECT COALESCE(MAX(position),0)+1 FROM pending_queue").fetchone()[0])
            for event in events:
                cursor = self.db.execute(
                    """INSERT OR IGNORE INTO events(
                       event_id,protocol_version,event_type,player,moderator,reason,reason_raw,
                       server_mode,source,occurred_at,received_at,raw_message,raw_hover,status
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'pending')""",
                    (
                        event.event_id, event.protocol_version, event.event_type, event.player,
                        event.moderator, event.reason, event.reason_raw, event.server_mode,
                        event.source, event.occurred_at, event.received_at,
                        event.raw_message, event.raw_hover,
                    ),
                )
                if cursor.rowcount == 0:
                    duplicates += 1
                    continue
                state = "pending" if current_exists else "current"
                self.db.execute(
                    "INSERT INTO pending_queue(event_id,position,state) VALUES (?,?,?)",
                    (event.event_id, position, state),
                )
                self.db.execute("UPDATE events SET status=? WHERE event_id=?", (state, event.event_id))
                accepted += 1
                current_exists = True
                position += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        current, queue = self.pending_snapshot()
        completed = time.time()
        latencies = [max(0.0, (completed - event.received_at) * 1000) for event in events]
        return accepted, duplicates, current, queue, latencies

    def pending_snapshot(self) -> tuple[PendingBan | None, tuple[PendingBan, ...]]:
        sql = """SELECT e.event_id,e.player,e.reason,e.server_mode,e.source,e.received_at,
                        e.event_type,p.state,p.position
                 FROM pending_queue p JOIN events e ON e.event_id=p.event_id"""
        current = _pending(self.db.execute(sql + " WHERE p.state='current'").fetchone())
        queue = tuple(_pending(row) for row in self.db.execute(sql + " WHERE p.state='pending' ORDER BY p.position"))
        return current, tuple(item for item in queue if item is not None)

    def _promote_next(self) -> None:
        row = self.db.execute(
            "SELECT event_id FROM pending_queue WHERE state='pending' ORDER BY position LIMIT 1"
        ).fetchone()
        if row:
            self.db.execute("UPDATE pending_queue SET state='current',position=0 WHERE event_id=?", (row[0],))
            self.db.execute("UPDATE events SET status='current' WHERE event_id=?", (row[0],))

    @staticmethod
    def _monday_epoch(now: float | None = None) -> float:
        local = datetime.fromtimestamp(now or time.time()).astimezone()
        monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return monday.timestamp()

    def _epochs(self) -> tuple[float, float]:
        total_epoch = float(self.get_setting("total_epoch", 0.0) or 0.0)
        week_reset = float(self.get_setting("week_reset_epoch", 0.0) or 0.0)
        return total_epoch, max(self._monday_epoch(), week_reset)

    def _counts(self) -> tuple[int, int]:
        total_epoch, week_epoch = self._epochs()
        total = int(self.db.execute("SELECT COUNT(*) FROM confirmed_bans WHERE confirmed_at>=?", (total_epoch,)).fetchone()[0])
        week = int(self.db.execute("SELECT COUNT(*) FROM confirmed_bans WHERE confirmed_at>=?", (week_epoch,)).fetchone()[0])
        return total + int(self.get_setting("total_offset", 0) or 0), week + int(self.get_setting("week_offset", 0) or 0)

    def confirm_current(self, reason: str | None = None) -> tuple[ConfirmedBan, PendingBan | None, tuple[PendingBan, ...], Statistics]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                """SELECT e.* FROM pending_queue p JOIN events e ON e.event_id=p.event_id
                   WHERE p.state='current'"""
            ).fetchone()
            if not row:
                raise LookupError("no current ban")
            selected_reason = normalize_reason(reason or row["reason"], event_type=row["event_type"])
            total, week = self._counts()
            total += 1
            week += 1
            report = build_report(row["player"], selected_reason, total, week, row["server_mode"])
            confirmed_at = time.time()
            cursor = self.db.execute(
                """INSERT INTO confirmed_bans(event_id,player,reason,server_mode,report,source,confirmed_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (row["event_id"], row["player"], selected_reason, row["server_mode"], report, row["source"], confirmed_at),
            )
            self.db.execute("DELETE FROM pending_queue WHERE event_id=?", (row["event_id"],))
            self.db.execute("UPDATE events SET status='confirmed',reason=? WHERE event_id=?", (selected_reason, row["event_id"]))
            self._promote_next()
            self.db.commit()
            record = ConfirmedBan(
                int(cursor.lastrowid), row["event_id"], row["player"], selected_reason,
                row["server_mode"], report, row["source"], confirmed_at,
            )
        except Exception:
            self.db.rollback()
            raise
        current, queue = self.pending_snapshot()
        return record, current, queue, self.statistics()

    def delete_current(self) -> tuple[PendingBan | None, tuple[PendingBan, ...]]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT event_id FROM pending_queue WHERE state='current'").fetchone()
            if row:
                self.db.execute("DELETE FROM pending_queue WHERE event_id=?", (row[0],))
                self.db.execute("UPDATE events SET status='deleted' WHERE event_id=?", (row[0],))
                self._promote_next()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.pending_snapshot()

    def skip_current(self) -> tuple[PendingBan | None, tuple[PendingBan, ...]]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT event_id FROM pending_queue WHERE state='current'").fetchone()
            waiting = self.db.execute("SELECT COUNT(*) FROM pending_queue WHERE state='pending'").fetchone()[0]
            if row and waiting:
                position = int(self.db.execute("SELECT COALESCE(MAX(position),0)+1 FROM pending_queue").fetchone()[0])
                self.db.execute("UPDATE pending_queue SET state='pending',position=? WHERE event_id=?", (position, row[0]))
                self.db.execute("UPDATE events SET status='pending' WHERE event_id=?", (row[0],))
                self._promote_next()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.pending_snapshot()

    def update_pending_reason(self, event_id: str, reason: str) -> bool:
        clean = normalize_reason(reason)
        cursor = self.db.execute(
            "UPDATE events SET reason=? WHERE event_id=? AND status IN ('current','pending')",
            (clean, event_id),
        )
        return cursor.rowcount > 0

    def delete_queued(self, event_id: str) -> tuple[PendingBan | None, tuple[PendingBan, ...]]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT state FROM pending_queue WHERE event_id=?", (event_id,)).fetchone()
            if row:
                was_current = row[0] == "current"
                self.db.execute("DELETE FROM pending_queue WHERE event_id=?", (event_id,))
                self.db.execute("UPDATE events SET status='deleted' WHERE event_id=?", (event_id,))
                if was_current:
                    self._promote_next()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.pending_snapshot()

    def move_queued(self, event_id: str, delta: int) -> tuple[PendingBan, ...]:
        rows = list(self.db.execute("SELECT event_id,position FROM pending_queue WHERE state='pending' ORDER BY position"))
        index = next((i for i, row in enumerate(rows) if row["event_id"] == event_id), -1)
        target = index + (1 if delta > 0 else -1)
        if index < 0 or target < 0 or target >= len(rows):
            return self.pending_snapshot()[1]
        self.db.execute("BEGIN IMMEDIATE")
        try:
            a, b = rows[index], rows[target]
            self.db.execute("UPDATE pending_queue SET position=? WHERE event_id=?", (-1, a["event_id"]))
            self.db.execute("UPDATE pending_queue SET position=? WHERE event_id=?", (a["position"], b["event_id"]))
            self.db.execute("UPDATE pending_queue SET position=? WHERE event_id=?", (b["position"], a["event_id"]))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.pending_snapshot()[1]

    def activate_queued(self, event_id: str) -> tuple[PendingBan | None, tuple[PendingBan, ...]]:
        """Open a waiting item now and move the previous current item to the queue."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            target = self.db.execute(
                "SELECT state FROM pending_queue WHERE event_id=?", (event_id,)
            ).fetchone()
            if not target or target["state"] != "pending":
                self.db.rollback()
                return self.pending_snapshot()
            current = self.db.execute(
                "SELECT event_id FROM pending_queue WHERE state='current'"
            ).fetchone()
            if current:
                position = int(self.db.execute(
                    "SELECT COALESCE(MAX(position),0)+1 FROM pending_queue"
                ).fetchone()[0])
                self.db.execute(
                    "UPDATE pending_queue SET state='pending',position=? WHERE event_id=?",
                    (position, current["event_id"]),
                )
                self.db.execute(
                    "UPDATE events SET status='pending' WHERE event_id=?", (current["event_id"],)
                )
            self.db.execute(
                "UPDATE pending_queue SET state='current',position=0 WHERE event_id=?", (event_id,)
            )
            self.db.execute("UPDATE events SET status='current' WHERE event_id=?", (event_id,))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.pending_snapshot()

    def clear_queue(self) -> tuple[PendingBan, ...]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            ids = [row[0] for row in self.db.execute("SELECT event_id FROM pending_queue WHERE state='pending'")]
            self.db.executemany("UPDATE events SET status='deleted' WHERE event_id=?", ((value,) for value in ids))
            self.db.execute("DELETE FROM pending_queue WHERE state='pending'")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.pending_snapshot()[1]

    @staticmethod
    def _history_filter(
        *, query: str = "", mode: str = "", reason: str = "",
        from_ts: float = 0.0, to_ts: float = 0.0,
    ) -> tuple[str, list[Any]]:
        clauses, params = [], []
        if query:
            clauses.append("player LIKE ? COLLATE NOCASE")
            params.append(f"%{query}%")
        if mode in {"FT", "RW"}:
            clauses.append("server_mode=?")
            params.append(mode)
        if reason:
            clauses.append("reason=?")
            params.append(reason)
        if from_ts > 0:
            clauses.append("confirmed_at>=?")
            params.append(float(from_ts))
        if to_ts > 0:
            clauses.append("confirmed_at<=?")
            params.append(float(to_ts))
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), params

    def history_page(
        self, *, page: int = 0, page_size: int = 100, query: str = "",
        mode: str = "", reason: str = "", from_ts: float = 0.0,
        to_ts: float = 0.0, sort_by: str = "confirmed_at", sort_desc: bool = True,
    ) -> tuple[list[ConfirmedBan], int]:
        where, params = self._history_filter(
            query=query, mode=mode, reason=reason, from_ts=from_ts, to_ts=to_ts,
        )
        order_columns = {
            "player": "player COLLATE NOCASE", "reason": "reason",
            "server_mode": "server_mode", "confirmed_at": "confirmed_at",
            "source": "source COLLATE NOCASE", "event_id": "event_id",
        }
        order = order_columns.get(sort_by, "confirmed_at")
        direction = "DESC" if sort_desc else "ASC"
        total = int(self.db.execute("SELECT COUNT(*) FROM confirmed_bans" + where, params).fetchone()[0])
        rows = self.db.execute(
            f"SELECT * FROM confirmed_bans{where} ORDER BY {order} {direction} LIMIT ? OFFSET ?",
            (*params, max(1, min(page_size, 250)), max(0, page) * page_size),
        )
        records = [ConfirmedBan(**dict(row)) for row in rows]
        return records, total

    def history_export_rows(self, **filters: Any):
        where, params = self._history_filter(
            query=str(filters.get("query", "")), mode=str(filters.get("mode", "")),
            reason=str(filters.get("reason", "")), from_ts=float(filters.get("from_ts", 0.0)),
            to_ts=float(filters.get("to_ts", 0.0)),
        )
        return self.db.execute(
            "SELECT event_id,player,reason,server_mode,confirmed_at,report,source "
            f"FROM confirmed_bans{where} ORDER BY confirmed_at DESC",
            params,
        )

    def delete_history(self, record_id: int) -> bool:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT event_id FROM confirmed_bans WHERE id=?", (record_id,)).fetchone()
            if not row:
                self.db.rollback()
                return False
            self.db.execute("DELETE FROM confirmed_bans WHERE id=?", (record_id,))
            self.db.execute("UPDATE events SET status='deleted' WHERE event_id=?", (row[0],))
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def statistics(self) -> Statistics:
        total, week = self._counts()
        target = int(self.get_setting("weekly_target", 0) or 0)
        total_epoch, _ = self._epochs()
        by_mode = {row["server_mode"]: int(row["amount"]) for row in self.db.execute(
            "SELECT server_mode,COUNT(*) amount FROM confirmed_bans WHERE confirmed_at>=? GROUP BY server_mode", (total_epoch,)
        )}
        top = tuple((row["reason"], int(row["amount"])) for row in self.db.execute(
            "SELECT reason,COUNT(*) amount FROM confirmed_bans WHERE confirmed_at>=? GROUP BY reason ORDER BY amount DESC LIMIT 6", (total_epoch,)
        ))
        since = time.time() - 7 * 86400
        recent = tuple((row["day"], int(row["amount"])) for row in self.db.execute(
            "SELECT date(confirmed_at,'unixepoch','localtime') day,COUNT(*) amount FROM confirmed_bans "
            "WHERE confirmed_at>=? GROUP BY day ORDER BY day", (since,)
        ))
        return Statistics(total, week, target, by_mode.get("FT", 0), by_mode.get("RW", 0), top, recent)

    def reset_week(self) -> Statistics:
        self.set_settings({"week_reset_epoch": time.time(), "week_offset": 0})
        return self.statistics()

    def reset_promotion(self) -> Statistics:
        now = time.time()
        self.set_settings({"total_epoch": now, "week_reset_epoch": now, "total_offset": 0, "week_offset": 0})
        return self.statistics()

    def set_statistics_counts(self, total: int, week: int) -> Statistics:
        total, week = int(total), int(week)
        if total < 0 or week < 0:
            raise ValueError("Счётчики не могут быть отрицательными")
        if week > total:
            raise ValueError("Недельный счётчик не может быть больше общего")
        total_epoch, week_epoch = self._epochs()
        stored_total = int(self.db.execute("SELECT COUNT(*) FROM confirmed_bans WHERE confirmed_at>=?", (total_epoch,)).fetchone()[0])
        stored_week = int(self.db.execute("SELECT COUNT(*) FROM confirmed_bans WHERE confirmed_at>=?", (week_epoch,)).fetchone()[0])
        self.set_settings({"total_offset": total - stored_total, "week_offset": week - stored_week})
        return self.statistics()

    def save_layout(self, name: str, geometry: bytes, state: bytes, locked: bool) -> None:
        self.db.execute(
            """INSERT INTO layout_profiles(name,geometry,state,locked,updated_at) VALUES (?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET geometry=excluded.geometry,state=excluded.state,
               locked=excluded.locked,updated_at=excluded.updated_at""",
            (name, geometry, state, int(locked), time.time()),
        )

    def load_layout(self, name: str) -> tuple[bytes, bytes, bool] | None:
        row = self.db.execute("SELECT geometry,state,locked FROM layout_profiles WHERE name=?", (name,)).fetchone()
        return (bytes(row[0]), bytes(row[1]), bool(row[2])) if row else None

    def layout_names(self) -> list[str]:
        return [row[0] for row in self.db.execute("SELECT name FROM layout_profiles ORDER BY name COLLATE NOCASE")]

    def rename_layout(self, old: str, new: str) -> bool:
        try:
            cursor = self.db.execute("UPDATE layout_profiles SET name=?,updated_at=? WHERE name=?", (new, time.time(), old))
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    def delete_layout(self, name: str) -> bool:
        return self.db.execute("DELETE FROM layout_profiles WHERE name=?", (name,)).rowcount > 0
