from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QFrame, QHBoxLayout, QLabel, QToolButton

from .icons import icon


class DockTitleBar(QFrame):
    def __init__(self, dock: QDockWidget, title: str):
        super().__init__(dock)
        self.dock = dock
        self.setObjectName("DockTitle")
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 0, 4, 0)
        layout.setSpacing(4)
        drag = QLabel()
        drag.setPixmap(icon("drag").pixmap(16, 16))
        drag.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(drag)
        self.label = QLabel(title, objectName="DockTitleText")
        layout.addWidget(self.label, 1)
        self.float_button = QToolButton()
        self.float_button.setIcon(icon("float"))
        self.float_button.setToolTip("Отсоединить или пристыковать панель")
        self.float_button.setAutoRaise(True)
        self.float_button.clicked.connect(lambda: dock.setFloating(not dock.isFloating()))
        layout.addWidget(self.float_button)
        self.close_button = QToolButton()
        self.close_button.setIcon(icon("close"))
        self.close_button.setToolTip("Скрыть панель; вернуть можно через Вид → Панели")
        self.close_button.setAutoRaise(True)
        self.close_button.clicked.connect(dock.hide)
        layout.addWidget(self.close_button)

    def set_locked(self, locked: bool) -> None:
        self.float_button.setVisible(not locked)
        self.close_button.setVisible(not locked)
