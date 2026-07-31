from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Callable

from banhelper.plugins.api import PluginAPI

PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_UNPACKED_BYTES = 25 * 1024 * 1024
MAX_FILES = 128


class PluginError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PluginInfo:
    plugin_id: str
    name: str
    version: str
    author: str
    description: str
    api_version: int
    entrypoint: str
    directory: Path
    enabled: bool = False
    active: bool = False
    error: str = ""


@dataclass(slots=True)
class _Runtime:
    module: ModuleType
    api: PluginAPI


class PluginManager:
    def __init__(self, plugins_dir: Path, state_file: Path):
        self.plugins_dir = plugins_dir
        self.state_file = state_file
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, PluginInfo] = {}
        self._runtime: dict[str, _Runtime] = {}
        self._api_factory: Callable[[PluginInfo], PluginAPI] | None = None
        self.refresh()

    def plugins(self) -> tuple[PluginInfo, ...]:
        return tuple(sorted(self._plugins.values(), key=lambda item: item.name.casefold()))

    def refresh(self) -> tuple[PluginInfo, ...]:
        enabled = self._read_state()
        found: dict[str, PluginInfo] = {}
        for directory in sorted(self.plugins_dir.iterdir()):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            try:
                info = self._read_manifest(directory)
                found[info.plugin_id] = replace(
                    info,
                    enabled=info.plugin_id in enabled,
                    active=info.plugin_id in self._runtime,
                )
            except PluginError:
                continue
        self._plugins = found
        return self.plugins()

    def load_enabled(self, api_factory: Callable[[PluginInfo], PluginAPI]) -> None:
        self._api_factory = api_factory
        self.refresh()
        for info in self.plugins():
            if info.enabled:
                self._activate(info.plugin_id)

    def reload(self) -> tuple[PluginInfo, ...]:
        for plugin_id in tuple(self._runtime):
            self._deactivate(plugin_id)
        self.refresh()
        if self._api_factory:
            for info in self.plugins():
                if info.enabled:
                    self._activate(info.plugin_id)
        return self.plugins()

    def set_enabled(self, plugin_id: str, enabled: bool) -> PluginInfo:
        if plugin_id not in self._plugins:
            raise PluginError(f"Плагин {plugin_id!r} не найден")
        state = self._read_state()
        if enabled:
            state.add(plugin_id)
        else:
            state.discard(plugin_id)
        self._write_state(state)
        self._plugins[plugin_id] = replace(self._plugins[plugin_id], enabled=enabled, error="")
        if enabled and self._api_factory:
            self._activate(plugin_id)
        elif not enabled:
            self._deactivate(plugin_id)
        return self._plugins[plugin_id]

    def install(self, archive: Path, *, replace_existing: bool = False) -> PluginInfo:
        archive = Path(archive)
        if archive.suffix.lower() != ".bhplugin":
            raise PluginError("Поддерживаются только файлы .bhplugin")
        if not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise PluginError("Файл плагина отсутствует или превышает 10 МБ")
        with zipfile.ZipFile(archive) as package:
            self._validate_archive(package)
            try:
                manifest = json.loads(package.read("plugin.json").decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PluginError(f"Некорректный plugin.json: {exc}") from exc
            plugin_id = self._validate_manifest(manifest)["id"]
            destination = self.plugins_dir / plugin_id
            if destination.exists() and not replace_existing:
                raise PluginError(f"Плагин {plugin_id} уже установлен")
            with tempfile.TemporaryDirectory(prefix=".plugin-", dir=self.plugins_dir) as temporary:
                staged = Path(temporary) / plugin_id
                staged.mkdir()
                package.extractall(staged)
                self._read_manifest(staged)
                if plugin_id in self._runtime:
                    self._deactivate(plugin_id)
                backup = self.plugins_dir / f".{plugin_id}.backup"
                if backup.exists():
                    shutil.rmtree(backup)
                if destination.exists():
                    destination.replace(backup)
                try:
                    staged.replace(destination)
                except Exception:
                    if backup.exists() and not destination.exists():
                        backup.replace(destination)
                    raise
                if backup.exists():
                    shutil.rmtree(backup)
        state = self._read_state()
        state.discard(plugin_id)
        self._write_state(state)
        self.refresh()
        return self._plugins[plugin_id]

    def _activate(self, plugin_id: str) -> None:
        if plugin_id in self._runtime or not self._api_factory:
            return
        info = self._plugins[plugin_id]
        try:
            entrypoint = (info.directory / info.entrypoint).resolve()
            if info.directory.resolve() not in entrypoint.parents or not entrypoint.is_file():
                raise PluginError("Entrypoint находится вне папки плагина или отсутствует")
            module_name = f"banhelper_plugin_{plugin_id.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, entrypoint)
            if spec is None or spec.loader is None:
                raise PluginError("Не удалось создать загрузчик Python")
            module = importlib.util.module_from_spec(spec)
            api = self._api_factory(info)
            sys.modules[module_name] = module
            sys.path.insert(0, str(info.directory))
            try:
                spec.loader.exec_module(module)
            finally:
                try:
                    sys.path.remove(str(info.directory))
                except ValueError:
                    pass
            activate = getattr(module, "activate", None)
            if not callable(activate):
                raise PluginError("Entrypoint должен содержать функцию activate(api)")
            activate(api)
            self._runtime[plugin_id] = _Runtime(module, api)
            self._plugins[plugin_id] = replace(info, active=True, error="")
        except Exception as exc:
            self._plugins[plugin_id] = replace(info, active=False, error=str(exc)[:300])

    def _deactivate(self, plugin_id: str) -> None:
        runtime = self._runtime.pop(plugin_id, None)
        if runtime:
            deactivate = getattr(runtime.module, "deactivate", None)
            if callable(deactivate):
                try:
                    deactivate(runtime.api)
                except Exception:
                    pass
        info = self._plugins.get(plugin_id)
        if info:
            self._plugins[plugin_id] = replace(info, active=False)

    def _read_manifest(self, directory: Path) -> PluginInfo:
        try:
            manifest = json.loads((directory / "plugin.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PluginError(f"Не удалось прочитать {directory.name}/plugin.json: {exc}") from exc
        data = self._validate_manifest(manifest)
        return PluginInfo(
            data["id"], data["name"], data["version"], data["author"], data["description"],
            data["api_version"], data["entrypoint"], directory,
        )

    @staticmethod
    def _validate_manifest(manifest: object) -> dict:
        if not isinstance(manifest, dict):
            raise PluginError("plugin.json должен содержать JSON-объект")
        plugin_id = str(manifest.get("id", "")).strip().lower()
        name = str(manifest.get("name", "")).strip()
        version = str(manifest.get("version", "")).strip()
        entrypoint = str(manifest.get("entrypoint", "main.py")).strip()
        try:
            api_version = int(manifest.get("api_version", 1))
        except (TypeError, ValueError) as exc:
            raise PluginError("api_version должен быть целым числом") from exc
        if not PLUGIN_ID.fullmatch(plugin_id):
            raise PluginError("id: 3-64 символа, строчные латинские буквы, цифры, _ и -")
        if not name or len(name) > 80 or not version or len(version) > 32:
            raise PluginError("name и version обязательны и имеют некорректную длину")
        path = PurePosixPath(entrypoint.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
            raise PluginError("entrypoint должен указывать на .py внутри плагина")
        if api_version != PluginAPI.API_VERSION:
            raise PluginError(f"Плагину нужен API {api_version}, поддерживается API {PluginAPI.API_VERSION}")
        return {
            "id": plugin_id, "name": name, "version": version,
            "author": str(manifest.get("author", "")).strip()[:80],
            "description": str(manifest.get("description", "")).strip()[:500],
            "api_version": api_version, "entrypoint": path.as_posix(),
        }

    @staticmethod
    def _validate_archive(package: zipfile.ZipFile) -> None:
        entries = package.infolist()
        if not entries or len(entries) > MAX_FILES:
            raise PluginError(f"Архив должен содержать от 1 до {MAX_FILES} файлов")
        total = 0
        names = set()
        for entry in entries:
            path = PurePosixPath(entry.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise PluginError(f"Опасный путь в архиве: {entry.filename}")
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise PluginError("Символические ссылки в .bhplugin запрещены")
            total += entry.file_size
            if total > MAX_UNPACKED_BYTES:
                raise PluginError("Распакованный плагин превышает 25 МБ")
            names.add(path.as_posix().rstrip("/"))
        if "plugin.json" not in names:
            raise PluginError("В корне .bhplugin отсутствует plugin.json")

    def _read_state(self) -> set[str]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            return {str(value) for value in payload.get("enabled", []) if PLUGIN_ID.fullmatch(str(value))}
        except (OSError, json.JSONDecodeError, AttributeError):
            return set()

    def _write_state(self, enabled: set[str]) -> None:
        payload = json.dumps({"enabled": sorted(enabled)}, ensure_ascii=False, indent=2)
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.state_file)
