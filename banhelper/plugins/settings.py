from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .manager import PluginError, PluginManager, PluginRecord


AKP153_SETTINGS = {
    "test_action": "",
    "fields": [
        {
            "key": "host",
            "label": "Адрес BanHelper API",
            "type": "text",
            "default": "127.0.0.1",
            "placeholder": "127.0.0.1",
        },
        {
            "key": "port",
            "label": "Порт",
            "type": "integer",
            "default": 8765,
            "minimum": 1024,
            "maximum": 65535,
        },
        {
            "key": "token",
            "label": "Токен",
            "type": "password",
            "default": "banhelper-local",
        },
        {
            "key": "timeout_seconds",
            "label": "Таймаут, секунд",
            "type": "number",
            "default": 2.0,
            "minimum": 0.2,
            "maximum": 10.0,
            "decimals": 1,
        },
    ],
}

_ALLOWED_TYPES = {"text", "password", "integer", "number", "boolean", "choice"}


class PluginSettingsStore:
    """Read and persist settings declared by a `.bhplugin` manifest."""

    def __init__(self, manager: PluginManager):
        self.manager = manager

    def records(self) -> tuple[PluginRecord, ...]:
        return self.manager.records()

    def schema(self, plugin_id: str) -> dict[str, Any]:
        record = self._record(plugin_id)
        manifest = self._manifest(record)
        raw = manifest.get("settings")
        if raw is None and plugin_id == "banhelper-akp153":
            raw = AKP153_SETTINGS
        if raw is None:
            return {"fields": [], "test_action": ""}
        if isinstance(raw, list):
            raw = {"fields": raw}
        if not isinstance(raw, dict):
            raise PluginError("settings в manifest.json должен быть объектом или списком")
        fields = raw.get("fields", [])
        if not isinstance(fields, list):
            raise PluginError("settings.fields должен быть списком")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in fields:
            if not isinstance(item, dict):
                raise PluginError("Каждое поле настроек должно быть JSON-объектом")
            key = str(item.get("key", "")).strip()
            field_type = str(item.get("type", "text")).strip().lower()
            if not key or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in key):
                raise PluginError(f"Некорректный ключ настройки: {key!r}")
            if key in seen:
                raise PluginError(f"Повторяющийся ключ настройки: {key}")
            if field_type not in _ALLOWED_TYPES:
                raise PluginError(f"Неизвестный тип настройки {field_type!r}")
            seen.add(key)
            field = dict(item)
            field["key"] = key
            field["type"] = field_type
            field["label"] = str(item.get("label") or key)[:100]
            if field_type == "choice":
                options = item.get("options", [])
                if not isinstance(options, list) or not options:
                    raise PluginError(f"Для {key} требуется непустой список options")
                field["options"] = options[:100]
            normalized.append(field)
        return {
            "fields": normalized,
            "test_action": str(raw.get("test_action", "")).strip().lower(),
        }

    def values(self, plugin_id: str) -> dict[str, Any]:
        schema = self.schema(plugin_id)
        values = {field["key"]: field.get("default") for field in schema["fields"]}
        path = self._settings_path(plugin_id)
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PluginError(f"Не удалось прочитать настройки плагина: {exc}") from exc
            if not isinstance(loaded, dict):
                raise PluginError("settings.json плагина должен содержать JSON-объект")
            values.update(loaded)
        return values

    def save(self, plugin_id: str, supplied: dict[str, Any]) -> dict[str, Any]:
        record = self._record(plugin_id)
        schema = self.schema(plugin_id)
        current = self.values(plugin_id)
        validated = dict(current)
        for field in schema["fields"]:
            key = field["key"]
            value = supplied.get(key, field.get("default"))
            validated[key] = self._validate_value(field, value)

        path = self._settings_path(plugin_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(validated, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)

        if plugin_id in self.manager.loaded:
            self.manager.unload(plugin_id)
            try:
                self.manager.load(record.source)
            except Exception as exc:
                raise PluginError(f"Настройки сохранены, но плагин не перезапустился: {exc}") from exc
        return validated

    def test_action(self, plugin_id: str) -> str:
        action = self.schema(plugin_id).get("test_action", "")
        if not action:
            return ""
        if "." not in action:
            action = f"{plugin_id}.{action}"
        return action

    def _settings_path(self, plugin_id: str) -> Path:
        return self.manager.plugins_dir / "data" / plugin_id / "settings.json"

    def _record(self, plugin_id: str) -> PluginRecord:
        record = next((item for item in self.manager.records() if item.metadata.plugin_id == plugin_id), None)
        if record is None:
            raise PluginError(f"Плагин {plugin_id!r} не найден")
        return record

    @staticmethod
    def _manifest(record: PluginRecord) -> dict[str, Any]:
        source = record.source
        try:
            if source.is_dir():
                value = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
            else:
                with zipfile.ZipFile(source) as archive:
                    candidates = [
                        name for name in archive.namelist()
                        if PurePosixPath(name).name == "manifest.json"
                    ]
                    selected = "manifest.json" if "manifest.json" in candidates else (
                        candidates[0] if len(candidates) == 1 else ""
                    )
                    if not selected:
                        raise PluginError("manifest.json не найден в архиве плагина")
                    value = json.loads(archive.read(selected).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            raise PluginError(f"Не удалось прочитать manifest.json: {exc}") from exc
        if not isinstance(value, dict):
            raise PluginError("manifest.json должен содержать JSON-объект")
        return value

    @staticmethod
    def _validate_value(field: dict[str, Any], value: Any) -> Any:
        field_type = field["type"]
        key = field["key"]
        if field_type in {"text", "password"}:
            result = str(value or "")
            maximum_length = int(field.get("maximum_length", 1000))
            if len(result) > maximum_length:
                raise PluginError(f"Поле «{field['label']}» длиннее {maximum_length} символов")
            return result
        if field_type == "boolean":
            return bool(value)
        if field_type == "integer":
            try:
                result = int(value)
            except (TypeError, ValueError) as exc:
                raise PluginError(f"Поле «{field['label']}» должно быть целым числом") from exc
            minimum = int(field.get("minimum", -2147483648))
            maximum = int(field.get("maximum", 2147483647))
            if not minimum <= result <= maximum:
                raise PluginError(f"Поле «{field['label']}» должно быть от {minimum} до {maximum}")
            return result
        if field_type == "number":
            try:
                result = float(value)
            except (TypeError, ValueError) as exc:
                raise PluginError(f"Поле «{field['label']}» должно быть числом") from exc
            minimum = float(field.get("minimum", -1e308))
            maximum = float(field.get("maximum", 1e308))
            if not minimum <= result <= maximum:
                raise PluginError(f"Поле «{field['label']}» должно быть от {minimum} до {maximum}")
            return result
        if field_type == "choice":
            options = field["options"]
            allowed = [option.get("value") if isinstance(option, dict) else option for option in options]
            if value not in allowed:
                raise PluginError(f"Некорректное значение поля «{field['label']}»")
            return value
        raise PluginError(f"Неизвестный тип поля {field_type!r} для {key}")
