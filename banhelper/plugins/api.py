from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

ActionHandler = Callable[[dict[str, Any]], Any]
LogHandler = Callable[[str, str], None]


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    plugin_id: str
    name: str
    version: str
    api_version: int
    description: str = ""
    author: str = ""


class PluginContext:
    """Stable surface exposed to third-party BanHelper plugins."""

    def __init__(self, metadata: PluginMetadata, data_dir: Path, log: LogHandler):
        self.metadata = metadata
        self.data_dir = data_dir
        self._log = log
        self._actions: dict[str, ActionHandler] = {}
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def register_action(self, action_id: str, handler: ActionHandler) -> None:
        normalized = action_id.strip().lower()
        if not normalized or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in normalized):
            raise ValueError(f"Invalid action id: {action_id!r}")
        if normalized in self._actions:
            raise ValueError(f"Action already registered: {normalized}")
        self._actions[normalized] = handler

    def actions(self) -> dict[str, ActionHandler]:
        return dict(self._actions)

    def log(self, level: str, message: str) -> None:
        self._log(level.upper(), f"[{self.metadata.plugin_id}] {message}")


@runtime_checkable
class BanHelperPlugin(Protocol):
    def activate(self, context: PluginContext) -> None: ...

    def deactivate(self) -> None: ...
