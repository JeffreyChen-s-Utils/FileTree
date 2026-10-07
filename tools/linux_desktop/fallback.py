"""Exercise Qt's actual xdg-open fallback on a disconnected private session bus."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtDBus import QDBusConnection
from PySide6.QtWidgets import QApplication

from je_file_tree.gui.file_actions import reveal_in_file_manager


def main() -> int:
    """Open the containing folder through an owned logging xdg-open executable."""
    app = QApplication([])
    target, record = sys.argv[1], Path(sys.argv[2])
    if QDBusConnection.sessionBus().isConnected():
        raise RuntimeError("Fallback probe must have no connected session bus")
    if not reveal_in_file_manager(target):
        raise RuntimeError("Native QDesktopServices fallback was rejected")
    deadline = time.monotonic() + 10
    while not record.exists():
        if time.monotonic() > deadline:
            raise RuntimeError("Native xdg-open fallback was not invoked")
        app.processEvents()
        time.sleep(.01)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
