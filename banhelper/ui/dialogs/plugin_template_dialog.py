from __future__ import annotations

import re

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout


class PluginTemplateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создать шаблон плагина")
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("BanHelper создаст исходники и скрипт сборки .bhplugin."))
        form = QFormLayout()
        self.plugin_id = QLineEdit(); self.plugin_id.setPlaceholderText("my-plugin")
        self.name = QLineEdit(); self.name.setPlaceholderText("Мой плагин")
        self.author = QLineEdit()
        self.description = QLineEdit()
        form.addRow("ID", self.plugin_id); form.addRow("Название", self.name)
        form.addRow("Автор", self.author); form.addRow("Описание", self.description)
        root.addLayout(form)
        self.error = QLabel("", objectName="Eyebrow"); root.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Create | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Create).setText("Создать")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self._validate); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", self.plugin_id.text().strip()):
            self.error.setText("ID: 3–64 символа, a-z, 0-9, дефис или подчёркивание.")
            return
        if not self.name.text().strip():
            self.error.setText("Укажите название.")
            return
        self.accept()

    def values(self) -> dict[str, str]:
        return {
            "id": self.plugin_id.text().strip(),
            "name": self.name.text().strip(),
            "author": self.author.text().strip(),
            "description": self.description.text().strip(),
        }
