from __future__ import annotations

PALETTE = {
    "bg": "#0d0f14", "surface": "#131720", "surface2": "#191e29",
    "surface3": "#212736", "border": "#2a3242", "border_hot": "#6553c7",
    "text": "#edf0f6", "muted": "#929cad", "accent": "#8067f2",
    "accent_hover": "#927cff", "danger": "#e45d68", "success": "#4fc38b",
    "warning": "#e2ae5c",
}

STYLESHEET = f"""
* {{ font-family: "Inter", "Segoe UI", sans-serif; font-size: 13px; }}
QWidget {{ color: {PALETTE['text']}; background-color: transparent; }}
QMainWindow, QDialog, QWidget#AppRoot, QWidget#Workspace {{ background-color: {PALETTE['bg']}; color: {PALETTE['text']}; }}
QDialog QWidget {{ color: {PALETTE['text']}; }}
QLabel {{ color: {PALETTE['text']}; }}
QMenuBar {{ background: {PALETTE['surface']}; color: {PALETTE['text']}; border-bottom: 1px solid {PALETTE['border']}; }}
QMenuBar::item {{ padding: 7px 11px; }} QMenuBar::item:selected {{ background: {PALETTE['surface3']}; }}
QMenu {{ background: {PALETTE['surface2']}; color: {PALETTE['text']}; border: 1px solid {PALETTE['border']}; padding: 5px; }}
QMenu::item {{ padding: 7px 28px 7px 10px; border-radius: 4px; }} QMenu::item:selected {{ background: {PALETTE['surface3']}; }}
QToolBar {{ background: {PALETTE['surface']}; border: 0; border-bottom: 1px solid {PALETTE['border']}; padding: 5px 8px; spacing: 6px; }}
QStatusBar {{ background: {PALETTE['surface']}; color: {PALETTE['muted']}; border-top: 1px solid {PALETTE['border']}; }}
QDockWidget {{ color: {PALETTE['text']}; border: 1px solid {PALETTE['border']}; }}
QDockWidget > QWidget {{ background: {PALETTE['surface']}; }}
QFrame#DockTitle {{ background: {PALETTE['surface2']}; border-bottom: 1px solid {PALETTE['border']}; }}
QLabel#DockTitleText {{ font-weight: 700; color: {PALETTE['text']}; }}
QLabel#Eyebrow {{ color: {PALETTE['muted']}; font-size: 11px; font-weight: 700; }}
QLabel#PlayerName {{ color: {PALETTE['text']}; font-size: 27px; font-weight: 750; }}
QLabel#Report {{ background: #0b0d12; border: 1px solid {PALETTE['border']}; border-radius: 6px; padding: 12px; font-family: "JetBrains Mono", monospace; font-size: 16px; }}
QLabel#Badge {{ background: {PALETTE['surface3']}; color: {PALETTE['muted']}; padding: 3px 7px; border-radius: 4px; }}
QWidget#SuccessBadge {{ background: #173529; border-radius: 4px; }}
QWidget#SuccessBadge QLabel {{ color: {PALETTE['success']}; background: transparent; }}
QPushButton, QToolButton {{ background: {PALETTE['surface3']}; color: {PALETTE['text']}; border: 1px solid {PALETTE['border']}; border-radius: 5px; padding: 7px 11px; }}
QPushButton:hover, QToolButton:hover {{ background: #2a3142; border-color: #424d64; }}
QPushButton:pressed, QToolButton:pressed {{ background: #181d28; }}
QPushButton:focus {{ border-color: {PALETTE['accent']}; }}
QPushButton:disabled, QToolButton:disabled {{ color: #626a79; background: #171a21; border-color: #222733; }}
QPushButton#Primary {{ background: {PALETTE['accent']}; border-color: {PALETTE['accent']}; color: white; font-weight: 700; }}
QPushButton#Primary:hover {{ background: {PALETTE['accent_hover']}; }}
QPushButton#Danger {{ color: #ff9aa3; }} QPushButton#Danger:hover {{ background: #3a2028; border-color: {PALETTE['danger']}; }}
QPushButton#ReasonButton {{ padding: 7px 9px; text-align: left; }}
QPushButton#ReasonButton:checked {{ background: {PALETTE['accent']}; border-color: {PALETTE['accent_hover']}; color: white; }}
QLineEdit, QSpinBox, QComboBox, QDateEdit {{ background: #0e1118; color: {PALETTE['text']}; border: 1px solid {PALETTE['border']}; border-radius: 5px; padding: 7px; selection-background-color: {PALETTE['accent']}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDateEdit:focus {{ border-color: {PALETTE['accent']}; }}
QTableView, QListView, QListWidget, QPlainTextEdit {{ background: #0f1219; alternate-background-color: #131822; color: {PALETTE['text']}; border: 0; gridline-color: {PALETTE['border']}; selection-background-color: #493d88; selection-color: white; }}
QHeaderView::section {{ background: {PALETTE['surface2']}; color: {PALETTE['muted']}; border: 0; border-right: 1px solid {PALETTE['border']}; border-bottom: 1px solid {PALETTE['border']}; padding: 7px; font-weight: 700; }}
QTabWidget::pane {{ background: {PALETTE['bg']}; border: 1px solid {PALETTE['border']}; }}
QTabBar::tab {{ background: {PALETTE['surface2']}; color: {PALETTE['muted']}; padding: 7px 13px; border: 1px solid {PALETTE['border']}; }}
QTabBar::tab:selected {{ color: {PALETTE['text']}; border-bottom: 2px solid {PALETTE['accent']}; }}
QScrollBar:vertical {{ background: #0d1016; width: 10px; margin: 0; }} QScrollBar::handle:vertical {{ background: #343c4e; min-height: 30px; border-radius: 4px; }}
QScrollBar:horizontal {{ background: #0d1016; height: 10px; margin: 0; }} QScrollBar::handle:horizontal {{ background: #343c4e; min-width: 30px; border-radius: 4px; }}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: #465169; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: transparent; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QCheckBox {{ color: {PALETTE['text']}; spacing: 7px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {PALETTE['border']}; border-radius: 3px; background: #0e1118; }}
QCheckBox::indicator:checked {{ background: {PALETTE['accent']}; border-color: {PALETTE['accent_hover']}; }}
QProgressBar {{ background: #0d1016; border: 1px solid {PALETTE['border']}; border-radius: 4px; text-align: center; }}
QProgressBar::chunk {{ background: {PALETTE['accent']}; border-radius: 3px; }}
QToolTip {{ background: {PALETTE['surface3']}; color: {PALETTE['text']}; border: 1px solid {PALETTE['border']}; padding: 5px; }}
"""


def build_stylesheet(theme: str = "graphite", scale: float = 1.0) -> str:
    """Return a complete Qt stylesheet; applying it never touches disk."""
    safe_scale = max(0.9, min(float(scale), 1.5))
    result = STYLESHEET.replace("font-size: 13px", f"font-size: {round(13 * safe_scale)}px", 1)
    if theme == "high_contrast":
        result += f"""
        QWidget {{ color: #ffffff; }}
        QMainWindow, QDialog, QWidget#Workspace {{ background-color: #07090d; }}
        QDockWidget, QLineEdit, QSpinBox, QComboBox, QDateEdit, QTabWidget::pane {{ border-color: #566178; }}
        QLabel#Eyebrow, QLabel#Badge {{ color: #c4cad6; }}
        """
    return result
