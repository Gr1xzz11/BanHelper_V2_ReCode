from __future__ import annotations

import json
from pathlib import Path

from banhelper.plugins.manager import PluginManager
from banhelper.plugins.settings import PluginSettingsStore


def make_settings_plugin(root: Path, plugin_id: str = "test.settings") -> Path:
    source = root / plugin_id
    source.mkdir(parents=True)
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "id": plugin_id,
                "name": "Settings test",
                "version": "1.0.0",
                "api_version": 1,
                "entrypoint": "plugin.py:Plugin",
                "settings": {
                    "fields": [
                        {"key": "host", "label": "Host", "type": "text", "default": "127.0.0.1"},
                        {"key": "port", "label": "Port", "type": "integer", "default": 8765, "minimum": 1024, "maximum": 65535},
                        {"key": "timeout", "label": "Timeout", "type": "number", "default": 2.0, "minimum": 0.2, "maximum": 10.0},
                        {"key": "enabled", "label": "Enabled", "type": "boolean", "default": True},
                        {"key": "mode", "label": "Mode", "type": "choice", "default": "FT", "options": ["FT", "RW"]},
                    ]
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (source / "plugin.py").write_text(
        "import json\n"
        "class Plugin:\n"
        "    def activate(self, context):\n"
        "        self.context = context\n"
        "        path = context.data_dir / 'settings.json'\n"
        "        self.settings = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}\n"
        "        context.register_action('check', lambda payload: dict(self.settings), 'Check')\n"
        "    def deactivate(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    return source


def test_schema_defaults_save_and_active_reload(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    make_settings_plugin(plugins)
    manager = PluginManager(plugins, tmp_path / "cache", lambda *_: None, tmp_path / "state.json")
    manager.discover()
    manager.set_enabled("test.settings", True)
    first_instance = manager.loaded["test.settings"].instance

    store = PluginSettingsStore(manager)
    assert store.values("test.settings") == {
        "host": "127.0.0.1",
        "port": 8765,
        "timeout": 2.0,
        "enabled": True,
        "mode": "FT",
    }
    saved = store.save(
        "test.settings",
        {"host": "localhost", "port": 9000, "timeout": 1.5, "enabled": False, "mode": "RW"},
    )
    assert saved["port"] == 9000 and saved["mode"] == "RW"
    assert manager.loaded["test.settings"].instance is not first_instance
    assert manager.invoke("test.settings.check") == saved


def test_akp153_legacy_manifest_gets_compatibility_schema(tmp_path: Path) -> None:
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
    store = PluginSettingsStore(manager)
    schema = store.schema("banhelper-akp153")
    assert [field["key"] for field in schema["fields"]] == [
        "host", "port", "token", "timeout_seconds"
    ]
    assert store.values("banhelper-akp153")["token"] == "banhelper-local"


def test_unknown_keys_are_preserved(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    make_settings_plugin(plugins)
    manager = PluginManager(plugins, tmp_path / "cache", lambda *_: None, tmp_path / "state.json")
    manager.discover()
    store = PluginSettingsStore(manager)
    settings_path = plugins / "data" / "test.settings" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"private_extra": "keep"}), encoding="utf-8")
    store.save("test.settings", {"host": "127.0.0.1", "port": 8765, "timeout": 2.0, "enabled": True, "mode": "FT"})
    assert json.loads(settings_path.read_text(encoding="utf-8"))["private_extra"] == "keep"
