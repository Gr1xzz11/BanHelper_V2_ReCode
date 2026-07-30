from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from banhelper.domain.reports import build_report
from banhelper.domain.validation import normalize_mode, normalize_player, normalize_reason
from banhelper.infrastructure.repositories import BanRepository


@dataclass(frozen=True, slots=True)
class ImportReport:
    added: int
    skipped: int
    damaged: int
    backup_path: str
    sources: tuple[str, ...]


class LegacyImportService:
    def __init__(self, repo: BanRepository, backups_dir: Path):
        self.repo = repo
        self.backups_dir = backups_dir

    def run(self, root: str | Path) -> ImportReport:
        base = Path(root)
        candidates = (
            base / "data" / "bans.json",
            base / "data_v2" / "history.json",
            base / "data_v2" / "queue.json",
            base / "data_v2" / "settings.json",
            base / "data" / "config.json",
        )
        existing = [path for path in candidates if path.is_file()]
        if not existing:
            raise FileNotFoundError("Поддерживаемые файлы старых данных не найдены")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = self.backups_dir / f"legacy-import-{stamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        for source in existing:
            shutil.copy2(source, backup_dir / source.name)

        added = skipped = damaged = 0
        imported_sources: list[str] = []
        history_paths = [path for path in existing if path.name in {"bans.json", "history.json"}]
        queue_paths = [path for path in existing if path.name == "queue.json"]
        settings_paths = [path for path in existing if path.name in {"settings.json", "config.json"}]
        self.repo.db.execute("BEGIN IMMEDIATE")
        try:
            for path in history_paths:
                source_key = self._source_key(path)
                if self.repo.db.execute("SELECT 1 FROM import_sources WHERE source_key=?", (source_key,)).fetchone():
                    skipped += 1
                    continue
                raw = self._load(path)
                if not isinstance(raw, list):
                    damaged += 1
                    continue
                local_added = local_skipped = local_damaged = 0
                for index, item in enumerate(raw):
                    try:
                        if not isinstance(item, dict): raise ValueError("record is not an object")
                        player = normalize_player(item.get("player"))
                        reason = self._legacy_reason(item.get("rule", item.get("reason")))
                        mode = normalize_mode(item.get("server_mode", item.get("mode", "FT")), fallback="FT")
                        timestamp_text = str(item.get("timestamp", ""))
                        try: confirmed_at = datetime.fromisoformat(timestamp_text).timestamp()
                        except ValueError: confirmed_at = time.time()
                        stable = str(item.get("id") or self._stable_id(path, index, item))
                        event_id = "legacy-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:32]
                        cursor = self.repo.db.execute(
                            """INSERT OR IGNORE INTO events(event_id,protocol_version,event_type,player,moderator,reason,
                               reason_raw,server_mode,source,occurred_at,received_at,raw_message,raw_hover,status)
                               VALUES (?,2,'ban',?,'',?, ?,?,'legacy',?,?, '', '', 'confirmed')""",
                            (event_id, player, reason, reason, mode, timestamp_text or str(confirmed_at), confirmed_at),
                        )
                        if cursor.rowcount == 0:
                            local_skipped += 1; continue
                        report = self._legacy_report(item.get("report"), player, reason, mode)
                        self.repo.db.execute(
                            "INSERT INTO confirmed_bans(event_id,player,reason,server_mode,report,source,confirmed_at) VALUES (?,?,?,?,?,'legacy',?)",
                            (event_id, player, reason, mode, report, confirmed_at),
                        )
                        local_added += 1
                    except Exception:
                        local_damaged += 1
                self.repo.db.execute(
                    "INSERT INTO import_sources(source_key,source_path,imported_at,added,skipped,damaged,backup_path) VALUES (?,?,?,?,?,?,?)",
                    (source_key, str(path), time.time(), local_added, local_skipped, local_damaged, str(backup_dir)),
                )
                added += local_added; skipped += local_skipped; damaged += local_damaged; imported_sources.append(str(path))

            for path in queue_paths:
                source_key = self._source_key(path)
                if self.repo.db.execute("SELECT 1 FROM import_sources WHERE source_key=?", (source_key,)).fetchone():
                    skipped += 1
                    continue
                raw = self._load(path)
                if not isinstance(raw, list): damaged += 1; continue
                local_added = local_skipped = local_damaged = 0
                for index, item in enumerate(raw):
                    try:
                        if not isinstance(item, dict): raise ValueError
                        player = normalize_player(item.get("player")); reason = self._legacy_reason(item.get("reason"), allow_empty=True)
                        mode = normalize_mode(item.get("mode", item.get("server_mode", "FT")), fallback="FT")
                        event_id = "legacyq-" + hashlib.sha256(self._stable_id(path, index, item).encode()).hexdigest()[:32]
                        cursor = self.repo.db.execute(
                            """INSERT OR IGNORE INTO events(event_id,protocol_version,event_type,player,moderator,reason,reason_raw,
                               server_mode,source,occurred_at,received_at,raw_message,raw_hover,status)
                               VALUES (?,2,'ban',?,'',?, ?,?,'legacy','',?,'','','pending')""",
                            (event_id, player, reason, reason, mode, time.time()),
                        )
                        if cursor.rowcount == 0: local_skipped += 1; continue
                        current_exists = self.repo.db.execute("SELECT 1 FROM pending_queue WHERE state='current'").fetchone()
                        state = "pending" if current_exists else "current"
                        position = self.repo.db.execute("SELECT COALESCE(MAX(position),0)+1 FROM pending_queue").fetchone()[0]
                        self.repo.db.execute("INSERT INTO pending_queue(event_id,position,state) VALUES (?,?,?)", (event_id, position, state))
                        self.repo.db.execute("UPDATE events SET status=? WHERE event_id=?", (state, event_id)); local_added += 1
                    except Exception: local_damaged += 1
                self.repo.db.execute(
                    "INSERT INTO import_sources(source_key,source_path,imported_at,added,skipped,damaged,backup_path) VALUES (?,?,?,?,?,?,?)",
                    (source_key, str(path), time.time(), local_added, local_skipped, local_damaged, str(backup_dir)),
                )
                added += local_added; skipped += local_skipped; damaged += local_damaged; imported_sources.append(str(path))

            for path in settings_paths:
                source_key = self._source_key(path)
                if self.repo.db.execute("SELECT 1 FROM import_sources WHERE source_key=?", (source_key,)).fetchone():
                    skipped += 1
                    continue
                raw = self._load(path)
                if not isinstance(raw, dict): damaged += 1; continue
                values = {}
                if "admin_filter" in raw or "admin" in raw:
                    values["admin_name"] = str(raw.get("admin_filter", raw.get("admin", "")))
                if "weekly_target" in raw: values["weekly_target"] = int(raw["weekly_target"] or 0)
                if "active_mode" in raw or "mode" in raw:
                    values["manual_mode"] = normalize_mode(raw.get("active_mode", raw.get("mode")), fallback="FT")
                fabric = raw.get("fabric") if isinstance(raw.get("fabric"), dict) else {}
                port = fabric.get("port", raw.get("fabric_port"))
                token = fabric.get("token", raw.get("fabric_token"))
                if port is not None:
                    values["listener_port"] = max(1024, min(65535, int(port)))
                if token is not None:
                    values["listener_token"] = str(token)
                favorites = raw.get("favorite_reasons")
                if isinstance(favorites, list):
                    cleaned_favorites = []
                    for value in favorites:
                        try: clean = normalize_reason(value)
                        except Exception: continue
                        if clean not in cleaned_favorites: cleaned_favorites.append(clean)
                    values["favorite_reasons_ft"] = cleaned_favorites
                quick = raw.get("quick_reasons")
                if isinstance(quick, dict):
                    reason_codes = []
                    for group in quick.values():
                        if not isinstance(group, dict): continue
                        for code in group:
                            try: clean = normalize_reason(code)
                            except Exception: continue
                            if clean not in reason_codes: reason_codes.append(clean)
                    if reason_codes: values["reasons_ft"] = reason_codes
                counters = raw.get("counters") or {}
                if isinstance(counters, dict):
                    values["total_offset"] = max(0, int(counters.get("total", 0)) - self.repo._counts()[0])
                    values["week_offset"] = max(0, int(counters.get("week", counters.get("day", 0))) - self.repo._counts()[1])
                now = time.time()
                for key, value in values.items():
                    self.repo.db.execute(
                        "INSERT INTO settings(key,value,updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                        (key, json.dumps(value, ensure_ascii=False), now),
                    )
                self.repo.db.execute(
                    "INSERT INTO import_sources(source_key,source_path,imported_at,added,skipped,damaged,backup_path) VALUES (?,?,?,?,?,?,?)",
                    (source_key, str(path), time.time(), 0, 0, 0, str(backup_dir)),
                )
                imported_sources.append(str(path))
            self.repo.db.commit()
        except Exception:
            self.repo.db.rollback(); raise
        return ImportReport(added, skipped, damaged, str(backup_dir), tuple(imported_sources))

    @staticmethod
    def _load(path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _source_key(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _stable_id(path: Path, index: int, item: dict) -> str:
        return f"{path.name}:{index}:{item.get('timestamp')}:{item.get('player')}:{item.get('rule', item.get('reason'))}"

    @staticmethod
    def _legacy_reason(value, *, allow_empty: bool = False) -> str:
        raw = str(value or "").strip()
        folded = raw.casefold()
        if "выход с проверки" in folded or folded in {"1.21", "1.21.4"}:
            return "LIV"
        bracketed = re.search(r"\[(\d+(?:\.\d+)+)\]", raw)
        if bracketed:
            return normalize_reason(bracketed.group(1))
        return normalize_reason(raw, allow_empty=allow_empty)

    @staticmethod
    def _legacy_report(value, player: str, reason: str, mode: str) -> str:
        lines = str(value or "").splitlines()
        total = week = 0
        if len(lines) >= 3:
            match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", lines[2])
            if match:
                total, week = int(match.group(1)), int(match.group(2))
                # Several v1 releases wrote week/total.  A weekly value cannot
                # exceed the all-time value, so that case is unambiguous.
                if week > total:
                    total, week = week, total
        return build_report(player, reason, total, week, mode)
