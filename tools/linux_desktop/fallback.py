"""Exercise Qt's actual xdg-open fallback on a disconnected private session bus."""

from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path

from PySide6.QtDBus import QDBusConnection
from PySide6.QtWidgets import QApplication

from je_file_tree.gui.file_actions import reveal_in_file_manager


def main() -> int:
    """Open the containing folder through an owned logging xdg-open executable."""
    if sys.platform != "linux" or len(sys.argv) != 1:
        raise ValueError("Fallback probe accepts only its private Linux container fixture")
    scratch = Path(os.environ["HOME"])
    info = scratch.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Fallback probe requires an owned private scratch directory")
    target, record = str(scratch / "備援 資料,夾" / "test.txt"), scratch / "xdg-open.json"
    app = QApplication([])
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
