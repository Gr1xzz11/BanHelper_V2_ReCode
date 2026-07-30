from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Qt

from banhelper.app.paths import AppPaths
from banhelper.domain.models import BanEvent, PendingBan, Statistics
from banhelper.services.ban_service import BanService
from banhelper.ui.main_window import MainWindow


def pending(index=1, state="current"):
    return PendingBan(f"gui-event-{index:04d}", f"Player_{index}", "5.5", "FT", "fabric", time.time(), state, index)


def window(qtbot, tmp_path):
    paths = AppPaths.temporary(tmp_path)
    service = BanService(paths)
    commands = []
    service.command = lambda name, payload=None: commands.append((name, payload)) or True
    widget = MainWindow(service, paths)
    qtbot.addWidget(widget)
    widget.show()
    return widget, service, commands


def test_signal_updates_only_current_card(qtbot, tmp_path):
    widget, service, _commands = window(qtbot, tmp_path)
    service.signals.statistics_changed.emit(Statistics(total=10, week=3))
    service.signals.current_changed.emit(pending())
    assert widget.current_panel.player.text() == "Player_1"
    assert widget.current_panel.report.text() == "Player_1\n5.5\n11/4"


def test_queue_and_confirmation_command(qtbot, tmp_path):
    widget, service, commands = window(qtbot, tmp_path)
    service.signals.current_changed.emit(pending())
    service.signals.queue_changed.emit((pending(2, "pending"), pending(3, "pending")))
    assert widget.queue_panel.model.rowCount() == 2
    qtbot.mouseClick(widget.current_panel.confirm, Qt.LeftButton)
    assert ("confirm", "5.5") in commands
    widget.queue_panel.table.selectRow(0)
    widget.queue_panel._activate()
    assert ("activate_queued", "gui-event-0002") in commands


def test_panels_can_hide_return_and_lock(qtbot, tmp_path):
    widget, _service, _commands = window(qtbot, tmp_path)
    queue_dock = widget.docks["queue"]
    queue_dock.hide(); assert not queue_dock.isVisible()
    queue_dock.toggleViewAction().trigger(); assert queue_dock.isVisible()
    widget.set_locked(True)
    assert all(dock.features().value == 0 for dock in widget.docks.values())
    assert not queue_dock.title_bar.close_button.isVisible()


def test_reason_buttons_are_cached_between_ft_rw_events(qtbot, tmp_path):
    widget, _service, _commands = window(qtbot, tmp_path)
    widget.reasons_panel.set_mode("FT")
    ft_buttons = [id(button) for _reason, button in widget.reasons_panel.buttons]
    widget.reasons_panel.set_mode("RW")
    rw_buttons = [id(button) for _reason, button in widget.reasons_panel.buttons]
    widget.reasons_panel.set_mode("FT")
    assert [id(button) for _reason, button in widget.reasons_panel.buttons] == ft_buttons
    assert rw_buttons and rw_buttons != ft_buttons


def test_layout_save_and_restore_commands(qtbot, tmp_path):
    widget, service, commands = window(qtbot, tmp_path)
    widget.active_layout = "Testing"
    widget.save_layout()
    command = next(item for item in commands if item[0] == "save_layout")
    _name, geometry, state, locked = command[1]
    assert geometry and state and not locked
    widget.restore_layout("Testing", geometry, state, True)
    assert widget.active_layout == "Testing" and widget.locked


def test_default_layout_removes_stale_tab_group(qtbot, tmp_path):
    widget, _service, _commands = window(qtbot, tmp_path)
    widget.addDockWidget(widget.dockWidgetArea(widget.docks["queue"]), widget.docks["statistics"])
    widget.tabifyDockWidget(widget.docks["queue"], widget.docks["statistics"])
    assert widget.docks["statistics"] in widget.tabifiedDockWidgets(widget.docks["queue"])

    widget._apply_default_layout()

    assert widget.docks["statistics"] not in widget.tabifiedDockWidgets(widget.docks["queue"])
    assert widget.docks["statistics"] in widget.tabifiedDockWidgets(widget.docks["history"])


def test_100_events_do_not_block_qt_event_loop(qtbot, tmp_path):
    paths = AppPaths.temporary(tmp_path)
    service = BanService(paths, queue_size=512)
    widget = MainWindow(service, paths); qtbot.addWidget(widget); widget.show()
    ticks: list[int] = []
    timer = QTimer(widget); timer.setInterval(1); timer.timeout.connect(lambda: ticks.append(1)); timer.start()
    service.start()
    try:
        for index in range(100):
            event = BanEvent.from_payload({
                "protocol_version": 2, "event_id": f"gui-load-{index:04d}", "event_type": "ban",
                "player": f"Load_{index}", "moderator": "Admin", "reason": "5.5", "server_mode": "FT",
            }, received_at=time.time())
            assert service.submit_event(event)
        qtbot.waitUntil(lambda: service.accepted == 100 and widget.queue_panel.model.rowCount() == 99, timeout=3000)
        assert len(ticks) >= 2
        assert widget.current and widget.current.player == "Load_0"
    finally:
        widget.close(); service.request_stop(); assert service.wait(3)
