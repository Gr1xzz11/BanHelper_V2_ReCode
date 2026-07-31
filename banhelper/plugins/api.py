from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable


class PluginAPI:
    """Stable, deliberately small API exposed to third-party plugins."""

    API_VERSION = 1

    def __init__(
        self,
        *,
        plugin_id: str,
        plugin_name: str,
        data_dir: Path,
        add_menu_action: Callable[[str, Callable[[], None]], object],
        show_status: Callable[[str, int], None],
        run_command: Callable[[str, object | None], bool],
    ):
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.data_dir = data_dir
        self._add_menu_action = add_menu_action
        self._show_status = show_status
        self._run_command = run_command
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def add_menu_action(self, title: str, callback: Callable[[], None]) -> object:
        """Add an action below Plugins -> <plugin name>."""
        clean = str(title).strip()
        if not clean or len(clean) > 80 or not callable(callback):
            raise ValueError("Plugin menu action needs a callable and a 1-80 character title")
        return self._add_menu_action(clean, callback)

    def show_status(self, message: str, timeout_ms: int = 3000) -> None:
        self._show_status(str(message)[:300], max(0, min(int(timeout_ms), 60_000)))

    def command(self, name: str, payload: object | None = None) -> bool:
        """Submit a documented BanService command without exposing its internals."""
        return bool(self._run_command(str(name), payload))

    def log(self, message: str, level: int = logging.INFO) -> None:
        logging.getLogger(f"banhelper.plugin.{self.plugin_id}").log(level, str(message))
