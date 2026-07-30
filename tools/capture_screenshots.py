from __future__ import annotations

import tempfile
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from banhelper.app.paths import AppPaths
from banhelper.domain.models import ConfirmedBan, PendingBan, Statistics
from banhelper.infrastructure.repositories import DEFAULT_SETTINGS
from banhelper.services.ban_service import BanService
from banhelper.ui.dialogs.settings_dialog import SettingsDialog
from banhelper.ui.main_window import MainWindow
from banhelper.ui.theme import STYLESHEET


def pending(index: int, state: str = "pending", mode: str = "FT", reason: str = "5.5") -> PendingBan:
    player = "LongPlayer_12345" if index == 1 else f"Player_{index:02d}"
    return PendingBan(f"screenshot-event-{index:04d}", player, reason, mode, "fabric", time.time() - index * 13, state, index)


def save(widget, target: Path, app: QApplication) -> None:
    app.processEvents()
    widget.grab().save(str(target))


def main() -> None:
    app = QApplication([]); app.setStyle("Fusion"); app.setStyleSheet(STYLESHEET)
    output = Path("screenshots"); output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="banhelper-screens-") as root:
        service = BanService(AppPaths.temporary(root)); service.command = lambda *_args, **_kwargs: True
        window = MainWindow(service, AppPaths.temporary(root)); window.apply_settings(dict(DEFAULT_SETTINGS)); window.set_statistics(Statistics(123, 17, 30, 97, 26, (("5.5", 38), ("LIV", 27), ("4.3.1", 19)), (("23.07", 11), ("24.07", 18), ("25.07", 14))))
        window.resize(1420, 860); window.show(); app.processEvents()
        default_state = window.saveState(2)
        save(window, output / "01-standard-layout.png", app)
        window.set_current(pending(1, "current", "RW", "4.3.1")); window.queue_panel.set_items(tuple(pending(i, mode="RW" if i % 2 else "FT", reason="LIV" if i == 3 else "5.5") for i in range(2, 14)))
        save(window, output / "02-current-ban-and-queue.png", app)
        save(window.queue_panel, output / "03-queue.png", app)
        records = [ConfirmedBan(i, f"history-{i:04d}", f"HistoryPlayer_{i}", "5.5" if i % 3 else "LIV", "RW" if i % 2 else "FT", f"HistoryPlayer_{i}\n5.5\n{100+i}/{10+i}", "fabric", time.time() - i * 3600) for i in range(1, 31)]
        window.history_panel.set_records(records, 325, 0); window.docks["history"].raise_(); save(window.history_panel, output / "04-history.png", app)
        window.docks["statistics"].raise_(); save(window.stats_panel, output / "05-statistics.png", app)
        dialog = SettingsDialog(dict(DEFAULT_SETTINGS), window); dialog.show(); dialog.resize(680, 560); save(dialog, output / "06-settings.png", app); dialog.close()
        window.docks["fabric"].setFloating(True); window.docks["fabric"].resize(420, 280); window.docks["fabric"].show(); save(window.docks["fabric"], output / "07-floating-panel.png", app); window.docks["fabric"].setFloating(False)
        window.set_locked(True); save(window, output / "08-locked-panels.png", app)
        window.set_locked(False); window.restoreState(default_state, 2); app.processEvents(); window.addDockWidget(window.dockWidgetArea(window.docks["queue"]), window.docks["statistics"]); window.tabifyDockWidget(window.docks["queue"], window.docks["statistics"]); window.docks["statistics"].raise_(); save(window, output / "09-changed-layout.png", app)
        window._restore_dock_state(default_state); window.resize(1100, 700); save(window, output / "10-minimum-size.png", app)
        window.close()


if __name__ == "__main__":
    main()
