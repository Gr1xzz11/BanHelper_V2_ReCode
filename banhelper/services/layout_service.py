from __future__ import annotations


def clean_profile_name(value: str) -> str:
    return " ".join(str(value or "").strip().split())[:64]
