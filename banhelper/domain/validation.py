from __future__ import annotations

import re
from typing import Any

PROTOCOL_VERSION = 2
VALID_MODES = ("FT", "RW")
VALID_EVENT_TYPES = ("ban", "verification_left")
PLAYER_PATTERN = re.compile(r"^[A-Za-z0-9_]{2,16}$")
REASON_PATTERN = re.compile(r"^(?:LIV|\d+(?:\.\d+)+)$", re.IGNORECASE)
EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class ValidationError(ValueError):
    def __init__(self, message: str, field: str = "") -> None:
        super().__init__(message)
        self.field = field


def normalize_mode(value: Any, *, fallback: str | None = None) -> str:
    mode = str(value or "").strip().upper()
    if mode in VALID_MODES:
        return mode
    if fallback is not None:
        candidate = str(fallback).strip().upper()
        return candidate if candidate in VALID_MODES else "FT"
    raise ValidationError("server_mode must be FT or RW", "server_mode")


def normalize_event_type(value: Any) -> str:
    event_type = str(value or "ban").strip().casefold()
    if event_type not in VALID_EVENT_TYPES:
        raise ValidationError("unsupported event_type", "event_type")
    return event_type


def normalize_player(value: Any) -> str:
    player = str(value or "").strip()
    if not PLAYER_PATTERN.fullmatch(player):
        raise ValidationError("player must contain 2-16 latin letters, digits or underscore", "player")
    return player


def normalize_reason(value: Any, *, event_type: str = "ban", allow_empty: bool = False) -> str:
    if normalize_event_type(event_type) == "verification_left":
        return "LIV"
    reason = str(value or "").strip().upper()
    if not reason and allow_empty:
        return ""
    if not REASON_PATTERN.fullmatch(reason):
        raise ValidationError("reason must be LIV or a numeric rule code", "reason")
    return "LIV" if reason.casefold() == "liv" else reason


def validate_event_id(value: Any) -> str:
    event_id = str(value or "").strip()
    if not EVENT_ID_PATTERN.fullmatch(event_id):
        raise ValidationError("event_id has invalid format", "event_id")
    return event_id


def validate_protocol(value: Any) -> int:
    try:
        protocol = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("protocol_version must be an integer", "protocol_version") from exc
    if protocol != PROTOCOL_VERSION:
        raise ValidationError(f"protocol_version {PROTOCOL_VERSION} required", "protocol_version")
    return protocol
