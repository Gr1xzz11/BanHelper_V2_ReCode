from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from .api import PluginContext, PluginMetadata

PLUGIN_API_VERSION = 1
PLUGIN_SUFFIX = ".bhplugin"


@dataclass(slots=True)
class LoadedPlugin:
    metadata: PluginMetadata
    instance: Any
    module: ModuleType
    context: PluginContext


class PluginManager:
    """Discovers and loads BanHelper plugin bundles from the user data dir."""

    def __init__(self, plugins_dir: Path, cache_dir: Path, log: Callable[[str, str], None]):
        self.plugins_dir = plugins_dir
        self.cache_dir = cache_dir
        self.log = log
        self.loaded: dict[str, LoadedPlugin] = {}
        self.actions: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def load_all(self) -> None:
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(self.plugins_dir.iterdir(), key=lambda path: path.name.lower()):
            if source.is_dir() or source.name.lower().endswith(PLUGIN_SUFFIX):
                try:
                    self.load(source)
                except Exception as exc:
                    self.log("ERROR", f"Плагин {source.name} не загружен: {exc}")

    def load(self, source: Path) -> LoadedPlugin:
        root = self._prepare(source)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        metadata = self._metadata(manifest)
        if metadata.plugin_id in self.loaded:
            raise ValueError(f"Duplicate plugin id: {metadata.plugin_id}")
        entrypoint = str(manifest.get("entrypoint", "plugin.py:Plugin"))
        relative_module, separator, object_name = entrypoint.partition(":")
        if not separator or not relative_module.endswith(".py") or not object_name:
            raise ValueError("entrypoint must look like plugin.py:Plugin")
        module_path = (root / relative_module).resolve()
        if root.resolve() not in module_path.parents or not module_path.is_file():
            raise ValueError("entrypoint is outside plugin bundle or missing")
        module = self._import_module(metadata.plugin_id, module_path)
        plugin_type = getattr(module, object_name, None)
        if plugin_type is None:
            raise ValueError(f"Entrypoint object not found: {object_name}")
        instance = plugin_type()
        context = PluginContext(metadata, self.plugins_dir / "data" / metadata.plugin_id, self.log)
        activate = getattr(instance, "activate", None)
        if not callable(activate):
            raise TypeError("Plugin must implement activate(context)")
        activate(context)
        for action_id, handler in context.actions().items():
            qualified = f"{metadata.plugin_id}.{action_id}"
            if qualified in self.actions:
                raise ValueError(f"Duplicate action: {qualified}")
            self.actions[qualified] = handler
        loaded = LoadedPlugin(metadata, instance, module, context)
        self.loaded[metadata.plugin_id] = loaded
        self.log("INFO", f"Плагин загружен: {metadata.name} {metadata.version}")
        return loaded

    def invoke(self, action_id: str, payload: dict[str, Any] | None = None) -> Any:
        handler = self.actions.get(action_id.strip().lower())
        if handler is None:
            raise KeyError(f"Unknown plugin action: {action_id}")
        return handler(dict(payload or {}))

    def shutdown(self) -> None:
        for plugin_id, loaded in reversed(tuple(self.loaded.items())):
            try:
                deactivate = getattr(loaded.instance, "deactivate", None)
                if callable(deactivate):
                    deactivate()
            except Exception as exc:
                self.log("ERROR", f"Ошибка остановки плагина {plugin_id}: {exc}")
        self.actions.clear()
        self.loaded.clear()

    def _prepare(self, source: Path) -> Path:
        if source.is_dir():
            if not (source / "manifest.json").is_file():
                raise ValueError("manifest.json not found")
            return source
        target = self.cache_dir / source.stem
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                destination = (target / member.filename).resolve()
                if target.resolve() not in destination.parents and destination != target.resolve():
                    raise ValueError("unsafe path in plugin archive")
            archive.extractall(target)
        if not (target / "manifest.json").is_file():
            children = [child for child in target.iterdir() if child.is_dir()]
            if len(children) == 1 and (children[0] / "manifest.json").is_file():
                return children[0]
            raise ValueError("manifest.json not found in bundle")
        return target

    @staticmethod
    def _metadata(manifest: dict[str, Any]) -> PluginMetadata:
        required = ("id", "name", "version", "api_version")
        missing = [key for key in required if key not in manifest]
        if missing:
            raise ValueError(f"Missing manifest fields: {', '.join(missing)}")
        api_version = int(manifest["api_version"])
        if api_version != PLUGIN_API_VERSION:
            raise ValueError(f"Unsupported plugin API {api_version}; expected {PLUGIN_API_VERSION}")
        plugin_id = str(manifest["id"]).strip().lower()
        if not plugin_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in plugin_id):
            raise ValueError("Invalid plugin id")
        return PluginMetadata(plugin_id, str(manifest["name"]), str(manifest["version"]), api_version, str(manifest.get("description", "")), str(manifest.get("author", "")))

    @staticmethod
    def _import_module(plugin_id: str, path: Path) -> ModuleType:
        module_name = f"banhelper_external_{plugin_id.replace('.', '_').replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
