from __future__ import annotations

from datetime import datetime, time, timedelta

from PySide6.QtCore import QDate, Signal, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget

from banhelper.ui.icons import icon
from banhelper.ui.models.history_model import HistoryTableModel


class HistoryPanel(QWidget):
    load_requested = Signal(object)
    delete_requested = Signal(int)
    export_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self.page = 0
        self.total = 0
        self.sort_by = "confirmed_at"
        self.sort_desc = True
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Поиск по нику…"); self.search.addAction(icon("search"), QLineEdit.LeadingPosition)
        self.mode = QComboBox(); self.mode.addItems(["Все режимы", "FT", "RW"])
        self.reason = QLineEdit(); self.reason.setPlaceholderText("Причина")
        apply = QPushButton("Применить"); apply.clicked.connect(self.reload)
        self.search.returnPressed.connect(self.reload)
        for widget in (self.search, self.mode, self.reason, apply): filters.addWidget(widget)
        root.addLayout(filters)
        date_filters = QHBoxLayout()
        self.date_enabled = QCheckBox("Фильтр по дате")
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-1)); self.date_from.setCalendarPopup(True); self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_to = QDateEdit(QDate.currentDate()); self.date_to.setCalendarPopup(True); self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setEnabled(False); self.date_to.setEnabled(False)
        self.date_enabled.toggled.connect(self.date_from.setEnabled); self.date_enabled.toggled.connect(self.date_to.setEnabled)
        date_filters.addWidget(self.date_enabled); date_filters.addWidget(QLabel("с")); date_filters.addWidget(self.date_from); date_filters.addWidget(QLabel("по")); date_filters.addWidget(self.date_to); date_filters.addStretch(1)
        root.addLayout(date_filters)
        self.model = HistoryTableModel()
        self.table = QTableView(); self.table.setModel(self.model); self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows); self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(True); self.table.verticalHeader().hide(); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSortIndicator(3, Qt.DescendingOrder)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._sort_changed)
        self.table.doubleClicked.connect(self.copy_selected)
        root.addWidget(self.table, 1)
        footer = QHBoxLayout()
        copy = QPushButton("Копировать отчёт", icon=icon("copy")); copy.clicked.connect(self.copy_selected)
        details = QPushButton("Подробности"); details.clicked.connect(self.details)
        export = QPushButton("Экспорт CSV"); export.clicked.connect(self.export)
        delete = QPushButton("Удалить", icon=icon("trash"), objectName="Danger"); delete.clicked.connect(self.delete_selected)
        self.page_label = QLabel("0 записей", objectName="Eyebrow")
        previous = QPushButton("Назад"); previous.clicked.connect(lambda: self.change_page(-1))
        following = QPushButton("Далее"); following.clicked.connect(lambda: self.change_page(1))
        footer.addWidget(copy); footer.addWidget(details); footer.addWidget(export); footer.addWidget(delete); footer.addStretch(1); footer.addWidget(self.page_label); footer.addWidget(previous); footer.addWidget(following)
        root.addLayout(footer)

    def request_payload(self) -> dict:
        mode = self.mode.currentText()
        from_ts = to_ts = 0.0
        if self.date_enabled.isChecked():
            from_ts = datetime.combine(self.date_from.date().toPython(), time.min).astimezone().timestamp()
            to_ts = datetime.combine(self.date_to.date().toPython(), time.max).astimezone().timestamp()
        return {
            "page": self.page, "page_size": 100, "query": self.search.text().strip(),
            "mode": mode if mode in {"FT", "RW"} else "", "reason": self.reason.text().strip().upper(),
            "from_ts": from_ts, "to_ts": to_ts, "sort_by": self.sort_by, "sort_desc": self.sort_desc,
        }

    def _sort_changed(self, column: int, order: Qt.SortOrder) -> None:
        columns = {0: "player", 1: "reason", 2: "server_mode", 3: "confirmed_at", 5: "source", 6: "event_id"}
        self.sort_by = columns.get(column, "confirmed_at")
        self.sort_desc = order == Qt.DescendingOrder
        if self.isVisible():
            self.reload()

    def reload(self) -> None:
        self.page = 0
        self.load_requested.emit(self.request_payload())

    def change_page(self, delta: int) -> None:
        candidate = max(0, self.page + delta)
        if candidate * 100 >= self.total and delta > 0: return
        self.page = candidate
        self.load_requested.emit(self.request_payload())

    def set_records(self, records, total: int, page: int) -> None:
        self.model.set_records(records)
        self.total, self.page = total, page
        first = page * 100 + 1 if records else 0
        last = page * 100 + len(records)
        self.page_label.setText(f"{first}–{last} из {total}")
        self.table.resizeColumnsToContents()

    def selected(self):
        index = self.table.currentIndex()
        return self.model.records[index.row()] if index.isValid() else None

    def copy_selected(self) -> None:
        if record := self.selected(): QGuiApplication.clipboard().setText(record.report)

    def details(self) -> None:
        if record := self.selected():
            QMessageBox.information(self, "Подробности бана", f"{record.report}\n\nИсточник: {record.source}\nEvent ID: {record.event_id}")

    def export(self) -> None:
        target = QFileDialog.getSaveFileName(
            self, "Экспорт истории", f"banhelper-history-{datetime.now():%Y%m%d}.csv", "CSV (*.csv)"
        )[0]
        if not target:
            return
        filters = self.request_payload()
        filters.pop("page", None); filters.pop("page_size", None)
        self.export_requested.emit((target, filters))

    def delete_selected(self) -> None:
        record = self.selected()
        if record and QMessageBox.question(self, "Удалить запись", "Удалить выбранную запись истории? Статистика будет пересчитана.") == QMessageBox.Yes:
            self.delete_requested.emit(record.id)
            self.reload()
