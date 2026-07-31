from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMainWindow, QMessageBox

from banhelper.plugins import PluginContext, PluginError, PluginManager


class PluginMenuController(QObject):
    """Attach the complete plugin UI to an existing BanHelper window."""

    def __init__(self, window: QMainWindow, manager: PluginManager):
        super().__init__(window)
        self.window = window
        self.manager = manager
        self.menu = window.menuBar().addMenu("Плагины")
        self.menu.addAction("Установить .bhplugin…", self.install_plugin)
        self.menu.addAction("Создать шаблон плагина…", self.create_template)
        self.menu.addAction("Открыть папку плагинов", self.open_plugins_directory)
        self.menu.addAction("Перезагрузить плагины", self.reload_plugins)
        self.menu.addSeparator()
        self.installed_menu = self.menu.addMenu("Установленные")
        self.commands_menu = self.menu.addMenu("Команды плагинов")
        self.manager.set_host_callbacks(
            show_status=lambda message, timeout: self.window.statusBar().showMessage(message, timeout),
            command=lambda name, payload: self.window.service.command(name, payload),
        )
        self.manager.load_enabled()
        self.refresh()

    def refresh(self) -> None:
        self.manager.discover()
        self.installed_menu.clear()
        self.commands_menu.clear()
        records = self.manager.records()
        if not records:
            empty = self.installed_menu.addAction("Плагины не установлены")
            empty.setEnabled(False)
            empty_commands = self.commands_menu.addAction("Нет активных команд")
            empty_commands.setEnabled(False)
            return
        command_count = 0
        for record in records:
            info = record.metadata
            plugin_menu = self.installed_menu.addMenu(f"{info.name}  {info.version}")
            identity = plugin_menu.addAction(info.plugin_id)
            identity.setEnabled(False)
            if info.author:
                author = plugin_menu.addAction(f"Автор: {info.author}")
                author.setEnabled(False)
            if info.description:
                description = plugin_menu.addAction(info.description)
                description.setEnabled(False)
            if record.error:
                error = plugin_menu.addAction(f"Ошибка: {record.error}")
                error.setEnabled(False)
            plugin_menu.addSeparator()
            enabled_action = plugin_menu.addAction("Включён")
            enabled_action.setCheckable(True)
            enabled_action.setChecked(record.enabled)
            enabled_action.toggled.connect(
                lambda enabled, plugin_id=info.plugin_id: self.toggle_plugin(plugin_id, enabled)
            )
            remove_action = plugin_menu.addAction("Удалить")
            remove_action.setEnabled(not record.builtin)
            remove_action.triggered.connect(
                lambda _checked=False, plugin_id=info.plugin_id: self.remove_plugin(plugin_id)
            )
            actions = self.manager.actions_for(info.plugin_id)
            if actions:
                submenu = self.commands_menu.addMenu(info.name)
                for action_id, title in actions:
                    submenu.addAction(
                        title,
                        lambda _checked=False, qualified=action_id: self.invoke_action(qualified),
                    )
                    command_count += 1
        if command_count == 0:
            empty_commands = self.commands_menu.addAction("Нет активных команд")
            empty_commands.setEnabled(False)

    def toggle_plugin(self, plugin_id: str, enabled: bool) -> None:
        try:
            record = self.manager.set_enabled(plugin_id, enabled)
            if record.error:
                QMessageBox.warning(
                    self.window,
                    "Плагин не запущен",
                    f"{record.metadata.name}:\n{record.error}",
                )
            else:
                state = "включён" if enabled else "выключен"
                self.window.statusBar().showMessage(f"{record.metadata.name}: {state}", 3000)
        except PluginError as exc:
            QMessageBox.warning(self.window, "Ошибка плагина", str(exc))
        self.refresh()

    def reload_plugins(self) -> None:
        records = self.manager.reload_all()
        self.refresh()
        failed = [record for record in records if record.enabled and record.error]
        if failed:
            QMessageBox.warning(
                self.window,
                "Некоторые плагины не запущены",
                "\n".join(f"{record.metadata.name}: {record.error}" for record in failed),
            )
        else:
            self.window.statusBar().showMessage("Плагины перезагружены", 3000)

    def invoke_action(self, action_id: str) -> None:
        try:
            self.manager.invoke(action_id, {})
        except Exception as exc:
            QMessageBox.warning(self.window, "Ошибка команды плагина", str(exc))

    def install_plugin(self) -> None:
        source = QFileDialog.getOpenFileName(
            self.window,
            "Установить плагин",
            str(Path.home()),
            "BanHelper plugin (*.bhplugin)",
        )[0]
        if not source:
            return
        warning = (
            "Плагин содержит Python-код и работает с правами BanHelper.\n"
            "Устанавливайте только файлы от авторов, которым доверяете.\n\nПродолжить?"
        )
        if QMessageBox.question(self.window, "Установка плагина", warning) != QMessageBox.Yes:
            return
        try:
            try:
                record = self.manager.install(Path(source))
            except PluginError as exc:
                if "уже установлен" not in str(exc):
                    raise
                if QMessageBox.question(
                    self.window,
                    "Обновить плагин?",
                    f"{exc}\nЗаменить установленную версию?",
                ) != QMessageBox.Yes:
                    return
                record = self.manager.install(Path(source), replace_existing=True)
            self.refresh()
            if QMessageBox.question(
                self.window,
                "Плагин установлен",
                f"«{record.metadata.name}» {record.metadata.version} установлен.\nВключить сейчас?",
            ) == QMessageBox.Yes:
                self.toggle_plugin(record.metadata.plugin_id, True)
        except (PluginError, OSError, ValueError) as exc:
            QMessageBox.critical(self.window, "Не удалось установить плагин", str(exc))

    def remove_plugin(self, plugin_id: str) -> None:
        record = next((item for item in self.manager.records() if item.metadata.plugin_id == plugin_id), None)
        if record is None:
            return
        if QMessageBox.question(
            self.window,
            "Удалить плагин",
            f"Удалить «{record.metadata.name}»? Данные плагина сохранятся.",
        ) != QMessageBox.Yes:
            return
        try:
            self.manager.uninstall(plugin_id)
            self.window.statusBar().showMessage(f"{record.metadata.name}: удалён", 3000)
        except PluginError as exc:
            QMessageBox.warning(self.window, "Не удалось удалить плагин", str(exc))
        self.refresh()

    def open_plugins_directory(self) -> None:
        self.manager.plugins_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.plugins_dir)))

    def create_template(self) -> None:
        plugin_id, ok = QInputDialog.getText(
            self.window,
            "Создать шаблон плагина",
            "ID плагина (a-z, 0-9, точка, дефис, подчёркивание):",
        )
        if not ok:
            return
        plugin_id = plugin_id.strip().lower()
        if not plugin_id or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in plugin_id
        ):
            QMessageBox.warning(self.window, "Некорректный ID", "Допустимы a-z, 0-9, точка, дефис и подчёркивание.")
            return
        name, ok = QInputDialog.getText(self.window, "Создать шаблон плагина", "Название плагина:")
        if not ok or not name.strip():
            return
        author, ok = QInputDialog.getText(self.window, "Создать шаблон плагина", "Автор:")
        if not ok:
            return
        parent = QFileDialog.getExistingDirectory(self.window, "Куда сохранить исходники плагина")
        if not parent:
            return
        target = Path(parent) / plugin_id
        if target.exists():
            QMessageBox.warning(self.window, "Папка уже существует", str(target))
            return
        try:
            target.mkdir(parents=True)
            manifest = {
                "id": plugin_id,
                "name": name.strip(),
                "version": "0.1.0",
                "api_version": 1,
                "author": author.strip(),
                "description": "",
                "entrypoint": "plugin.py:Plugin",
                "settings": {
                    "fields": [
                        {
                            "key": "example",
                            "label": "Пример настройки",
                            "type": "text",
                            "default": "",
                        }
                    ]
                },
            }
            (target / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (target / "plugin.py").write_text(
                "class Plugin:\n"
                "    def activate(self, context):\n"
                "        self.context = context\n"
                "        context.log('INFO', 'Плагин запущен')\n"
                "        context.register_action(\n"
                "            'check',\n"
                "            lambda payload: context.show_status('Плагин работает'),\n"
                "            'Проверить плагин',\n"
                "        )\n\n"
                "    def deactivate(self):\n"
                "        self.context.log('INFO', 'Плагин остановлен')\n",
                encoding="utf-8",
            )
            (target / "build.py").write_text(
                "from pathlib import Path\n"
                "import zipfile\n\n"
                "root = Path(__file__).resolve().parent\n"
                "output = root.parent / f'{root.name}.bhplugin'\n"
                "with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:\n"
                "    for path in root.rglob('*'):\n"
                "        if path.is_file() and path.name != 'build.py' and '__pycache__' not in path.parts:\n"
                "            archive.write(path, path.relative_to(root).as_posix())\n"
                "print(output)\n",
                encoding="utf-8",
            )
            (target / "README.md").write_text(
                f"# {name.strip()}\n\n"
                "Измените `plugin.py`, затем выполните `python build.py`.\n"
                "Полученный `.bhplugin` устанавливается через меню «Плагины» BanHelper.\n",
                encoding="utf-8",
            )
            QMessageBox.information(
                self.window,
                "Шаблон создан",
                f"Исходники созданы:\n{target}\n\nСборка:\npython build.py",
            )
        except OSError as exc:
            QMessageBox.critical(self.window, "Не удалось создать шаблон", str(exc))


def attach_plugin_menu(window: QMainWindow, manager: PluginManager) -> PluginMenuController:
    controller = PluginMenuController(window, manager)
    window.plugin_menu_controller = controller  # type: ignore[attr-defined]
    window.plugin_manager = manager  # type: ignore[attr-defined]
    window.plugins_menu = controller.menu  # type: ignore[attr-defined]
    return controller
