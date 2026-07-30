from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QHeaderView, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget

from banhelper.domain.models import PendingBan
from banhelper.ui.icons import icon


class QueuePanel(QWidget):
    activate_requested = Signal(str)
    delete_requested = Signal(str)
    move_requested = Signal(str, int)
    clear_requested = Signal()

    def __init__(self):
        super().__init__()
        self.items: tuple[PendingBan, ...] = ()
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        header = QHBoxLayout()
        self.count = QLabel("0 элементов", objectName="Eyebrow")
        header.addWidget(self.count)
        header.addStretch(1)
        root.addLayout(header)
        self.model = QStandardItemModel(0, 5, self)
        self.model.setHorizontalHeaderLabels(["Игрок", "Причина", "Режим", "Время", "Состояние"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._activate)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        activate = QPushButton("Открыть"); activate.setToolTip("Показать этот бан сейчас; текущий вернётся в очередь"); activate.clicked.connect(self._activate)
        up = QPushButton("Выше", icon=icon("up")); up.clicked.connect(lambda: self._move(-1))
        down = QPushButton("Ниже", icon=icon("down")); down.clicked.connect(lambda: self._move(1))
        delete = QPushButton("Удалить", icon=icon("trash"), objectName="Danger"); delete.clicked.connect(self._delete)
        clear = QPushButton("Очистить"); clear.clicked.connect(self._clear)
        for button in (activate, up, down, delete, clear): actions.addWidget(button)
        root.addLayout(actions)

    def set_items(self, items: tuple[PendingBan, ...]) -> None:
        incoming = tuple(items)
        old_ids = [item.event_id for item in self.items]
        new_ids = [item.event_id for item in incoming]
        if new_ids[:len(old_ids)] == old_ids:
            for item in incoming[len(old_ids):]:
                self._append_row(item)
        elif new_ids != old_ids:
            self.model.removeRows(0, self.model.rowCount())
            for item in incoming:
                self._append_row(item)
        self.items = incoming
        self.count.setText(f"{len(items)} элементов")

    def _append_row(self, item: PendingBan) -> None:
        values = [item.player, item.reason or "—", item.server_mode, datetime.fromtimestamp(item.received_at).astimezone().strftime("%H:%M:%S"), "Ожидает"]
        row = [QStandardItem(value) for value in values]
        for cell in row: cell.setEditable(False)
        row[0].setData(item.event_id, Qt.UserRole)
        self.model.appendRow(row)

    def selected_id(self) -> str:
        row = self.table.currentIndex().row()
        return str(self.model.item(row, 0).data(Qt.UserRole)) if row >= 0 else ""

    def _move(self, delta: int) -> None:
        if event_id := self.selected_id(): self.move_requested.emit(event_id, delta)

    def _activate(self) -> None:
        if event_id := self.selected_id():
            self.activate_requested.emit(event_id)

    def _delete(self) -> None:
        event_id = self.selected_id()
        if event_id and QMessageBox.question(self, "Удалить из очереди", "Удалить выбранный бан без подтверждения?") == QMessageBox.Yes:
            self.delete_requested.emit(event_id)

    def _clear(self) -> None:
        if self.items and QMessageBox.question(self, "Очистить очередь", "Удалить все ожидающие баны?") == QMessageBox.Yes:
            self.clear_requested.emit()
