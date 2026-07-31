from __future__ import annotations

from types import SimpleNamespace

import pytest

from banhelper.app.bootstrap import ListenerManager
from banhelper.app.paths import AppPaths
from banhelper.services.ban_service import BanService


def manager(tmp_path):
    service = BanService(AppPaths.temporary(tmp_path))
    bridge = ListenerManager(service, {"listener_autostart": False})
    assert bridge.wait()
    return service, bridge


def test_reason_and_copy_are_routed_through_gui_signals(tmp_path) -> None:
    _service, bridge = manager(tmp_path)
    reasons: list[str] = []
    copied: list[bool] = []
    bridge.reason_requested.connect(reasons.append)
    bridge.copy_requested.connect(lambda: copied.append(True))
    bridge._remember_current(SimpleNamespace(event_id="event-1"))

    assert bridge.handle_action("reason", "5.5")
    assert bridge.handle_action("copy", None)
    assert reasons == ["5.5"]
    assert copied == [True]


def test_mode_confirm_and_skip_use_service_queue(tmp_path) -> None:
    service, bridge = manager(tmp_path)
    bridge._remember_current(SimpleNamespace(event_id="event-1"))

    assert bridge.handle_action("mode", "RW")
    assert bridge.handle_action("confirm", None)
    assert bridge.handle_action("skip", None)
    assert service.work.size == 3


def test_actions_validate_current_mode_reason_and_name(tmp_path) -> None:
    _service, bridge = manager(tmp_path)
    with pytest.raises(ValueError, match="Нет текущей карточки"):
        bridge.handle_action("confirm", None)
    with pytest.raises(ValueError, match="FT или RW"):
        bridge.handle_action("mode", "bad")

    bridge._remember_current(SimpleNamespace(event_id="event-1"))
    with pytest.raises(ValueError):
        bridge.handle_action("reason", "not a reason")
    with pytest.raises(ValueError, match="Неизвестное действие"):
        bridge.handle_action("explode", None)
