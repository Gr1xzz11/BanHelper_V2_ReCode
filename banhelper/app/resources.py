from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    """Return the read-only application resource root for source and frozen builds."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Nuitka exposes __compiled__ and places bundled data next to this module
    # (standalone) or the executable (onefile extraction).
    if "__compiled__" in globals():
        return Path(__file__).resolve().parents[2]
    return Path(__file__).resolve().parents[2]


def resource_path(relative: str | os.PathLike[str]) -> Path:
    candidate = resource_root() / Path(relative)
    return candidate.resolve()


def application_icon() -> Path:
    if os.name == "nt":
        return resource_path("assets/banhelper.ico")
    svg = resource_path("assets/banhelper.svg")
    return svg if svg.is_file() else resource_path("assets/banhelper.png")


def fabric_jar() -> Path:
    bundled = resource_path("fabric/banhelper-bridge-2.0.0.jar")
    if bundled.is_file():
        return bundled
    return resource_path("release/banhelper-bridge-2.0.0.jar")
