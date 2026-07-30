import sys
import tempfile
from pathlib import Path

from banhelper.app.bootstrap import run
from banhelper.app.paths import AppPaths
from banhelper.infrastructure.database import Database
from banhelper.infrastructure.repositories import BanRepository


if __name__ == "__main__":
    if "--packaging-smoke" in sys.argv:
        sys.argv.remove("--packaging-smoke")
        paths = AppPaths.discover(); paths.ensure()
        connection = Database(paths.database).connect()
        BanRepository(connection).set_settings({"listener_autostart": False, "packaging_smoke": True})
        connection.close()
        raise SystemExit(run(paths, auto_quit_ms=800, enforce_single_instance=False))
    if "--smoke-test" in sys.argv:
        sys.argv.remove("--smoke-test")
        with tempfile.TemporaryDirectory(prefix="banhelper-packaged-smoke-") as root:
            paths = AppPaths.temporary(root); paths.ensure()
            connection = Database(paths.database).connect()
            BanRepository(connection).set_settings({"listener_autostart": False})
            connection.close()
            raise SystemExit(run(paths, auto_quit_ms=800, enforce_single_instance=False))
    raise SystemExit(run())
