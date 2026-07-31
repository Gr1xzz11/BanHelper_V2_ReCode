from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Callable

from banhelper.app.resources import resource_path

from .api import PluginContext, PluginMetadata

PLUGIN_API_VERSION = 1
PLUGIN_SUFFIX = ".bhplugin"
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_UNPACKED_BYTES = 50 * 1024 * 1024
MAX_FILES = 256


class PluginError(RuntimeError):
    pass


@dataclass(slots=True)
class LoadedPlugin:
    metadata: PluginMetadata
    instance: Any
    module: ModuleType
    context: PluginContext


@dataclass(frozen=True, slots=True)
class PluginRecord:
    metadata: PluginMetadata
    source: Path
    enabled: bool = False
    active: bool = False
    error: str = ""
    builtin: bool = False


class PluginManager:
    """Install, enable and run BanHelper `.bhplugin` bundles."""

    def __init__(
        self,
        plugins_dir: Path,
        cache_dir: Path,
        log: Callable[[str, str], None],
        state_file: Path | None = None,
    ):
        self.plugins_dir = Path(plugins_dir)
        self.cache_dir = Path(cache_dir)
        self.state_file = Path(state_file or (self.plugins_dir / ".enabled.json"))
        self.log = log
        self.loaded: dict[str, LoadedPlugin] = {}
        self.actions: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self.action_titles: dict[str, str] = {}
        self._records: dict[str, PluginRecord] = {}
        self._show_status: Callable[[str, int], None] = lambda _message, _timeout: None
        self._command: Callable[[str, Any | None], bool] = lambda _name, _payload: False
        self._builtin_ids: set[str] = set()
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._seed_builtins()
        self.discover()

    def set_host_callbacks(
        self,
        *,
        show_status: Callable[[str, int], None],
        command: Callable[[str, Any | None], bool],
    ) -> None:
        self._show_status = show_status
        self._command = command

    def records(self) -> tuple[PluginRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda item: item.metadata.name.casefold()))

    def discover(self) -> tuple[PluginRecord, ...]:
        enabled = self._read_enabled()
        records: dict[str, PluginRecord] = {}
        for source in sorted(self.plugins_dir.iterdir(), key=lambda path: path.name.casefold()):
            if source.name.startswith(".") or source.name == "data":
                continue
            if not source.is_dir() and not source.name.lower().endswith(PLUGIN_SUFFIX):
                continue
            try:
                metadata = self._metadata_from_source(source)
                if metadata.plugin_id in records:
                    raise PluginError(f"Duplicate plugin id: {metadata.plugin_id}")
                previous = self._records.get(metadata.plugin_id)
                records[metadata.plugin_id] = PluginRecord(
                    metadata=metadata,
                    source=source,
                    enabled=metadata.plugin_id in enabled,
                    active=metadata.plugin_id in self.loaded,
                    error=previous.error if previous else "",
                    builtin=metadata.plugin_id in self._builtin_ids,
                )
            except Exception as exc:
                self.log("ERROR", f"Плагин {source.name} не распознан: {exc}")
        self._records = records
        return self.records()

    def load_all(self) -> None:
        """Compatibility alias: load only plugins explicitly enabled by the user."""
        self.load_enabled()

    def load_enabled(self) -> None:
        self.discover()
        for record in self.records():
            if record.enabled and not record.active:
                try:
                    self.load(record.source)
                except Exception as exc:
                    self._set_error(record.metadata.plugin_id, str(exc))
                    self.log("ERROR", f"Плагин {record.metadata.name} не загружен: {exc}")

    def reload_all(self) -> tuple[PluginRecord, ...]:
        self.shutdown()
        self.discover()
        self.load_enabled()
        return self.records()

    def install(self, archive: Path, *, replace_existing: bool = False) -> PluginRecord:
        archive = Path(archive)
        if archive.suffix.lower() != PLUGIN_SUFFIX:
            raise PluginError("Поддерживаются только файлы .bhplugin")
        if not archive.is_file():
            raise PluginError("Файл плагина не найден")
        if archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise PluginError("Файл плагина превышает 25 МБ")
        with zipfile.ZipFile(archive) as package:
            self._validate_archive(package)
            manifest = self._read_manifest_from_archive(package)
            metadata = self._metadata(manifest)
        existing = self._records.get(metadata.plugin_id)
        if existing and not replace_existing:
            raise PluginError(f"Плагин {metadata.plugin_id} уже установлен")
        if existing and existing.builtin:
            raise PluginError("Встроенный плагин нельзя заменить")
        if existing:
            self.unload(metadata.plugin_id)
            if existing.source.is_dir():
                shutil.rmtree(existing.source)
            elif existing.source.exists():
                existing.source.unlink()
        destination = self.plugins_dir / f"{metadata.plugin_id}{PLUGIN_SUFFIX}"
        temporary = destination.with_suffix(f"{PLUGIN_SUFFIX}.tmp")
        shutil.copy2(archive, temporary)
        os.replace(temporary, destination)
        enabled = self._read_enabled()
        enabled.discard(metadata.plugin_id)
        self._write_enabled(enabled)
        self.discover()
        return self._records[metadata.plugin_id]

    def uninstall(self, plugin_id: str) -> None:
        record = self._records.get(plugin_id)
        if record is None:
            raise PluginError(f"Плагин {plugin_id!r} не найден")
        if record.builtin:
            raise PluginError("Встроенный плагин удалить нельзя")
        self.unload(plugin_id)
        if record.source.is_dir():
            shutil.rmtree(record.source)
        elif record.source.exists():
            record.source.unlink()
        cached = self.cache_dir / plugin_id
        if cached.exists():
            shutil.rmtree(cached)
        enabled = self._read_enabled()
        enabled.discard(plugin_id)
        self._write_enabled(enabled)
        self.discover()

    def set_enabled(self, plugin_id: str, enabled: bool) -> PluginRecord:
        record = self._records.get(plugin_id)
        if record is None:
            raise PluginError(f"Плагин {plugin_id!r} не найден")
        state = self._read_enabled()
        if enabled:
            state.add(plugin_id)
        else:
            state.discard(plugin_id)
        self._write_enabled(state)
        self._records[plugin_id] = replace(record, enabled=enabled, error="")
        if enabled:
            try:
                self.load(record.source)
            except Exception as exc:
                self._set_error(plugin_id, str(exc))
        else:
            self.unload(plugin_id)
        return self._records[plugin_id]

    def load(self, source: Path) -> LoadedPlugin:
        source = Path(source)
        root = self._prepare(source)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        metadata = self._metadata(manifest)
        if metadata.plugin_id in self.loaded:
            return self.loaded[metadata.plugin_id]
        entrypoint = str(manifest.get("entrypoint", "plugin.py:Plugin"))
        relative_module, separator, object_name = entrypoint.partition(":")
        if not separator or not relative_module.endswith(".py") or not object_name:
            raise PluginError("entrypoint должен выглядеть как plugin.py:Plugin")
        module_path = (root / relative_module).resolve()
        if root.resolve() not in module_path.parents or not module_path.is_file():
            raise PluginError("entrypoint находится вне плагина или отсутствует")
        module = self._import_module(metadata.plugin_id, module_path)
        plugin_type = getattr(module, object_name, None)
        if plugin_type is None:
            raise PluginError(f"Объект entrypoint не найден: {object_name}")
        instance = plugin_type()
        context = PluginContext(
            metadata,
            self.plugins_dir / "data" / metadata.plugin_id,
            self.log,
            self._show_status,
            self._command,
        )
        activate = getattr(instance, "activate", None)
        if not callable(activate):
            raise PluginError("Плагин должен реализовать activate(context)")
        activate(context)
        registered: list[str] = []
        try:
            titles = context.action_titles()
            for action_id, handler in context.actions().items():
                qualified = f"{metadata.plugin_id}.{action_id}"
                if qualified in self.actions:
                    raise PluginError(f"Duplicate action: {qualified}")
                self.actions[qualified] = handler
                self.action_titles[qualified] = titles.get(action_id, action_id)
                registered.append(qualified)
        except Exception:
            for qualified in registered:
                self.actions.pop(qualified, None)
                self.action_titles.pop(qualified, None)
            raise
        loaded = LoadedPlugin(metadata, instance, module, context)
        self.loaded[metadata.plugin_id] = loaded
        record = self._records.get(metadata.plugin_id)
        if record:
            self._records[metadata.plugin_id] = replace(record, active=True, error="")
        self.log("INFO", f"Плагин загружен: {metadata.name} {metadata.version}")
        return loaded

    def unload(self, plugin_id: str) -> None:
        loaded = self.loaded.pop(plugin_id, None)
        if loaded is not None:
            try:
                deactivate = getattr(loaded.instance, "deactivate", None)
                if callable(deactivate):
                    deactivate()
            except Exception as exc:
                self.log("ERROR", f"Ошибка остановки плагина {plugin_id}: {exc}")
        prefix = f"{plugin_id}."
        for action_id in tuple(self.actions):
            if action_id.startswith(prefix):
                self.actions.pop(action_id, None)
                self.action_titles.pop(action_id, None)
        record = self._records.get(plugin_id)
        if record:
            self._records[plugin_id] = replace(record, active=False)

    def actions_for(self, plugin_id: str) -> tuple[tuple[str, str], ...]:
        prefix = f"{plugin_id}."
        return tuple(
            (action_id, self.action_titles.get(action_id, action_id.removeprefix(prefix)))
            for action_id in sorted(self.actions)
            if action_id.startswith(prefix)
        )

    def invoke(self, action_id: str, payload: dict[str, Any] | None = None) -> Any:
        handler = self.actions.get(action_id.strip().lower())
        if handler is None:
            raise KeyError(f"Unknown plugin action: {action_id}")
        return handler(dict(payload or {}))

    def shutdown(self) -> None:
        for plugin_id in reversed(tuple(self.loaded)):
            self.unload(plugin_id)

    def _set_error(self, plugin_id: str, error: str) -> None:
        record = self._records.get(plugin_id)
        if record:
            self._records[plugin_id] = replace(record, active=False, error=str(error)[:400])

    def _prepare(self, source: Path) -> Path:
        if source.is_dir():
            if not (source / "manifest.json").is_file():
                raise PluginError("manifest.json не найден")
            return source
        with zipfile.ZipFile(source) as archive:
            self._validate_archive(archive)
            metadata = self._metadata(self._read_manifest_from_archive(archive))
            target = self.cache_dir / metadata.plugin_id
            if target.exists():
                shutil.rmtree(target)
            with tempfile.TemporaryDirectory(prefix="plugin-", dir=self.cache_dir) as temporary:
                staged = Path(temporary) / metadata.plugin_id
                staged.mkdir()
                archive.extractall(staged)
                if not (staged / "manifest.json").is_file():
                    children = [child for child in staged.iterdir() if child.is_dir()]
                    if len(children) == 1 and (children[0] / "manifest.json").is_file():
                        staged = children[0]
                    else:
                        raise PluginError("manifest.json не найден в архиве")
                shutil.copytree(staged, target)
            return target

    def _metadata_from_source(self, source: Path) -> PluginMetadata:
        if source.is_dir():
            manifest_path = source / "manifest.json"
            if not manifest_path.is_file():
                raise PluginError("manifest.json не найден")
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PluginError(f"Некорректный manifest.json: {exc}") from exc
            return self._metadata(manifest)
        with zipfile.ZipFile(source) as archive:
            self._validate_archive(archive)
            return self._metadata(self._read_manifest_from_archive(archive))

    @staticmethod
    def _read_manifest_from_archive(archive: zipfile.ZipFile) -> dict[str, Any]:
        candidates = [name for name in archive.namelist() if PurePosixPath(name).name == "manifest.json"]
        if "manifest.json" in candidates:
            selected = "manifest.json"
        elif len(candidates) == 1:
            selected = candidates[0]
        else:
            raise PluginError("В архиве должен быть один manifest.json")
        try:
            value = json.loads(archive.read(selected).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PluginError(f"Некорректный manifest.json: {exc}") from exc
        if not isinstance(value, dict):
            raise PluginError("manifest.json должен содержать JSON-объект")
        return value

    @staticmethod
    def _metadata(manifest: dict[str, Any]) -> PluginMetadata:
        required = ("id", "name", "version", "api_version")
        missing = [key for key in required if key not in manifest]
        if missing:
            raise PluginError(f"В manifest.json отсутствуют поля: {', '.join(missing)}")
        try:
            api_version = int(manifest["api_version"])
        except (TypeError, ValueError) as exc:
            raise PluginError("api_version должен быть целым числом") from exc
        if api_version != PLUGIN_API_VERSION:
            raise PluginError(f"Плагину нужен API {api_version}; поддерживается API {PLUGIN_API_VERSION}")
        plugin_id = str(manifest["id"]).strip().lower()
        if not plugin_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in plugin_id):
            raise PluginError("Некорректный id плагина")
        name = str(manifest["name"]).strip()
        version = str(manifest["version"]).strip()
        if not name or not version:
            raise PluginError("name и version обязательны")
        return PluginMetadata(
            plugin_id,
            name[:100],
            version[:40],
            api_version,
            str(manifest.get("description", ""))[:500],
            str(manifest.get("author", ""))[:100],
        )

    @staticmethod
    def _validate_archive(archive: zipfile.ZipFile) -> None:
        entries = archive.infolist()
        if not entries or len(entries) > MAX_FILES:
            raise PluginError(f"Архив должен содержать от 1 до {MAX_FILES} файлов")
        total = 0
        for member in entries:
            path = PurePosixPath(member.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise PluginError(f"Опасный путь в архиве: {member.filename}")
            if stat.S_ISLNK(member.external_attr >> 16):
                raise PluginError("Символические ссылки в .bhplugin запрещены")
            total += member.file_size
            if total > MAX_UNPACKED_BYTES:
                raise PluginError("Распакованный плагин превышает 50 МБ")

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

    def _read_enabled(self) -> set[str]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            values = payload.get("enabled", []) if isinstance(payload, dict) else []
            return {str(value) for value in values}
        except (OSError, json.JSONDecodeError):
            return set()

    def _write_enabled(self, enabled: set[str]) -> None:
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"enabled": sorted(enabled)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.state_file)

    def _seed_builtins(self) -> None:
        source_root = resource_path("builtin_plugins")
        first_run = not self.state_file.exists()
        if not source_root.is_dir():
            return
        enabled = self._read_enabled()
        for source in sorted(source_root.iterdir()):
            if not source.is_dir() or not (source / "manifest.json").is_file():
                continue
            try:
                metadata = self._metadata(json.loads((source / "manifest.json").read_text(encoding="utf-8")))
            except Exception as exc:
                self.log("ERROR", f"Встроенный плагин {source.name} повреждён: {exc}")
                continue
            self._builtin_ids.add(metadata.plugin_id)
            destination = self.plugins_dir / metadata.plugin_id
            if not destination.exists():
                shutil.copytree(source, destination)
            if first_run:
                enabled.add(metadata.plugin_id)
        if first_run and enabled:
            self._write_enabled(enabled)
