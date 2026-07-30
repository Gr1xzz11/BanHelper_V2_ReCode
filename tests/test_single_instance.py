from __future__ import annotations

import uuid

from banhelper.infrastructure.single_instance import SingleInstance


def test_second_instance_activates_first(qtbot):
    name = f"BanHelper-test-{uuid.uuid4()}"
    primary = SingleInstance(name)
    assert primary.acquire()
    activated: list[bool] = []
    primary.activation_requested.connect(lambda: activated.append(True))
    secondary = SingleInstance(name)
    assert not secondary.acquire()
    qtbot.waitUntil(lambda: activated == [True], timeout=2000)
