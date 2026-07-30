from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    activation_requested = Signal()

    def __init__(self, name: str = "BanHelper-2-main"):
        super().__init__()
        self.name = name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._receive)

    def acquire(self) -> bool:
        if self.server.listen(self.name):
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
        return self.server.listen(self.name)

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
