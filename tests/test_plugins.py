from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from banhelper.plugins.manager import PluginManager


def make_plugin(root: Path, *, plugin_id: str = "test.echo") -> Path:
    source = root / "source"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({
        "id": plugin_id,
        "name": "Echo",
        "version": "1.0.0",
        "api_version": 1,
        "entrypoint": "plugin.py:Plugin",
    }), encoding="utf-8")
    (source / "plugin.py").write_text(
        "class Plugin:\n"
        "    def activate(self, context):\n"
        "        context.register_action('echo', lambda payload: payload)\n"
        "    def deactivate(self):\n"
        "        self.stopped = True\n",
        encoding="utf-8",
    )
    bundle = root / "echo.bhplugin"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.write(source / "manifest.json", "manifest.json")
        archive.write(source / "plugin.py", "plugin.py")
    return bundle


def test_load_bundle_and_invoke_action(tmp_path: Path) -> None:
    logs = []
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    bundle = make_plugin(tmp_path)
    bundle.replace(plugins / bundle.name)
    manager = PluginManager(plugins, tmp_path / "cache", lambda level, message: logs.append((level, message)))
    manager.load_all()
    assert manager.invoke("test.echo.echo", {"ok": True}) == {"ok": True}
    assert "test.echo" in manager.loaded
    manager.shutdown()
    assert manager.loaded == {}


def test_rejects_path_traversal(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    bundle = plugins / "evil.bhplugin"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("../escape.py", "bad")
    manager = PluginManager(plugins, tmp_path / "cache", lambda *_: None)
    with pytest.raises(ValueError, match="unsafe path"):
        manager.load(bundle)


def test_rejects_incompatible_api(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    source = plugins / "bad"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({"id": "bad", "name": "Bad", "version": "1", "api_version": 99}), encoding="utf-8")
    manager = PluginManager(plugins, tmp_path / "cache", lambda *_: None)
    with pytest.raises(ValueError, match="Unsupported plugin API"):
        manager.load(source)
