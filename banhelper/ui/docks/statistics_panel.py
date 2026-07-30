from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QScrollArea, QVBoxLayout, QWidget

from banhelper.domain.models import Statistics


class StatisticsPanel(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget(); root = QVBoxLayout(body); root.setContentsMargins(10, 10, 10, 10)
        scroll.setWidget(body); outer.addWidget(scroll)
        grid = QGridLayout(); grid.setSpacing(8)
        self.values = {}
        for index, (key, title) in enumerate((("total", "ВСЕГО"), ("week", "НЕДЕЛЯ"), ("ft", "FT"), ("rw", "RW"))):
            box = QWidget(); layout = QVBoxLayout(box); layout.setContentsMargins(8, 6, 8, 6)
            caption = QLabel(title, objectName="Eyebrow"); value = QLabel("0", objectName="PlayerName")
            value.setStyleSheet("font-size: 20px")
            layout.addWidget(caption); layout.addWidget(value); self.values[key] = value
            grid.addWidget(box, index // 2, index % 2)
        root.addLayout(grid)
        self.progress_label = QLabel("Недельная цель не задана", objectName="Eyebrow")
        self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setValue(0)
        self.top = QLabel("Популярные причины: —"); self.top.setWordWrap(True)
        self.days = QLabel("Последние дни: —"); self.days.setWordWrap(True)
        root.addWidget(self.progress_label); root.addWidget(self.progress); root.addWidget(self.top); root.addWidget(self.days); root.addStretch(1)

    def set_statistics(self, stats: Statistics) -> None:
        for key in self.values: self.values[key].setText(str(getattr(stats, key)))
        self.progress.setValue(stats.percent)
        self.progress_label.setText(f"Недельная цель: {stats.week}/{stats.target} · {stats.percent}%" if stats.target else "Недельная цель не задана")
        self.top.setText("Популярные причины: " + (" · ".join(f"{code}: {count}" for code, count in stats.top_reasons) or "—"))
        self.days.setText("Последние дни: " + (" · ".join(f"{day}: {count}" for day, count in stats.recent_days) or "—"))
