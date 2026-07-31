from __future__ import annotations

import threading
import weakref

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_local_instances: dict[str, weakref.ReferenceType["SingleInstance"]] = {}
_local_instances_lock = threading.Lock()


class SingleInstance(QObject):
    activation_requested = Signal()

    def __init__(self, name: str = "BanHelper-2-main"):
        super().__init__()
        self.name = name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._receive)

    def acquire(self) -> bool:
        primary = self._local_primary()
        if primary is not None and primary is not self:
            QTimer.singleShot(0, primary.activation_requested.emit)
            return False
        if self.server.isListening():
            return True
        if self.server.listen(self.name):
            self._register_local()
            return True
        socket = QLocalSocket(self)
        socket.connectToServer(self.name)
        if socket.waitForConnected(300):
            socket.write(b"activate")
            socket.flush()
            socket.waitForBytesWritten(300)
            socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.name)
        acquired = self.server.listen(self.name)
        if acquired:
            self._register_local()
        return acquired

    def release(self) -> None:
        if self.server.isListening():
            self.server.close()
        with _local_instances_lock:
            reference = _local_instances.get(self.name)
            if reference is not None and reference() is self:
                _local_instances.pop(self.name, None)

    def _local_primary(self) -> "SingleInstance | None":
        with _local_instances_lock:
            reference = _local_instances.get(self.name)
            primary = reference() if reference is not None else None
            if reference is not None and primary is None:
                _local_instances.pop(self.name, None)
            return primary

    def _register_local(self) -> None:
        with _local_instances_lock:
            _local_instances[self.name] = weakref.ref(self)

    def _receive(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.readyRead.connect(lambda s=socket: self._activate(s))
            if socket.bytesAvailable():
                self._activate(socket)

    def _activate(self, socket: QLocalSocket) -> None:
        if socket.readAll():
            self.activation_requested.emit()
        socket.disconnectFromServer()
