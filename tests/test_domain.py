import time

import pytest

from banhelper.domain.models import BanEvent
from banhelper.domain.reasons import default_reasons
from banhelper.domain.reports import build_report
from banhelper.domain.validation import ValidationError, normalize_mode, normalize_reason, normalize_player


def payload(**changes):
    value = {
        "protocol_version": 2,
        "event_id": "event-0001",
        "event_type": "ban",
        "player": "Player_1",
        "moderator": "Admin",
        "reason": "5.5",
        "server_mode": "FT",
    }
    value.update(changes)
    return value


def test_validation_and_modes():
    assert normalize_mode("rw") == "RW"
    assert normalize_player("Player_1") == "Player_1"
    with pytest.raises(ValidationError):
        normalize_mode("unknown")
    with pytest.raises(ValidationError):
        normalize_player("bad name")


def test_verification_left_is_always_liv():
    event = BanEvent.from_payload(
        payload(event_type="verification_left", reason="1.21.4"), received_at=time.time()
    )
    assert event.reason == "LIV"
    assert normalize_reason("1.21.4", event_type="verification_left") == "LIV"


def test_empty_extracted_reason_opens_manual_fallback_card():
    event = BanEvent.from_payload(payload(reason=""), received_at=time.time())
    assert event.reason == ""


def test_report_format_is_exact():
    assert build_report("Player_1", "5.5", 123, 17, "FT") == "Player_1\n5.5\n123/17"
    assert build_report("Player_1", "5.5", 123, 17, "RW") == "Player_1 (RW)\n5.5\n123/17"


def test_reason_catalogs_are_separate_and_include_legacy_codes():
    ft = {reason.code for reason in default_reasons("FT")}
    rw = {reason.code for reason in default_reasons("RW")}
    assert {"LIV", "5.5", "4.3", "4.3.1", "4.3.2", "5.1", "3.1"} <= ft
    assert rw == {"LIV", "5.5", "4.3.1", "4.3.2", "3.1"}


@pytest.mark.parametrize("field,value", [("protocol_version", 1), ("event_id", "x"), ("reason", "Minecraft 1.21.4"), ("server_mode", "XX")])
def test_invalid_events_are_rejected(field, value):
    with pytest.raises((ValidationError, ValueError)):
        BanEvent.from_payload(payload(**{field: value}), received_at=time.time())
