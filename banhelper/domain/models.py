from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .validation import (
    normalize_event_type,
    normalize_mode,
    normalize_player,
    normalize_reason,
    ValidationError,
    validate_event_id,
    validate_protocol,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class BanEvent:
    event_id: str
    player: str
    reason: str
    server_mode: str
    moderator: str
    event_type: str
    protocol_version: int
    occurred_at: str
    received_at: float
    source: str = "fabric"
    reason_raw: str = ""
    raw_message: str = ""
    raw_hover: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any], *, received_at: float) -> "BanEvent":
        if not isinstance(payload, dict):
            raise TypeError("JSON body must be an object")
        if "reason" not in payload:
            raise ValidationError("reason field is required", "reason")
        event_type = normalize_event_type(payload.get("event_type", "ban"))
        return cls(
            event_id=validate_event_id(payload.get("event_id")),
            player=normalize_player(payload.get("player")),
            reason=normalize_reason(payload.get("reason"), event_type=event_type, allow_empty=True),
            server_mode=normalize_mode(payload.get("server_mode")),
            moderator=str(payload.get("moderator", "")).strip()[:64],
            event_type=event_type,
            protocol_version=validate_protocol(payload.get("protocol_version")),
            occurred_at=str(payload.get("timestamp") or utc_now_iso())[:64],
            received_at=float(received_at),
            source="fabric",
            reason_raw=str(payload.get("reason_raw", payload.get("reason", "")))[:512],
            raw_message=str(payload.get("raw_message", ""))[:8192],
            raw_hover=str(payload.get("raw_hover", ""))[:8192],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PendingBan:
    event_id: str
    player: str
    reason: str
    server_mode: str
    source: str
    received_at: float
    state: str
    position: int
    event_type: str = "ban"


@dataclass(frozen=True, slots=True)
class ConfirmedBan:
    id: int
    event_id: str
    player: str
    reason: str
    server_mode: str
    report: str
    source: str
    confirmed_at: float


@dataclass(frozen=True, slots=True)
class Statistics:
    total: int = 0
    week: int = 0
    target: int = 0
    ft: int = 0
    rw: int = 0
    top_reasons: tuple[tuple[str, int], ...] = ()
    recent_days: tuple[tuple[str, int], ...] = ()

    @property
    def percent(self) -> int:
        return min(100, round(self.week * 100 / self.target)) if self.target > 0 else 0


@dataclass(frozen=True, slots=True)
class ProcessResult:
    accepted: bool
    duplicate: bool
    current: PendingBan | None
    queue: tuple[PendingBan, ...]
    latency_ms: float
