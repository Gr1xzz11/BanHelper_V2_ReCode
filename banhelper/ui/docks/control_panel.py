from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from banhelper.ui.icons import icon


class ControlPanel(QWidget):
    settings_requested = Signal()
    reset_week_requested = Signal()
    promotion_requested = Signal()
    backup_requested = Signal()
    import_requested = Signal()
    adjust_statistics_requested = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget(); root = QVBoxLayout(body); root.setContentsMargins(9, 9, 9, 9); root.setSpacing(7)
        scroll.setWidget(body); outer.addWidget(scroll)
        root.addWidget(QLabel("БЫСТРОЕ УПРАВЛЕНИЕ", objectName="Eyebrow"))
        settings = QPushButton("Настройки", icon=icon("settings")); settings.clicked.connect(self.settings_requested)
        adjust = QPushButton("Изменить статистику"); adjust.clicked.connect(self.adjust_statistics_requested)
        week = QPushButton("Сбросить недельный"); week.clicked.connect(self.reset_week_requested)
        promotion = QPushButton("Повышение: сбросить счётчики"); promotion.clicked.connect(self.promotion_requested)
        backup = QPushButton("Создать резервную копию"); backup.clicked.connect(self.backup_requested)
        import_button = QPushButton("Импортировать старые данные"); import_button.clicked.connect(self.import_requested)
        for button in (settings, adjust, week, promotion, backup, import_button): root.addWidget(button)
        root.addStretch(1)
