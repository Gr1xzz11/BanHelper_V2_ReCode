from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox, QPushButton, QSizePolicy, QToolBar, QVBoxLayout, QWidget

from banhelper.app.paths import AppPaths
from banhelper.domain.models import PendingBan, Statistics
from banhelper.services.ban_service import BanService
from banhelper.services.layout_service import clean_profile_name
from banhelper.domain.validation import ValidationError, normalize_reason
from banhelper.ui.dialogs.settings_dialog import SettingsDialog
from banhelper.ui.dialogs.statistics_dialog import StatisticsAdjustmentDialog
from banhelper.ui.docks.base import PanelDock
from banhelper.ui.docks.control_panel import ControlPanel
from banhelper.ui.docks.current_ban import CurrentBanPanel
from banhelper.ui.docks.fabric_status import FabricStatusPanel
from banhelper.ui.docks.history_panel import HistoryPanel
from banhelper.ui.docks.log_panel import EventLogPanel
from banhelper.ui.docks.queue_panel import QueuePanel
from banhelper.ui.docks.reasons_panel import ReasonsPanel
from banhelper.ui.docks.statistics_panel import StatisticsPanel
from banhelper.ui.theme import build_stylesheet
from banhelper.ui.icons import icon


class MainWindow(QMainWindow):
    def __init__(self, service: BanService, paths: AppPaths, listener_manager=None):
        super().__init__(); self.service = service; self.paths = paths; self.listener_manager = listener_manager
        self.settings: dict = {}; self.current: PendingBan | None = None; self.statistics = Statistics()
        self.active_layout = "Основная"; self.locked = False; self._layout_names: list[str] = []
        self._factory_state: QByteArray | None = None
        self.layout_timer = QTimer(self); self.layout_timer.setSingleShot(True); self.layout_timer.setInterval(600); self.layout_timer.timeout.connect(self.save_layout)
        self.setObjectName("BanHelperMainWindow"); self.setWindowTitle("BanHelper 2"); self.setMinimumSize(1100, 700); self.resize(1420, 860)
        self.setDockNestingEnabled(True); self.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AnimatedDocks | QMainWindow.GroupedDragging)
        self.workspace = QWidget(objectName="Workspace"); workspace_layout = QVBoxLayout(self.workspace)
        workspace_label = QLabel("Все панели скрыты\nВерните их через «Вид → Панели»", alignment=Qt.AlignCenter, objectName="Eyebrow")
        workspace_layout.addWidget(workspace_label); self.workspace.setMaximumSize(1, 1); self.setCentralWidget(self.workspace)
        self._build_panels(); self._build_menu(); self._build_toolbar(); self._connect_service(); self._default_layout()
        if self.listener_manager:
            self.listener_manager.test_completed.connect(lambda ok, message: self.statusBar().showMessage(message, 4000))
        self._install_shortcuts()

    def _panel(self, title, name, widget, _area):
        dock = PanelDock(title, name, widget, self)
        dock.dockLocationChanged.connect(lambda _area: self.layout_timer.start())
        dock.topLevelChanged.connect(lambda _floating: self.layout_timer.start())
        dock.visibilityChanged.connect(lambda _visible: (self.layout_timer.start(), QTimer.singleShot(0, self._update_workspace)))
        return dock

    def _build_panels(self) -> None:
        self.current_panel = CurrentBanPanel(); self.queue_panel = QueuePanel(); self.reasons_panel = ReasonsPanel(); self.history_panel = HistoryPanel(); self.stats_panel = StatisticsPanel(); self.log_panel = EventLogPanel(); self.control_panel = ControlPanel(); self.fabric_panel = FabricStatusPanel()
        self.docks = {
            "current": self._panel("Текущий бан", "dockCurrent", self.current_panel, Qt.LeftDockWidgetArea),
            "queue": self._panel("Очередь", "dockQueue", self.queue_panel, Qt.RightDockWidgetArea),
            "reasons": self._panel("Быстрые причины", "dockReasons", self.reasons_panel, Qt.RightDockWidgetArea),
            "history": self._panel("История", "dockHistory", self.history_panel, Qt.BottomDockWidgetArea),
            "statistics": self._panel("Статистика", "dockStatistics", self.stats_panel, Qt.LeftDockWidgetArea),
            "log": self._panel("Журнал событий", "dockLog", self.log_panel, Qt.BottomDockWidgetArea),
            "control": self._panel("Управление", "dockControl", self.control_panel, Qt.RightDockWidgetArea),
            "fabric": self._panel("Состояние Fabric", "dockFabric", self.fabric_panel, Qt.RightDockWidgetArea),
        }
        self.current_panel.copy_requested.connect(self.copy_report); self.current_panel.confirm_requested.connect(lambda reason: self.service.command("confirm", reason)); self.current_panel.skip_requested.connect(lambda: self.service.command("skip_current")); self.current_panel.delete_requested.connect(self.delete_current); self.current_panel.change_reason_requested.connect(self.choose_reason)
        self.queue_panel.activate_requested.connect(lambda event_id: self.service.command("activate_queued", event_id)); self.queue_panel.delete_requested.connect(lambda event_id: self.service.command("delete_queued", event_id)); self.queue_panel.move_requested.connect(lambda event_id, delta: self.service.command("move_queued", (event_id, delta))); self.queue_panel.clear_requested.connect(lambda: self.service.command("clear_queue"))
        self.reasons_panel.reason_selected.connect(self.apply_reason)
        self.history_panel.load_requested.connect(lambda filters: self.service.command("load_history", filters)); self.history_panel.delete_requested.connect(lambda record_id: self.service.command("delete_history", record_id)); self.history_panel.export_requested.connect(lambda payload: self.service.command("export_history", payload))
        self.control_panel.settings_requested.connect(self.open_settings); self.control_panel.reset_week_requested.connect(self.reset_week); self.control_panel.promotion_requested.connect(self.reset_promotion); self.control_panel.backup_requested.connect(self.create_backup); self.control_panel.import_requested.connect(self.import_legacy)
        self.control_panel.adjust_statistics_requested.connect(self.adjust_statistics)

    def _default_layout(self) -> None:
        if self._factory_state is not None:
            self._restore_dock_state(self._factory_state)
            self.docks["current"].raise_(); self.docks["queue"].raise_(); self.docks["reasons"].raise_(); self.docks["history"].raise_(); self.docks["control"].raise_()
            return
        self.addDockWidget(Qt.LeftDockWidgetArea, self.docks["current"])
        self.addDockWidget(Qt.RightDockWidgetArea, self.docks["queue"])
        self.splitDockWidget(self.docks["queue"], self.docks["reasons"], Qt.Vertical)
        self.splitDockWidget(self.docks["current"], self.docks["history"], Qt.Vertical)
        self.tabifyDockWidget(self.docks["history"], self.docks["log"])
        self.splitDockWidget(self.docks["reasons"], self.docks["control"], Qt.Vertical)
        self.tabifyDockWidget(self.docks["history"], self.docks["statistics"])
        self.tabifyDockWidget(self.docks["history"], self.docks["fabric"])
        self.docks["current"].raise_(); self.docks["queue"].raise_(); self.docks["reasons"].raise_(); self.docks["history"].raise_(); self.docks["control"].raise_()
        self.resizeDocks([self.docks["current"], self.docks["queue"]], [900, 360], Qt.Horizontal)
        self.resizeDocks([self.docks["current"], self.docks["history"]], [560, 260], Qt.Vertical)
        self._factory_state = self.saveState(2)

    def _restore_dock_state(self, state: QByteArray | bytes) -> bool:
        # Qt can retain a stale tab group when restoreState() is applied over a
        # materially different nested layout. Detaching first makes loading a
        # profile deterministic without recreating any panel or its contents.
        for dock in self.docks.values():
            self.removeDockWidget(dock)
        return self.restoreState(QByteArray(state), 2)

    def _update_workspace(self) -> None:
        any_visible = any(dock.isVisible() for dock in self.docks.values())
        self.workspace.setMaximumSize(1, 1) if any_visible else self.workspace.setMaximumSize(16777215, 16777215)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        settings = file_menu.addAction("Настройки"); settings.triggered.connect(self.open_settings)
        backup = file_menu.addAction("Создать резервную копию"); backup.triggered.connect(self.create_backup)
        file_menu.addSeparator(); close = file_menu.addAction("Выход"); close.triggered.connect(self.close)
        self.view_menu = self.menuBar().addMenu("Вид")
        self.panels_menu = self.view_menu.addMenu("Панели")
        for dock in self.docks.values(): self.panels_menu.addAction(dock.toggleViewAction())
        self.lock_action = self.view_menu.addAction("Заблокировать панели"); self.lock_action.setCheckable(True); self.lock_action.toggled.connect(self.set_locked)
        self.view_menu.addAction("Сохранить раскладку", self.save_layout)
        self.layouts_menu = self.view_menu.addMenu("Загрузить раскладку")
        self.view_menu.addAction("Создать профиль раскладки", self.create_layout)
        self.view_menu.addAction("Переименовать профиль", self.rename_layout)
        self.view_menu.addAction("Удалить профиль", self.delete_layout)
        self.view_menu.addSeparator(); self.view_menu.addAction("Сбросить раскладку", self.reset_layout)
        mode_menu = self.menuBar().addMenu("Режим"); self.mode_group = QActionGroup(self); self.mode_group.setExclusive(True)
        for mode in ("FT", "RW"):
            action = mode_menu.addAction(mode); action.setCheckable(True); action.setData(mode); self.mode_group.addAction(action); action.triggered.connect(lambda _checked=False, value=mode: self.set_manual_mode(value))
        self.mode_group.actions()[0].setChecked(True)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Состояние", self); toolbar.setObjectName("StatusToolbar"); toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        brand = QLabel("  BANHELPER  ", objectName="DockTitleText"); toolbar.addWidget(brand); toolbar.addSeparator()
        self.mode_buttons = {}
        for mode in ("FT", "RW"):
            button = QPushButton(mode); button.setCheckable(True); button.setFixedWidth(48)
            button.clicked.connect(lambda _checked=False, value=mode: self.set_manual_mode(value))
            self.mode_buttons[mode] = button; toolbar.addWidget(button)
        toolbar.addSeparator()
        badge = QWidget(objectName="SuccessBadge"); badge_layout = QHBoxLayout(badge); badge_layout.setContentsMargins(7, 3, 7, 3); badge_layout.setSpacing(4)
        badge_icon = QLabel(); badge_icon.setPixmap(icon("status", "#4fc38b", 11).pixmap(11, 11)); self.fabric_badge = QLabel("FABRIC")
        badge_layout.addWidget(badge_icon); badge_layout.addWidget(self.fabric_badge); toolbar.addWidget(badge)
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred); toolbar.addWidget(spacer)
        self.toolbar_counter = QLabel("ВСЕГО 0   ·   НЕДЕЛЯ 0", objectName="Badge"); toolbar.addWidget(self.toolbar_counter)

    def _install_shortcuts(self) -> None:
        self.shortcuts = {
            "shortcut_focus": QShortcut(QKeySequence("Ctrl+Shift+B"), self, activated=lambda: self.docks["current"].raise_()),
            "shortcut_confirm": QShortcut(QKeySequence("Ctrl+Return"), self, activated=lambda: self.service.command("confirm", self.current_panel.selected_reason) if self.current else None),
            "shortcut_skip": QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=lambda: self.service.command("skip_current") if self.current else None),
            "shortcut_copy": QShortcut(QKeySequence("Ctrl+C"), self, activated=lambda: self.copy_report(self.current_panel.report.text()) if self.current else None),
        }
        self.favorite_shortcuts = [
            QShortcut(QKeySequence(f"Alt+{index + 1}"), self, activated=lambda value=index: self.select_favorite_reason(value))
            for index in range(5)
        ]

    def _connect_service(self) -> None:
        signals = self.service.signals
        signals.initialized.connect(self.initialized); signals.current_changed.connect(self.set_current); signals.queue_changed.connect(self.queue_panel.set_items); signals.history_loaded.connect(self.history_panel.set_records); signals.statistics_changed.connect(self.set_statistics); signals.confirmed.connect(lambda _record: self.history_panel.reload()); signals.settings_changed.connect(self.apply_settings); signals.layout_loaded.connect(self.restore_layout); signals.layouts_changed.connect(self.set_layout_names); signals.log.connect(self.log_panel.append); signals.error.connect(self.show_error)

    def initialized(self, current, queue, stats, settings) -> None:
        self.apply_settings(settings); self.set_current(current); self.queue_panel.set_items(queue); self.set_statistics(stats)
        self.history_panel.reload(); self.active_layout = str(settings.get("active_layout", "Основная")); QTimer.singleShot(50, self._restore_active_layout)
        self.statusBar().showMessage("Готов к получению банов")

    def _restore_active_layout(self) -> None:
        if self.active_layout in self._layout_names:
            self.service.command("load_layout", self.active_layout)
        else:
            self.save_layout()

    def set_current(self, current) -> None:
        self.current = current; self.current_panel.set_current(current)
        if current: self.reasons_panel.set_mode(current.server_mode); self.reasons_panel.select(current.reason, notify=False)
        else: self.reasons_panel.set_mode(self.settings.get("manual_mode", "FT"))

    def set_statistics(self, stats) -> None:
        self.statistics = stats; self.current_panel.set_statistics(stats); self.stats_panel.set_statistics(stats)
        target = f"/{stats.target}" if stats.target else ""
        self.toolbar_counter.setText(f"ВСЕГО {stats.total}   ·   НЕДЕЛЯ {stats.week}{target}")

    def apply_settings(self, settings: dict) -> None:
        self.settings = dict(settings); mode = settings.get("manual_mode", "FT"); self.reasons_panel.set_mode(mode)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet(str(settings.get("theme", "graphite")), float(settings.get("ui_scale", 1.0))))
        logging.getLogger().setLevel(getattr(logging, str(settings.get("log_level", "INFO")).upper(), logging.INFO))
        for action in self.mode_group.actions(): action.setChecked(action.data() == mode)
        for key, shortcut in getattr(self, "shortcuts", {}).items():
            shortcut.setKey(QKeySequence(str(settings.get(key, ""))))
        for index, shortcut in enumerate(getattr(self, "favorite_shortcuts", []), 1):
            shortcut.setKey(QKeySequence(str(settings.get(f"shortcut_reason_{index}", f"Alt+{index}"))))
        for value, button in getattr(self, "mode_buttons", {}).items(): button.setChecked(value == mode)
        for value in ("FT", "RW"):
            self.reasons_panel.set_catalog(
                value,
                list(settings.get(f"reasons_{value.lower()}", [])),
                list(settings.get(f"favorite_reasons_{value.lower()}", [])),
            )

    def set_manual_mode(self, mode: str) -> None:
        self.service.command("save_settings", {"manual_mode": mode})
        if not self.current: self.reasons_panel.set_mode(mode)

    def select_favorite_reason(self, index: int) -> None:
        mode = self.current.server_mode if self.current else str(self.settings.get("manual_mode", "FT"))
        favorites = list(self.settings.get(f"favorite_reasons_{mode.lower()}", []))
        if index >= len(favorites):
            return
        reason = str(favorites[index])
        self.reasons_panel.select(reason)

    def choose_reason(self) -> None:
        reason, ok = QInputDialog.getText(self, "Изменить причину", "Код причины:", text=self.current_panel.selected_reason)
        if ok and reason.strip():
            try: clean = normalize_reason(reason)
            except ValidationError as exc: QMessageBox.warning(self, "Некорректная причина", str(exc)); return
            self.reasons_panel.select(clean)

    def apply_reason(self, reason: str) -> None:
        self.current_panel.set_reason(reason)
        if self.current:
            self.service.command("update_pending_reason", (self.current.event_id, reason))

    def copy_report(self, text: str) -> None:
        if text: QGuiApplication.clipboard().setText(text); self.statusBar().showMessage("Отчёт скопирован", 1800)

    def delete_current(self) -> None:
        if self.current and QMessageBox.question(self, "Удалить карточку", "Удалить текущую карточку без статистики?") == QMessageBox.Yes: self.service.command("delete_current")

    def reset_week(self) -> None:
        if QMessageBox.question(self, "Сброс недели", "Обнулить недельный счётчик?") == QMessageBox.Yes: self.service.command("reset_week")

    def adjust_statistics(self) -> None:
        dialog = StatisticsAdjustmentDialog(self.statistics.total, self.statistics.week, self)
        if dialog.exec():
            total, week = dialog.values()
            if week > total:
                QMessageBox.warning(self, "Некорректная статистика", "За неделю нельзя указать больше, чем всего.")
                return
            self.service.command("set_statistics_counts", (total, week))

    def reset_promotion(self) -> None:
        if QMessageBox.question(self, "Повышение", "Обнулить общий и недельный счётчики? История сохранится.") == QMessageBox.Yes: self.service.command("reset_promotion")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self); dialog.save_requested.connect(lambda values: self.service.command("save_settings", values)); dialog.test_listener_requested.connect(self.test_listener); dialog.open_data_requested.connect(lambda: QDesktopServices.openUrl(self.paths.data_dir.as_uri())); dialog.backup_requested.connect(self.create_backup); dialog.restore_requested.connect(self.restore_backup); dialog.import_requested.connect(self.import_legacy); dialog.reset_requested.connect(self.reset_settings); dialog.reset_layout_requested.connect(self.reset_layout); dialog.exec()

    def test_listener(self) -> None:
        if not self.listener_manager:
            self.statusBar().showMessage("Listener недоступен", 3000)
            return
        self.statusBar().showMessage("Проверяю listener…")
        self.listener_manager.test_async()

    def create_backup(self) -> None:
        configured = str(self.settings.get("backup_directory", "")).strip()
        backup_dir = Path(configured) if configured else self.paths.backups_dir
        target = QFileDialog.getSaveFileName(self, "Резервная копия", str(backup_dir / f"banhelper-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"), "SQLite (*.sqlite3)")[0]
        if target: self.service.command("backup", target)

    def restore_backup(self) -> None:
        source = QFileDialog.getOpenFileName(self, "Восстановить резервную копию", str(self.paths.backups_dir), "SQLite (*.sqlite3)")[0]
        if source and QMessageBox.question(self, "Восстановление", "Заменить текущие данные резервной копией?") == QMessageBox.Yes: self.service.command("restore_backup", source)

    def reset_settings(self) -> None:
        if QMessageBox.question(self, "Сброс настроек", "Вернуть настройки по умолчанию? История не удаляется.") == QMessageBox.Yes: self.service.command("reset_settings")

    def import_legacy(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку старого BanHelper")
        if folder: self.service.command("import_legacy", folder)

    def set_locked(self, locked: bool) -> None:
        self.locked = locked
        for dock in self.docks.values(): dock.set_locked(locked)
        self.layout_timer.start()

    def save_layout(self) -> None:
        if not self.active_layout: return
        self.service.command("save_layout", (self.active_layout, bytes(self.saveGeometry()), bytes(self.saveState(2)), self.locked))

    def restore_layout(self, name: str, geometry: bytes, state: bytes, locked: bool) -> None:
        self.restoreGeometry(QByteArray(geometry)); self._restore_dock_state(state); self.active_layout = name; self.lock_action.setChecked(locked); QTimer.singleShot(0, self.ensure_visible)

    def ensure_visible(self) -> None:
        screens = QGuiApplication.screens(); available = [screen.availableGeometry() for screen in screens]
        if available and not any(area.intersects(self.frameGeometry()) for area in available): self.move(available[0].topLeft() + QPoint(40, 40))
        for dock in self.docks.values():
            if dock.isFloating() and not any(area.intersects(dock.frameGeometry()) for area in available): dock.setFloating(False)

    def set_layout_names(self, names) -> None:
        self._layout_names = list(names); self.layouts_menu.clear()
        for name in self._layout_names: self.layouts_menu.addAction(name, lambda _checked=False, value=name: self.service.command("load_layout", value))

    def create_layout(self) -> None:
        name, ok = QInputDialog.getText(self, "Новый профиль", "Название:")
        if ok and (clean := clean_profile_name(name)): self.active_layout = clean; self.save_layout(); self.service.command("save_settings", {"active_layout": clean})

    def rename_layout(self) -> None:
        name, ok = QInputDialog.getText(self, "Переименовать профиль", "Новое название:", text=self.active_layout)
        if ok and (clean := clean_profile_name(name)) and clean != self.active_layout: old = self.active_layout; self.active_layout = clean; self.service.command("rename_layout", (old, clean))

    def delete_layout(self) -> None:
        if self.active_layout and QMessageBox.question(self, "Удалить профиль", f"Удалить профиль «{self.active_layout}»?") == QMessageBox.Yes:
            deleted = self.active_layout
            self.service.command("delete_layout", deleted); self.active_layout = "Основная"
            self.service.command("save_settings", {"active_layout": self.active_layout})
            if self.active_layout in self._layout_names and deleted != self.active_layout: self.service.command("load_layout", self.active_layout)
            else: self._apply_default_layout()

    def reset_layout(self) -> None:
        if QMessageBox.question(self, "Сбросить раскладку", "Вернуть стандартное расположение панелей?") == QMessageBox.Yes:
            self._apply_default_layout()

    def _apply_default_layout(self) -> None:
        self.lock_action.setChecked(False)
        for dock in self.docks.values(): dock.show(); dock.setFloating(False)
        self._default_layout(); self.save_layout()

    def show_error(self, operation: str, message: str) -> None:
        self.log_panel.append("ERROR", f"{operation}: {message}"); self.statusBar().showMessage(message, 5000)

    def activate(self) -> None:
        if self.isMinimized(): self.showNormal()
        self.show(); self.raise_(); self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.save_layout(); event.accept()
