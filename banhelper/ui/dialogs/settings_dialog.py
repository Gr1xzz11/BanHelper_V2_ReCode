from __future__ import annotations

import secrets

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)


class SettingsDialog(QDialog):
    save_requested = Signal(object)
    test_listener_requested = Signal()
    open_data_requested = Signal()
    backup_requested = Signal()
    restore_requested = Signal()
    import_requested = Signal()
    reset_requested = Signal()
    reset_layout_requested = Signal()

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent); self.settings = dict(settings)
        self.setWindowTitle("Настройки BanHelper"); self.resize(620, 500)
        root = QVBoxLayout(self); tabs = QTabWidget(); root.addWidget(tabs, 1)
        general = QWidget(); form = QFormLayout(general)
        self.admin = QLineEdit(str(settings.get("admin_name", "")))
        self.target = QSpinBox(); self.target.setRange(0, 100000); self.target.setValue(int(settings.get("weekly_target", 0)))
        self.mode = QComboBox(); self.mode.addItems(["FT", "RW"]); self.mode.setCurrentText(str(settings.get("manual_mode", "FT")))
        self.theme = QComboBox(); self.theme.addItem("Графитовая", "graphite"); self.theme.addItem("Высокий контраст", "high_contrast"); self.theme.setCurrentIndex(max(0, self.theme.findData(str(settings.get("theme", "graphite")))))
        self.scale = QComboBox(); self.scale.addItems(["0.9", "1.0", "1.1", "1.25", "1.5"]); self.scale.setCurrentText(str(settings.get("ui_scale", 1.0)))
        self.level = QComboBox(); self.level.addItems(["INFO", "WARNING", "ERROR", "DEBUG"]); self.level.setCurrentText(str(settings.get("log_level", "INFO")))
        form.addRow("Ник администратора", self.admin); form.addRow("Недельная цель", self.target); form.addRow("Ручной режим", self.mode); form.addRow("Тема", self.theme); form.addRow("Масштаб", self.scale); form.addRow("Уровень логирования", self.level)
        tabs.addTab(general, "Основные")
        listener = QWidget(); listener_form = QFormLayout(listener)
        self.host = QLineEdit(str(settings.get("listener_host", "127.0.0.1"))); self.host.setReadOnly(True)
        self.port = QSpinBox(); self.port.setRange(1024, 65535); self.port.setValue(int(settings.get("listener_port", 8765)))
        self.token = QLineEdit(str(settings.get("listener_token", ""))); self.token.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.autostart = QCheckBox("Запускать listener вместе с BanHelper"); self.autostart.setChecked(bool(settings.get("listener_autostart", True)))
        generate = QPushButton("Сгенерировать новый токен"); generate.clicked.connect(lambda: self.token.setText(secrets.token_urlsafe(32)))
        test = QPushButton("Проверить listener"); test.clicked.connect(self.test_listener_requested)
        listener_form.addRow("Адрес", self.host); listener_form.addRow("Порт", self.port); listener_form.addRow("Токен", self.token); listener_form.addRow(self.autostart); listener_form.addRow(generate); listener_form.addRow(test)
        tabs.addTab(listener, "Fabric listener")
        reasons = QWidget(); reasons_form = QFormLayout(reasons)
        self.reasons_ft = QPlainTextEdit("\n".join(settings.get("reasons_ft", []))); self.reasons_ft.setPlaceholderText("Один код причины на строку")
        self.reasons_rw = QPlainTextEdit("\n".join(settings.get("reasons_rw", [])))
        self.favorites_ft = QLineEdit(", ".join(settings.get("favorite_reasons_ft", [])))
        self.favorites_rw = QLineEdit(", ".join(settings.get("favorite_reasons_rw", [])))
        reasons_form.addRow("Причины FT", self.reasons_ft); reasons_form.addRow("Избранные FT", self.favorites_ft); reasons_form.addRow("Причины RW", self.reasons_rw); reasons_form.addRow("Избранные RW", self.favorites_rw)
        tabs.addTab(reasons, "Причины")
        hotkeys = QWidget(); hotkeys_form = QFormLayout(hotkeys)
        self.shortcut_copy = QLineEdit(str(settings.get("shortcut_copy", "Ctrl+C"))); self.shortcut_confirm = QLineEdit(str(settings.get("shortcut_confirm", "Ctrl+Return"))); self.shortcut_skip = QLineEdit(str(settings.get("shortcut_skip", "Ctrl+Shift+S"))); self.shortcut_focus = QLineEdit(str(settings.get("shortcut_focus", "Ctrl+Shift+B")))
        hotkeys_form.addRow("Копировать", self.shortcut_copy); hotkeys_form.addRow("Подтвердить", self.shortcut_confirm); hotkeys_form.addRow("Пропустить", self.shortcut_skip); hotkeys_form.addRow("Фокус на бане", self.shortcut_focus)
        self.favorite_shortcuts = []
        for index in range(1, 6):
            editor = QLineEdit(str(settings.get(f"shortcut_reason_{index}", f"Alt+{index}")))
            self.favorite_shortcuts.append(editor); hotkeys_form.addRow(f"Избранная причина {index}", editor)
        tabs.addTab(hotkeys, "Горячие клавиши")
        storage = QWidget(); storage_layout = QVBoxLayout(storage)
        storage_layout.addWidget(QLabel("История, очередь, настройки и раскладки находятся в одной SQLite-базе."))
        backup_row = QWidget(); backup_layout = QHBoxLayout(backup_row); backup_layout.setContentsMargins(0, 0, 0, 0)
        self.backup_directory = QLineEdit(str(settings.get("backup_directory", ""))); self.backup_directory.setPlaceholderText("Папка BanHelper/backups по умолчанию")
        choose_backup = QPushButton("Выбрать…"); choose_backup.clicked.connect(self._choose_backup_directory)
        backup_layout.addWidget(self.backup_directory, 1); backup_layout.addWidget(choose_backup)
        storage_layout.addWidget(QLabel("Директория резервных копий", objectName="Eyebrow")); storage_layout.addWidget(backup_row)
        open_data = QPushButton("Открыть папку данных"); open_data.clicked.connect(self.open_data_requested)
        backup = QPushButton("Создать резервную копию"); backup.clicked.connect(self.backup_requested)
        restore = QPushButton("Восстановить резервную копию"); restore.clicked.connect(self.restore_requested)
        legacy = QPushButton("Импортировать старые данные"); legacy.clicked.connect(self.import_requested)
        reset = QPushButton("Сбросить настройки", objectName="Danger"); reset.clicked.connect(self.reset_requested)
        reset_layout = QPushButton("Сбросить раскладку", objectName="Danger"); reset_layout.clicked.connect(self.reset_layout_requested)
        for button in (open_data, backup, restore, legacy, reset_layout, reset): storage_layout.addWidget(button)
        storage_layout.addStretch(1); tabs.addTab(storage, "Данные")
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Сохранить"); buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self._save); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _save(self) -> None:
        values = {
            "admin_name": self.admin.text().strip(), "weekly_target": self.target.value(),
            "manual_mode": self.mode.currentText(), "ui_scale": float(self.scale.currentText()),
            "theme": self.theme.currentData(), "log_level": self.level.currentText(), "listener_host": "127.0.0.1",
            "listener_port": self.port.value(), "listener_token": self.token.text().strip(),
            "listener_autostart": self.autostart.isChecked(), "backup_directory": self.backup_directory.text().strip(),
            "reasons_ft": self._lines(self.reasons_ft), "reasons_rw": self._lines(self.reasons_rw),
            "favorite_reasons_ft": self._csv(self.favorites_ft.text()), "favorite_reasons_rw": self._csv(self.favorites_rw.text()),
            "shortcut_copy": self.shortcut_copy.text().strip(), "shortcut_confirm": self.shortcut_confirm.text().strip(),
            "shortcut_skip": self.shortcut_skip.text().strip(), "shortcut_focus": self.shortcut_focus.text().strip(),
        }
        for index, editor in enumerate(self.favorite_shortcuts, 1):
            values[f"shortcut_reason_{index}"] = editor.text().strip()
        self.save_requested.emit(values); self.accept()

    def _choose_backup_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Директория резервных копий", self.backup_directory.text())
        if selected:
            self.backup_directory.setText(selected)

    @staticmethod
    def _lines(editor: QPlainTextEdit) -> list[str]:
        return list(dict.fromkeys(line.strip().upper() for line in editor.toPlainText().splitlines() if line.strip()))

    @staticmethod
    def _csv(value: str) -> list[str]:
        return list(dict.fromkeys(item.strip().upper() for item in value.split(",") if item.strip()))
