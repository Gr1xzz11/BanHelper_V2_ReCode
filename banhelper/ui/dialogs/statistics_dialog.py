from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout


class StatisticsAdjustmentDialog(QDialog):
    def __init__(self, total: int, week: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Изменить статистику")
        self.setMinimumWidth(390)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Задайте фактические счётчики. История банов не изменится."))
        form = QFormLayout()
        self.total = QSpinBox(); self.total.setRange(0, 10_000_000); self.total.setValue(total)
        self.week = QSpinBox(); self.week.setRange(0, 10_000_000); self.week.setValue(week)
        form.addRow("Всего банов", self.total)
        form.addRow("За текущую неделю", self.week)
        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self) -> tuple[int, int]:
        return self.total.value(), self.week.value()
