from __future__ import annotations

from .validation import normalize_mode, normalize_player, normalize_reason


def build_report(player: str, reason: str, total: int, week: int, server_mode: str) -> str:
    clean_player = normalize_player(player)
    clean_reason = normalize_reason(reason)
    mode = normalize_mode(server_mode)
    shown_player = f"{clean_player} (RW)" if mode == "RW" else clean_player
    return f"{shown_player}\n{clean_reason}\n{int(total)}/{int(week)}"
