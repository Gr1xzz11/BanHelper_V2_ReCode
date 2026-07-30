from __future__ import annotations

from PySide6.QtCore import QEvent, Signal, Qt
from PySide6.QtWidgets import QGridLayout, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from banhelper.domain.reasons import Reason, default_reasons
from banhelper.domain.validation import ValidationError, normalize_reason
from banhelper.ui.icons import icon


class ReasonsPanel(QWidget):
    reason_selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.mode = "FT"
        self.selected = ""
        self.buttons: list[tuple[Reason, QPushButton]] = []
        self.button_sets: dict[str, list[tuple[Reason, QPushButton]]] = {"FT": [], "RW": []}
        self.catalogs = {mode: list(default_reasons(mode)) for mode in ("FT", "RW")}
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск причины…")
        self.search.addAction(icon("search"), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        root.addWidget(self.search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.grid = QGridLayout(self.body)
        self.grid.setContentsMargins(0, 4, 0, 0)
        self.grid.setSpacing(6)
        scroll.setWidget(self.body)
        root.addWidget(scroll, 1)
        self.body.installEventFilter(self)
        scroll.viewport().installEventFilter(self)
        self.set_mode("FT")

    def set_mode(self, mode: str) -> None:
        mode = "RW" if str(mode).upper() == "RW" else "FT"
        if self.buttons and self.mode == mode:
            return
        for _reason, button in self.buttons:
            button.hide()
        while self.grid.count():
            self.grid.takeAt(0)
        self.mode = mode
        if not self.button_sets[mode]:
            self.button_sets[mode] = self._build_buttons(mode)
        self.buttons = self.button_sets[mode]
        for _reason, button in self.buttons:
            button.show()
        self._relayout()
        self._filter(self.search.text())

    def _build_buttons(self, mode: str) -> list[tuple[Reason, QPushButton]]:
        result = []
        for reason in self.catalogs[mode]:
            title = reason.title if len(reason.title) <= 20 else reason.title[:19].rstrip() + "…"
            button = QPushButton(f"{reason.code}  {title}")
            button.setObjectName("ReasonButton")
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            button.setCheckable(True)
            button.setToolTip(f"{reason.category} · {reason.title}")
            button.clicked.connect(lambda _checked=False, code=reason.code: self.select(code))
            result.append((reason, button))
        return result

    def set_catalog(self, mode: str, codes: list[str], favorites: list[str]) -> None:
        mode = "RW" if str(mode).upper() == "RW" else "FT"
        known = {reason.code: reason for reason in default_reasons(mode)}
        unique = []
        for code in codes:
            try: clean = normalize_reason(code)
            except ValidationError: continue
            if clean not in unique: unique.append(clean)
        favorite_order = {code: index for index, code in enumerate(favorites)}
        original_order = {code: index for index, code in enumerate(unique)}
        unique.sort(key=lambda code: (0, favorite_order[code]) if code in favorite_order else (1, original_order[code]))
        catalog = [known.get(code, Reason(code, "Пользовательская причина", "Другое")) for code in unique]
        if catalog == self.catalogs[mode]:
            return
        self.catalogs[mode] = catalog
        for _reason, button in self.button_sets[mode]:
            button.hide(); button.setParent(None); button.deleteLater()
        self.button_sets[mode] = []
        if self.mode == mode:
            self.buttons = []
            self.mode = ""
            self.set_mode(mode)

    def select(self, code: str, notify: bool = True) -> None:
        self.selected = code
        for reason, button in self.buttons:
            button.setChecked(reason.code == code)
        if notify:
            self.reason_selected.emit(code)

    def _filter(self, text: str) -> None:
        query = text.strip().casefold()
        for reason, button in self.buttons:
            button.setVisible(not query or query in f"{reason.code} {reason.title} {reason.category}".casefold())

    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == QEvent.Resize:
            self._relayout()
        return super().eventFilter(watched, event)

    def _relayout(self) -> None:
        width = max(220, self.body.width())
        columns = max(2, min(4, width // 170))
        while self.grid.count():
            self.grid.takeAt(0)
        for column in range(4):
            self.grid.setColumnStretch(column, 0)
            self.grid.setColumnMinimumWidth(column, 0)
        for index, (_reason, button) in enumerate(self.buttons):
            self.grid.addWidget(button, index // columns, index % columns)
        for column in range(columns):
            self.grid.setColumnStretch(column, 1)
