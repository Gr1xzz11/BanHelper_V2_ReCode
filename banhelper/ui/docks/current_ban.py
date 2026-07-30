from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from banhelper.domain.models import PendingBan, Statistics
from banhelper.domain.reports import build_report
from banhelper.ui.icons import icon


class CurrentBanPanel(QWidget):
    copy_requested = Signal(str)
    confirm_requested = Signal(str)
    skip_requested = Signal()
    delete_requested = Signal()
    change_reason_requested = Signal()

    def __init__(self):
        super().__init__()
        self.current: PendingBan | None = None
        self.statistics = Statistics()
        self.selected_reason = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        top = QHBoxLayout()
        self.state = QLabel("ОЖИДАНИЕ", objectName="Eyebrow")
        self.mode = QLabel("FT", objectName="Badge")
        self.source = QLabel("Fabric не подключён", objectName="Badge")
        top.addWidget(self.state)
        top.addStretch(1)
        top.addWidget(self.source)
        top.addWidget(self.mode)
        root.addLayout(top)
        self.player = QLabel("Ожидание нового бана", objectName="PlayerName")
        self.player.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.player)
        self.meta = QLabel("Событие появится здесь сразу после отправки Fabric-модом", objectName="Eyebrow")
        self.meta.setWordWrap(True)
        root.addWidget(self.meta)
        self.report = QLabel("", objectName="Report")
        self.report.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.report.setMinimumHeight(88)
        root.addWidget(self.report)
        root.addStretch(1)
        actions = QGridLayout()
        actions.setSpacing(7)
        self.copy = QPushButton("Копировать", icon=icon("copy"))
        self.copy.setShortcut("Ctrl+C")
        self.copy.clicked.connect(lambda: self.copy_requested.emit(self.report.text()))
        self.confirm = QPushButton("Подтвердить", icon=icon("check"), objectName="Primary")
        self.confirm.setShortcut("Ctrl+Return")
        self.confirm.clicked.connect(lambda: self.confirm_requested.emit(self.selected_reason))
        self.reason = QPushButton("Изменить причину")
        self.reason.clicked.connect(self.change_reason_requested)
        self.skip = QPushButton("Пропустить")
        self.skip.clicked.connect(self.skip_requested)
        self.delete = QPushButton("Удалить", icon=icon("trash"), objectName="Danger")
        self.delete.clicked.connect(self.delete_requested)
        actions.addWidget(self.copy, 0, 0)
        actions.addWidget(self.confirm, 0, 1)
        actions.addWidget(self.reason, 1, 0)
        actions.addWidget(self.skip, 1, 1)
        actions.addWidget(self.delete, 1, 2)
        root.addLayout(actions)
        self._render()

    def set_current(self, current: PendingBan | None) -> None:
        self.current = current
        self.selected_reason = current.reason if current else ""
        self._render()

    def set_statistics(self, statistics: Statistics) -> None:
        self.statistics = statistics
        self._render()

    def set_reason(self, reason: str) -> None:
        self.selected_reason = reason
        self._render()

    def _render(self) -> None:
        active = self.current is not None
        self.report.setVisible(active)
        for button in (self.copy, self.confirm, self.reason, self.skip, self.delete):
            button.setVisible(active)
        for button in (self.copy, self.confirm):
            button.setEnabled(bool(active and self.selected_reason))
        for button in (self.reason, self.skip, self.delete):
            button.setEnabled(active)
        if not self.current:
            self.state.setText("ОЖИДАНИЕ")
            self.player.setText("Ожидание нового бана")
            self.mode.setText("—")
            self.source.setText("Fabric")
            self.meta.setText("Событие появится здесь сразу после отправки Fabric-модом")
            self.report.setText("")
            return
        item = self.current
        self.state.setText("БАН ОБНАРУЖЕН")
        self.player.setText(item.player)
        self.mode.setText(item.server_mode)
        self.source.setText(item.source.capitalize())
        shown_time = datetime.fromtimestamp(item.received_at).astimezone().strftime("%H:%M:%S")
        reason = self.selected_reason or "не выбрана"
        self.meta.setText(f"Причина: {reason}   ·   Получен: {shown_time}   ·   ID: {item.event_id}")
        self.report.setText(
            build_report(item.player, self.selected_reason, self.statistics.total + 1, self.statistics.week + 1, item.server_mode)
            if self.selected_reason else ""
        )
