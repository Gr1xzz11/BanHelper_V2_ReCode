from __future__ import annotations

import http.client
import json
import sys
import threading

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from banhelper.app.paths import AppPaths
from banhelper.app.resources import application_icon, fabric_jar
from banhelper.infrastructure.database import Database
from banhelper.infrastructure.fabric_listener import FabricListener
from banhelper.infrastructure.logging_setup import configure_logging, shutdown_logging
from banhelper.infrastructure.repositories import BanRepository
from banhelper.infrastructure.single_instance import SingleInstance
from banhelper.plugins import PluginManager
from banhelper.services.ban_service import BanService
from banhelper.ui.main_window import MainWindow
from banhelper.ui.plugin_menu import attach_plugin_menu
from banhelper.ui.theme import build_stylesheet


class ListenerManager(QObject):
    changed = Signal(bool, str, int, str)
    test_completed = Signal(bool, str)

    def __init__(self, service: BanService, settings: dict):
        super().__init__(); self.service = service; self.listener: FabricListener | None = None
        self.configuration = {}; self._stop_thread: threading.Thread | None = None
        self.apply(settings)

    def apply(self, settings: dict) -> None:
        configuration = {
            "host": str(settings.get("listener_host", "127.0.0.1")),
            "port": int(settings.get("listener_port", 8765)),
            "token": str(settings.get("listener_token", "banhelper-local")),
            "enabled": bool(settings.get("listener_autostart", True)),
            "fallback_mode": str(settings.get("manual_mode", "FT")),
        }
        if configuration == self.configuration and self.listener and self.listener.running: return
        self.configuration = configuration
        def restart():
            old = self.listener
            if old:
                old.request_stop(); old.wait(3)
            if not configuration["enabled"]:
                self.listener = None; self.changed.emit(False, configuration["host"], configuration["port"], "Listener выключен"); self.service.signals.log.emit("INFO", "Fabric listener выключен в настройках"); return
            try:
                new_listener = FabricListener(
                    configuration["host"], configuration["port"], configuration["token"],
                    self.service.submit_event, self.service.signals.log.emit, configuration["fallback_mode"],
                )
                new_listener.start(); self.listener = new_listener
                self.changed.emit(True, new_listener.host, new_listener.port, "")
            except Exception as exc:
                self.listener = None; self.changed.emit(False, configuration["host"], configuration["port"], str(exc)); self.service.signals.log.emit("ERROR", f"Fabric listener не запущен: {exc}")
        self._stop_thread = threading.Thread(target=restart, name="ListenerRestart", daemon=True); self._stop_thread.start()

    def metrics(self) -> tuple[int, int, float]:
        listener = self.listener
        return (listener.received, listener.rejected, listener.last_event_at) if listener else (0, 0, 0.0)

    def status_text(self) -> str:
        listener = self.listener
        return f"Listener работает на {listener.host}:{listener.port}" if listener and listener.running else "Listener не запущен"

    def test_async(self) -> None:
        configuration = dict(self.configuration)
        def check() -> None:
            connection = None
            try:
                connection = http.client.HTTPConnection(configuration["host"], configuration["port"], timeout=1.5)
                connection.request("GET", "/status")
                response = connection.getresponse(); payload = json.loads(response.read().decode("utf-8"))
                ok = response.status == 200 and payload.get("protocol_version") == 2
                self.test_completed.emit(ok, "Listener отвечает; протокол v2" if ok else "Listener вернул несовместимый ответ")
            except Exception as exc:
                self.test_completed.emit(False, f"Listener не отвечает: {exc}")
            finally:
                if connection:
                    connection.close()
        threading.Thread(target=check, name="ListenerSelfTest", daemon=True).start()

    def request_stop(self) -> None:
        if self.listener: self.listener.request_stop()

    def wait(self) -> bool:
        if self._stop_thread and self._stop_thread.is_alive(): self._stop_thread.join(3)
        return self.listener.wait(3) if self.listener else True


class Runtime:
    def __init__(self, paths: AppPaths, service: BanService, listeners: ListenerManager, plugins: PluginManager):
        self.paths = paths; self.service = service; self.listeners = listeners; self.plugins = plugins

    def request_stop(self) -> None:
        self.plugins.shutdown(); self.listeners.request_stop(); self.service.request_stop()

    def wait(self) -> tuple[bool, bool]:
        return self.listeners.wait(), self.service.wait(5.0)


def load_startup_settings(paths: AppPaths) -> dict:
    connection = Database(paths.database).connect()
    try:
        return BanRepository(connection).settings()
    finally:
        connection.close()


def create_runtime(paths: AppPaths) -> tuple[BanService, ListenerManager, PluginManager, dict]:
    settings = load_startup_settings(paths)
    service = BanService(paths)
    listeners = ListenerManager(service, settings)
    plugins = PluginManager(
        paths.data_dir / "plugins",
        paths.cache_dir / "plugins",
        service.signals.log.emit,
        paths.config_dir / "plugins.json",
    )
    service.signals.settings_changed.connect(listeners.apply)
    return service, listeners, plugins, settings


def run(paths: AppPaths | None = None, *, auto_quit_ms: int | None = None, enforce_single_instance: bool = True) -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("BanHelper")
    app.setOrganizationName("BanHelper")
    app.setWindowIcon(QIcon(str(application_icon())))
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())
    instance = SingleInstance("BanHelper-2-main") if enforce_single_instance else None
    if instance is not None and not instance.acquire():
        return 0
    app_paths = paths or AppPaths.discover()
    try:
        if not fabric_jar().is_file():
            raise FileNotFoundError(f"Fabric-мод не найден в ресурсах приложения: {fabric_jar()}")
        app_paths.ensure()
        configure_logging(app_paths.logs_dir)
        service, listeners, plugins, _settings = create_runtime(app_paths)
    except Exception as exc:
        shutdown_logging()
        if instance is not None:
            instance.release()
        QMessageBox.critical(None, "BanHelper не запущен", str(exc))
        return 2

    runtime = Runtime(app_paths, service, listeners, plugins)
    listener_ok = False
    service_ok = False
    exit_code = 3
    try:
        window = MainWindow(service, app_paths, listeners)
        attach_plugin_menu(window, plugins)
        if instance is not None:
            instance.activation_requested.connect(window.activate)
        listeners.changed.connect(lambda ok, host, port, error: window.fabric_panel.set_running(host, port) if ok else window.fabric_panel.set_error(error))
        service.start()
        QTimer.singleShot(150, lambda: window.fabric_panel.set_running(listeners.listener.host, listeners.listener.port) if listeners.listener and listeners.listener.running else None)
        metrics = QTimer()
        metrics.setInterval(1000)
        metrics.timeout.connect(lambda: window.fabric_panel.update_metrics(*listeners.metrics()))
        metrics.start()
        window.show()
        if auto_quit_ms is not None:
            QTimer.singleShot(max(100, int(auto_quit_ms)), app.quit)
        exit_code = app.exec()
    finally:
        runtime.request_stop()
        listener_ok, service_ok = runtime.wait()
        if instance is not None:
            instance.release()
        shutdown_logging()

    if not listener_ok or not service_ok:
        return 3
    return exit_code
