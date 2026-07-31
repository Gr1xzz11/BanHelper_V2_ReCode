from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def shutdown_logging() -> None:
    root = logging.getLogger()
    for handler in tuple(root.handlers):
        if not getattr(handler, "_banhelper", False):
            continue
        root.removeHandler(handler)
        try:
            handler.flush()
        finally:
            handler.close()


def configure_logging(log_dir: str | Path, level: str = "INFO") -> None:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    # A process may run more than one isolated smoke/runtime session. Never
    # leave a previous BanHelper file handle attached to the root logger.
    shutdown_logging()
    handler = RotatingFileHandler(directory / "banhelper.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler._banhelper = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
