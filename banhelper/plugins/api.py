from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

ActionHandler = Callable[[dict[str, Any]], Any]
LogHandler = Callable[[str, str], None]
StatusHandler = Callable[[str, int], None]
CommandHandler = Callable[[str, Any | None], bool]


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

    def __init__(
        self,
        metadata: PluginMetadata,
        data_dir: Path,
        log: LogHandler,
        show_status: StatusHandler | None = None,
        command: CommandHandler | None = None,
    ):
        self.metadata = metadata
        self.data_dir = data_dir
        self._log = log
        self._show_status = show_status or (lambda _message, _timeout: None)
        self._command = command or (lambda _name, _payload: False)
        self._actions: dict[str, ActionHandler] = {}
        self._action_titles: dict[str, str] = {}
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def plugin_id(self) -> str:
        return self.metadata.plugin_id

    @property
    def plugin_name(self) -> str:
        return self.metadata.name

    def register_action(self, action_id: str, handler: ActionHandler, title: str | None = None) -> None:
        normalized = action_id.strip().lower()
        if not normalized or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for char in normalized):
            raise ValueError(f"Invalid action id: {action_id!r}")
        if normalized in self._actions:
            raise ValueError(f"Action already registered: {normalized}")
        if not callable(handler):
            raise TypeError("Plugin action handler must be callable")
        clean_title = str(title or action_id).strip()
        if not clean_title or len(clean_title) > 100:
            raise ValueError("Plugin action title must contain 1-100 characters")
        self._actions[normalized] = handler
        self._action_titles[normalized] = clean_title

    def actions(self) -> dict[str, ActionHandler]:
        return dict(self._actions)

    def action_titles(self) -> dict[str, str]:
        return dict(self._action_titles)

    def show_status(self, message: str, timeout_ms: int = 3000) -> None:
        self._show_status(str(message)[:300], max(0, min(int(timeout_ms), 60_000)))

    def command(self, name: str, payload: Any | None = None) -> bool:
        return bool(self._command(str(name), payload))

    def log(self, level: str, message: str | None = None) -> None:
        if message is None:
            message = str(level)
            level = "INFO"
        self._log(str(level).upper(), f"[{self.metadata.plugin_id}] {message}")


@runtime_checkable
class BanHelperPlugin(Protocol):
    def activate(self, context: PluginContext) -> None: ...

    def deactivate(self) -> None: ...
