from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QDockWidget, QWidget

from banhelper.ui.title_bar import DockTitleBar


class PanelDock(QDockWidget):
    def __init__(self, title: str, object_name: str, content: QWidget, parent=None):
        super().__init__(title, parent)
        self.setObjectName(object_name)
        self.setWidget(content)
        self.title_bar = DockTitleBar(self, title)
        self.setTitleBarWidget(self.title_bar)
        self.setMinimumSize(220, 120)
        self._limits: tuple[QSize, QSize] | None = None

    def set_locked(self, locked: bool) -> None:
        self.title_bar.set_locked(locked)
        if locked:
            self._limits = (self.minimumSize(), self.maximumSize())
            self.setFeatures(QDockWidget.NoDockWidgetFeatures)
            current = self.size()
            self.setMinimumSize(current)
            self.setMaximumSize(current)
        else:
            self.setFeatures(
                QDockWidget.DockWidgetMovable
                | QDockWidget.DockWidgetFloatable
                | QDockWidget.DockWidgetClosable
            )
            if self._limits:
                self.setMinimumSize(self._limits[0])
                self.setMaximumSize(self._limits[1])
                self._limits = None
