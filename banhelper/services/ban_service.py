from __future__ import annotations

import logging
import csv
import shutil
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path
from queue import Empty
from typing import Any

from PySide6.QtCore import QObject, Signal

from banhelper.app.paths import AppPaths
from banhelper.domain.models import BanEvent
from banhelper.infrastructure.database import Database
from banhelper.infrastructure.repositories import BanRepository, DEFAULT_SETTINGS

from .event_queue import BoundedWorkQueue, WorkItem
from .import_service import LegacyImportService
from .statistics_service import StatisticsService


class ServiceSignals(QObject):
    initialized = Signal(object, object, object, object)
    current_changed = Signal(object)
    queue_changed = Signal(object)
    history_loaded = Signal(object, int, int)
    statistics_changed = Signal(object)
    confirmed = Signal(object)
    settings_changed = Signal(object)
    layout_loaded = Signal(str, bytes, bytes, bool)
    layouts_changed = Signal(object)
    log = Signal(str, str)
    error = Signal(str, str)
    stopped = Signal()


class BanService:
    """Thread-confined SQLite service and bounded command/event pipeline."""

    def __init__(self, paths: AppPaths, *, queue_size: int = 2048):
        self.paths = paths
        self.signals = ServiceSignals()
        self.work = BoundedWorkQueue(queue_size)
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._shutdown_requested = threading.Event()
        self._logger = logging.getLogger("banhelper.service")
        self.latencies_ms: list[float] = []
        self.duplicates = 0
        self.accepted = 0
        self._seen_lock = threading.Lock()
        self._seen_ids: OrderedDict[str, None] = OrderedDict()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopping.clear()
        self._shutdown_requested.clear()
        self._thread = threading.Thread(target=self._run, name="BanService", daemon=False)
        self._thread.start()

    def submit_event(self, event: BanEvent) -> bool:
        with self._seen_lock:
            if event.event_id in self._seen_ids:
                self._seen_ids.move_to_end(event.event_id)
                self.duplicates += 1
                self.signals.log.emit("WARNING", f"Повторная доставка пропущена: {event.event_id}")
                return True
            self._seen_ids[event.event_id] = None
            while len(self._seen_ids) > 50_000:
                self._seen_ids.popitem(last=False)
        accepted = self.work.put(WorkItem("event", event))
        if not accepted:
            with self._seen_lock:
                self._seen_ids.pop(event.event_id, None)
        return accepted

    def command(self, name: str, payload: Any = None) -> bool:
        accepted = self.work.put(WorkItem(name, payload))
        if not accepted:
            self.signals.error.emit(name, "Рабочая очередь переполнена")
        return accepted

    def request_stop(self) -> None:
        # The sentinel is queued after any final layout/settings writes.  The
        # caller waits only after Qt's event loop has already stopped.
        self._shutdown_requested.set()
        self.work.put(WorkItem("stop"))

    def wait(self, timeout: float = 5.0) -> bool:
        thread = self._thread
        if not thread:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def _emit_snapshot(self, repo: BanRepository) -> None:
        current, queue = repo.pending_snapshot()
        self.signals.current_changed.emit(current)
        self.signals.queue_changed.emit(queue)

    def _run(self) -> None:
        connection: sqlite3.Connection | None = None
        try:
            connection = Database(self.paths.database).connect()
            repo = BanRepository(connection)
            current, queue = repo.pending_snapshot()
            settings = repo.settings()
            stats = StatisticsService(repo).snapshot()
            self.signals.initialized.emit(current, queue, stats, settings)
            self.signals.layouts_changed.emit(repo.layout_names())
            self.signals.log.emit("INFO", "Фоновый сервис и SQLite WAL запущены")
            while not self._stopping.is_set():
                try:
                    item = self.work.get(timeout=0.25)
                except Empty:
                    if self._shutdown_requested.is_set():
                        break
                    continue
                if item.kind == "stop":
                    break
                try:
                    if item.kind == "event":
                        batch = [item.payload]
                        deferred = None
                        deadline = time.monotonic() + 0.008
                        while len(batch) < 256:
                            try:
                                remaining = deadline - time.monotonic()
                                if remaining <= 0:
                                    break
                                following = self.work.get(timeout=remaining)
                            except Empty:
                                break
                            if following.kind != "event":
                                deferred = following
                                break
                            batch.append(following.payload)
                        self._handle_event_batch(repo, tuple(batch))
                        if deferred is not None:
                            if deferred.kind == "stop":
                                self._stopping.set()
                            else:
                                self._handle(repo, deferred)
                    else:
                        self._handle(repo, item)
                    if self._shutdown_requested.is_set() and self.work.size == 0:
                        break
                except Exception as exc:
                    self._logger.exception("service operation failed: %s", item.kind)
                    self.signals.error.emit(item.kind, str(exc))
                    self.signals.log.emit("ERROR", f"{item.kind}: {exc}")
        except Exception as exc:
            self._logger.exception("service startup failed")
            self.signals.error.emit("startup", str(exc))
        finally:
            if connection is not None:
                try:
                    connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    connection.close()
                except Exception:
                    self._logger.exception("database shutdown failed")
            self.signals.stopped.emit()

    def _handle(self, repo: BanRepository, item: WorkItem) -> None:
        kind, payload = item.kind, item.payload
        statistics = StatisticsService(repo)
        if kind == "confirm":
            record, current, queue, stats = repo.confirm_current(payload or None)
            self.signals.confirmed.emit(record)
            self.signals.current_changed.emit(current)
            self.signals.queue_changed.emit(queue)
            self.signals.statistics_changed.emit(stats)
            self.signals.log.emit("INFO", f"Подтверждён {record.player} · {record.reason}")
        elif kind == "delete_current":
            current, queue = repo.delete_current()
            self.signals.current_changed.emit(current)
            self.signals.queue_changed.emit(queue)
            self.signals.log.emit("INFO", "Текущая карточка удалена")
        elif kind == "skip_current":
            current, queue = repo.skip_current()
            self.signals.current_changed.emit(current)
            self.signals.queue_changed.emit(queue)
            self.signals.log.emit("INFO", "Текущая карточка перемещена в конец очереди")
        elif kind == "update_pending_reason":
            event_id, reason = payload
            if not repo.update_pending_reason(str(event_id), str(reason)):
                raise LookupError("Карточка для изменения причины не найдена")
        elif kind == "delete_queued":
            current, queue = repo.delete_queued(str(payload))
            self.signals.current_changed.emit(current)
            self.signals.queue_changed.emit(queue)
        elif kind == "move_queued":
            event_id, delta = payload
            self.signals.queue_changed.emit(repo.move_queued(event_id, int(delta)))
        elif kind == "activate_queued":
            current, queue = repo.activate_queued(str(payload))
            self.signals.current_changed.emit(current)
            self.signals.queue_changed.emit(queue)
            self.signals.log.emit("INFO", "Выбранный элемент очереди открыт")
        elif kind == "clear_queue":
            self.signals.queue_changed.emit(repo.clear_queue())
        elif kind == "load_history":
            filters = dict(payload or {})
            page = int(filters.pop("page", 0))
            records, total = repo.history_page(page=page, **filters)
            self.signals.history_loaded.emit(records, total, page)
        elif kind == "delete_history":
            if repo.delete_history(int(payload)):
                self.signals.statistics_changed.emit(repo.statistics())
        elif kind == "export_history":
            target, filters = payload
            target_path = Path(target)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            with target_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("event_id", "player", "reason", "mode", "confirmed_at", "report", "source"))
                for row in repo.history_export_rows(**dict(filters or {})):
                    writer.writerow(tuple(row))
                    count += 1
            self.signals.log.emit("INFO", f"История экспортирована: {count} записей · {target_path}")
        elif kind == "refresh_statistics":
            self.signals.statistics_changed.emit(statistics.snapshot())
        elif kind == "reset_week":
            self.signals.statistics_changed.emit(statistics.reset_week())
        elif kind == "reset_promotion":
            self.signals.statistics_changed.emit(statistics.reset_promotion())
        elif kind == "set_statistics_counts":
            total, week = payload
            self.signals.statistics_changed.emit(statistics.set_counts(total, week))
            self.signals.log.emit("INFO", f"Статистика скорректирована вручную: {total}/{week}")
        elif kind == "save_settings":
            repo.set_settings(dict(payload))
            settings = repo.settings()
            self.signals.settings_changed.emit(settings)
            self.signals.statistics_changed.emit(repo.statistics())
        elif kind == "save_layout":
            name, geometry, state, locked = payload
            repo.save_layout(name, geometry, state, locked)
            self.signals.layouts_changed.emit(repo.layout_names())
        elif kind == "load_layout":
            layout = repo.load_layout(str(payload))
            if layout:
                self.signals.layout_loaded.emit(str(payload), *layout)
            else:
                self.signals.error.emit("load_layout", "Профиль раскладки не найден")
        elif kind == "rename_layout":
            old, new = payload
            if not repo.rename_layout(old, new):
                raise ValueError("Не удалось переименовать профиль")
            repo.set_settings({"active_layout": new})
            self.signals.layouts_changed.emit(repo.layout_names())
        elif kind == "delete_layout":
            repo.delete_layout(str(payload))
            self.signals.layouts_changed.emit(repo.layout_names())
        elif kind == "backup":
            target = Path(payload)
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = sqlite3.connect(target)
            try:
                repo.db.backup(backup)
            finally:
                backup.close()
            self.signals.log.emit("INFO", f"Резервная копия создана: {target}")
        elif kind == "restore_backup":
            safety_path = self.paths.backups_dir / f"before-restore-{time.strftime('%Y%m%d-%H%M%S')}.sqlite3"
            safety_path.parent.mkdir(parents=True, exist_ok=True)
            safety = sqlite3.connect(safety_path)
            try:
                repo.db.backup(safety)
            finally:
                safety.close()
            source = sqlite3.connect(Path(payload))
            try:
                if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Резервная копия повреждена")
                source.backup(repo.db)
            finally:
                source.close()
            current, queue = repo.pending_snapshot()
            self.signals.initialized.emit(current, queue, repo.statistics(), repo.settings())
            self.signals.log.emit("INFO", f"Резервная копия восстановлена; копия до восстановления: {safety_path}")
        elif kind == "reset_settings":
            repo.set_settings(dict(DEFAULT_SETTINGS))
            self.signals.settings_changed.emit(repo.settings())
            self.signals.statistics_changed.emit(repo.statistics())
        elif kind == "import_legacy":
            report = LegacyImportService(repo, self.paths.backups_dir).run(payload)
            current, queue = repo.pending_snapshot()
            self.signals.current_changed.emit(current)
            self.signals.queue_changed.emit(queue)
            self.signals.statistics_changed.emit(repo.statistics())
            self.signals.log.emit(
                "INFO",
                f"Импорт завершён: добавлено {report.added}, пропущено {report.skipped}, повреждено {report.damaged}",
            )
        else:
            raise ValueError(f"unknown service command: {kind}")

    def _handle_event_batch(self, repo: BanRepository, events: tuple[BanEvent, ...]) -> None:
        accepted, duplicates, current, queue, latencies = repo.process_events(events)
        self.accepted += accepted
        self.duplicates += duplicates
        self.latencies_ms.extend(latencies)
        if len(self.latencies_ms) > 10_000:
            del self.latencies_ms[:1000]
        self.signals.current_changed.emit(current)
        self.signals.queue_changed.emit(queue)
        if accepted:
            self.signals.log.emit("INFO", f"Получено событий: {accepted}; очередь: {len(queue)}")
        if duplicates:
            self.signals.log.emit("WARNING", f"Повторных доставок пропущено: {duplicates}")
