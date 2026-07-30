from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: str | Path, level: str = "INFO") -> None:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    if any(getattr(handler, "_banhelper", False) for handler in root.handlers):
        return
    handler = RotatingFileHandler(directory / "banhelper.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler._banhelper = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
