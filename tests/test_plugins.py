from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from banhelper.plugins import PluginAPI, PluginError, PluginManager


def package(path: Path, *, plugin_id: str = "test-plugin", main: str | None = None) -> Path:
    manifest = {
        "id": plugin_id,
        "name": "Test Plugin",
        "version": "0.1.0",
        "author": "Tests",
        "description": "Plugin test",
        "api_version": 1,
        "entrypoint": "main.py",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("plugin.json", json.dumps(manifest))
        archive.writestr(
            "main.py",
            main or "def activate(api):\n    api.show_status('loaded', 100)\n",
        )
    return path


def api_factory(events: list) -> callable:
    def create(info):
        return PluginAPI(
            plugin_id=info.plugin_id,
            plugin_name=info.name,
            data_dir=info.directory / "data",
            add_menu_action=lambda title, callback: events.append(("action", title)),
            show_status=lambda message, timeout: events.append(("status", message, timeout)),
            run_command=lambda name, payload: True,
        )

    return create


def test_install_is_disabled_then_can_activate(tmp_path):
    manager = PluginManager(tmp_path / "plugins", tmp_path / "config" / "plugins.json")
    info = manager.install(package(tmp_path / "test.bhplugin"))
    assert info.plugin_id == "test-plugin"
    assert not info.enabled and not info.active

    events = []
    manager.load_enabled(api_factory(events))
    info = manager.set_enabled("test-plugin", True)
    assert info.enabled and info.active and events == [("status", "loaded", 100)]

    manager.set_enabled("test-plugin", False)
    assert not manager.plugins()[0].active


def test_plugin_failure_is_contained(tmp_path):
    manager = PluginManager(tmp_path / "plugins", tmp_path / "plugins.json")
    manager.install(package(tmp_path / "broken.bhplugin", main="def activate(api):\n    raise RuntimeError('boom')\n"))
    manager.load_enabled(api_factory([]))
    info = manager.set_enabled("test-plugin", True)
    assert info.enabled and not info.active
    assert "boom" in info.error


def test_rejects_zip_slip(tmp_path):
    archive = tmp_path / "evil.bhplugin"
    with zipfile.ZipFile(archive, "w") as package_file:
        package_file.writestr("../plugin.json", "{}")
    manager = PluginManager(tmp_path / "plugins", tmp_path / "plugins.json")
    with pytest.raises(PluginError, match="Опасный путь"):
        manager.install(archive)


def test_rejects_wrong_extension_and_api(tmp_path):
    manager = PluginManager(tmp_path / "plugins", tmp_path / "plugins.json")
    wrong = package(tmp_path / "plugin.zip")
    with pytest.raises(PluginError, match=".bhplugin"):
        manager.install(wrong)

    archive = tmp_path / "future.bhplugin"
    manifest = {
        "id": "future-plugin", "name": "Future", "version": "1",
        "api_version": 999, "entrypoint": "main.py",
    }
    with zipfile.ZipFile(archive, "w") as package_file:
        package_file.writestr("plugin.json", json.dumps(manifest))
        package_file.writestr("main.py", "def activate(api): pass")
    with pytest.raises(PluginError, match="поддерживается API 1"):
        manager.install(archive)
