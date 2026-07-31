from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from banhelper.plugins.manager import PluginManager
from banhelper.ui.dialogs.settings_dialog import SettingsDialog


def test_plugins_tab_lists_plugin_and_builds_akp153_fields(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    source = plugins / "akp"
    source.mkdir()
    (source / "manifest.json").write_text(
        json.dumps({
            "id": "banhelper-akp153",
            "name": "BanHelper AKP153 Bridge",
            "version": "1.0.1",
            "api_version": 1,
            "entrypoint": "plugin.py:Plugin",
        }),
        encoding="utf-8",
    )
    (source / "plugin.py").write_text(
        "class Plugin:\n"
        "    def activate(self, context): self.context = context\n"
        "    def deactivate(self): pass\n",
        encoding="utf-8",
    )
    manager = PluginManager(plugins, tmp_path / "cache", lambda *_: None, tmp_path / "state.json")
    manager.discover()
    parent = QMainWindow()
    parent.plugin_manager = manager
    dialog = SettingsDialog({}, parent)
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    assert "Плагины" in [tabs.tabText(index) for index in range(tabs.count())]
    index = dialog.plugin_selector.findData("banhelper-akp153")
    assert index >= 0
    dialog.plugin_selector.setCurrentIndex(index)
    app.processEvents()
    assert set(dialog.plugin_editors) == {"host", "port", "token", "timeout_seconds"}
    assert dialog.plugin_editors["port"].value() == 8765
    dialog.close()
    parent.close()
