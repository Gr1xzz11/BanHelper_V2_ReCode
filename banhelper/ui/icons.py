from __future__ import annotations

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer


PATHS = {
    "close": '<path d="M5 5l10 10M15 5L5 15"/>',
    "float": '<rect x="4" y="6" width="10" height="10" rx="1"/><path d="M8 4h8v8"/>',
    "drag": '<path d="M7 5h.1M13 5h.1M7 10h.1M13 10h.1M7 15h.1M13 15h.1" stroke-width="3"/>',
    "copy": '<rect x="7" y="7" width="9" height="10" rx="1"/><path d="M13 7V4H4v10h3"/>',
    "check": '<path d="M4 10l4 4 8-9"/>',
    "trash": '<path d="M5 6h10M8 6V4h4v2M7 8v8h6V8"/>',
    "up": '<path d="M5 12l5-5 5 5"/>',
    "down": '<path d="M5 8l5 5 5-5"/>',
    "search": '<circle cx="9" cy="9" r="5"/><path d="M13 13l4 4"/>',
    "settings": '<circle cx="10" cy="10" r="3"/><path d="M10 3v2M10 15v2M3 10h2M15 10h2M5 5l1.5 1.5M13.5 13.5L15 15M15 5l-1.5 1.5M6.5 13.5L5 15"/>',
    "status": '<circle cx="10" cy="10" r="5"/>',
}


def icon(name: str, color: str = "#aab2c3", size: int = 18) -> QIcon:
    body = PATHS.get(name, PATHS["settings"])
    fill = color if name == "status" else "none"
    stroke = "none" if name == "status" else color
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="{fill}" stroke="{stroke}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill("transparent")
    from PySide6.QtGui import QPainter
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
