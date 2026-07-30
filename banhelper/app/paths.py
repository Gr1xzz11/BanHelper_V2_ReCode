from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    data_dir: Path
    database: Path
    logs_dir: Path
    backups_dir: Path
    config_dir: Path
    cache_dir: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "BanHelper"
            config = base
            local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
            cache = local / "BanHelper" / "cache"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "banhelper"
            config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "banhelper"
            cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "banhelper"
            legacy = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "BanHelper"
            # Keep existing installations intact and visible. New installations
            # use the lowercase XDG location required by the Linux package.
            if legacy.joinpath("banhelper.sqlite3").exists() and not base.joinpath("banhelper.sqlite3").exists():
                base = legacy
        return cls(base, base / "banhelper.sqlite3", base / "logs", base / "backups", config, cache)

    @classmethod
    def temporary(cls, root: str | Path) -> "AppPaths":
        base = Path(root)
        return cls(base, base / "banhelper.sqlite3", base / "logs", base / "backups", base / "config", base / "cache")

    def ensure(self) -> None:
        for directory in (self.data_dir, self.logs_dir, self.backups_dir, self.config_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
