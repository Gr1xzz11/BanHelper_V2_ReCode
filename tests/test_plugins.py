from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from banhelper.plugins import PluginError, PluginManager


def make_plugin(root: Path, *, plugin_id: str = "test.echo", broken: bool = False) -> Path:
    source = root / f"source-{plugin_id.replace('.', '-')}"
    source.mkdir()
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "id": plugin_id,
                "name": "Echo",
                "version": "1.0.0",
                "api_version": 1,
                "entrypoint": "plugin.py:Plugin",
            }
        ),
        encoding="utf-8",
    )
    body = (
        "class Plugin:\n"
        "    def activate(self, context):\n"
        "        raise RuntimeError('boom')\n"
        if broken
        else
        "class Plugin:\n"
        "    def activate(self, context):\n"
        "        self.context = context\n"
        "        context.register_action('echo', lambda payload: payload, 'Echo payload')\n"
        "    def deactivate(self):\n"
        "        self.context.log('INFO', 'stopped')\n"
    )
    (source / "plugin.py").write_text(body, encoding="utf-8")
    bundle = root / f"{plugin_id}.bhplugin"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source / "manifest.json", "manifest.json")
        archive.write(source / "plugin.py", "plugin.py")
    return bundle


def manager(tmp_path: Path) -> PluginManager:
    return PluginManager(
        tmp_path / "plugins",
        tmp_path / "cache",
        lambda *_args: None,
        tmp_path / "config" / "plugins.json",
    )


def test_builtin_plugin_is_seeded_and_enabled(tmp_path: Path) -> None:
    plugins = manager(tmp_path)
    core = next(record for record in plugins.records() if record.metadata.plugin_id == "core-tools")
    assert core.builtin and core.enabled
    plugins.set_host_callbacks(show_status=lambda *_: None, command=lambda *_: True)
    plugins.load_enabled()
    assert plugins.actions_for("core-tools")


def test_install_enable_invoke_disable_and_uninstall(tmp_path: Path) -> None:
    plugins = manager(tmp_path)
    bundle = make_plugin(tmp_path)
    record = plugins.install(bundle)
    assert record.metadata.plugin_id == "test.echo"
    assert not record.enabled and not record.active

    plugins.set_host_callbacks(show_status=lambda *_: None, command=lambda *_: True)
    record = plugins.set_enabled("test.echo", True)
    assert record.enabled and record.active
    assert plugins.actions_for("test.echo") == (("test.echo.echo", "Echo payload"),)
    assert plugins.invoke("test.echo.echo", {"ok": True}) == {"ok": True}

    record = plugins.set_enabled("test.echo", False)
    assert not record.enabled and not record.active
    plugins.uninstall("test.echo")
    assert all(item.metadata.plugin_id != "test.echo" for item in plugins.records())


def test_plugin_failure_is_contained(tmp_path: Path) -> None:
    plugins = manager(tmp_path)
    plugins.install(make_plugin(tmp_path, plugin_id="test.broken", broken=True))
    record = plugins.set_enabled("test.broken", True)
    assert record.enabled and not record.active
    assert "boom" in record.error


def test_rejects_path_traversal(tmp_path: Path) -> None:
    bundle = tmp_path / "evil.bhplugin"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("../escape.py", "bad")
    plugins = manager(tmp_path)
    with pytest.raises(PluginError, match="Опасный путь"):
        plugins.install(bundle)


def test_rejects_incompatible_api(tmp_path: Path) -> None:
    bundle = tmp_path / "future.bhplugin"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"id": "future", "name": "Future", "version": "1", "api_version": 99}),
        )
        archive.writestr("plugin.py", "class Plugin: pass")
    plugins = manager(tmp_path)
    with pytest.raises(PluginError, match="поддерживается API 1"):
        plugins.install(bundle)
