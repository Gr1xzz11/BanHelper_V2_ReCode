from __future__ import annotations

from collections import deque
from datetime import datetime

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class EventLogPanel(QWidget):
    def __init__(self, limit: int = 500):
        super().__init__(); self.lines = deque(maxlen=limit); self.level = "INFO"
        root = QVBoxLayout(self); root.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout(); self.filter = QComboBox(); self.filter.addItems(["INFO", "WARNING", "ERROR"]); self.filter.currentTextChanged.connect(self._render)
        clear = QPushButton("Очистить экран"); clear.clicked.connect(self.clear)
        top.addWidget(self.filter); top.addStretch(1); top.addWidget(clear); root.addLayout(top)
        self.output = QPlainTextEdit(); self.output.setReadOnly(True); root.addWidget(self.output, 1)

    def append(self, level: str, message: str) -> None:
        self.lines.append((level, datetime.now().strftime("%H:%M:%S"), message))
        self._render()

    def clear(self) -> None:
        self.lines.clear(); self.output.clear()

    def _render(self, *_args) -> None:
        threshold = {"INFO": 0, "WARNING": 1, "ERROR": 2}[self.filter.currentText()]
        rank = {"INFO": 0, "WARNING": 1, "ERROR": 2}
        self.output.setPlainText("\n".join(f"{stamp}  {level:<7}  {message}" for level, stamp, message in self.lines if rank.get(level, 0) >= threshold))
        bar = self.output.verticalScrollBar(); bar.setValue(bar.maximum())
