from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from banhelper.ui.icons import icon


class FabricStatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(10, 10, 10, 10)
        status_row = QHBoxLayout(); status_row.setSpacing(5)
        self.state_icon = QLabel(); self.state_icon.setPixmap(icon("status", "#e2ae5c", 12).pixmap(12, 12))
        self.state = QLabel("Listener запускается", objectName="Eyebrow")
        status_row.addWidget(self.state_icon); status_row.addWidget(self.state); status_row.addStretch(1); root.addLayout(status_row)
        grid = QGridLayout()
        self.address = QLabel("—"); self.last = QLabel("—"); self.received = QLabel("0"); self.rejected = QLabel("0")
        for row, (title, value) in enumerate((("Адрес", self.address), ("Последнее событие", self.last), ("Принято", self.received), ("Отклонено", self.rejected))):
            grid.addWidget(QLabel(title, objectName="Eyebrow"), row, 0); grid.addWidget(value, row, 1)
        root.addLayout(grid); root.addStretch(1)

    def set_running(self, host: str, port: int) -> None:
        self.state.setText("Listener работает"); self.state.setStyleSheet("color: #4fc38b")
        self.state_icon.setPixmap(icon("status", "#4fc38b", 12).pixmap(12, 12))
        self.address.setText(f"{host}:{port}")

    def set_error(self, message: str) -> None:
        self.state.setText(f"Ошибка: {message}"); self.state.setStyleSheet("color: #e45d68")
        self.state_icon.setPixmap(icon("status", "#e45d68", 12).pixmap(12, 12))

    def update_metrics(self, received: int, rejected: int, last_event_at: float) -> None:
        self.received.setText(str(received)); self.rejected.setText(str(rejected))
        self.last.setText(datetime.fromtimestamp(last_event_at).astimezone().strftime("%H:%M:%S") if last_event_at else "—")
