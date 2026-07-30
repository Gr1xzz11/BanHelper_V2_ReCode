from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from banhelper.domain.models import ConfirmedBan


class HistoryTableModel(QAbstractTableModel):
    HEADERS = ("Игрок", "Причина", "Режим", "Дата и время", "Отчёт", "Источник", "Event ID")

    def __init__(self):
        super().__init__()
        self.records: list[ConfirmedBan] = []

    def set_records(self, records: list[ConfirmedBan]) -> None:
        self.beginResetModel()
        self.records = list(records)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):  # noqa: N802
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.records):
            return None
        record = self.records[index.row()]
        if role == Qt.UserRole:
            return record
        if role not in (Qt.DisplayRole, Qt.ToolTipRole):
            return None
        values = (
            record.player, record.reason, record.server_mode,
            datetime.fromtimestamp(record.confirmed_at).astimezone().strftime("%d.%m.%Y %H:%M:%S"),
            record.report.replace("\n", " · "), record.source, record.event_id,
        )
        return values[index.column()]
