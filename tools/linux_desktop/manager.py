"""A separate strict (as, s) FileManager1 service on a real private session bus."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import ClassInfo, QCoreApplication, QObject, Slot
from PySide6.QtDBus import QDBusConnection
from je_file_tree.core.export import _atomic_file


@ClassInfo(**{"D-Bus Interface": "org.freedesktop.FileManager1"})
class FileManager(QObject):
    """Record only calls that Qt's native D-Bus signature checker accepts as a string array and string."""

    def __init__(self, output: Path) -> None:
        super().__init__()
        self.output = output

    @Slot("QStringList", "QString")
    def ShowItems(self, uris: list[str], startup_id: str) -> None:  # noqa: N802 - D-Bus interface method
        """Record the successful typed call for the client probe."""
        with _atomic_file(self.output, encoding="utf-8") as stream:
            json.dump({"uris": uris, "startup_id": startup_id}, stream)


def main() -> int:
    """Own the standard service name inside this test's session bus until the parent terminates us."""
    app = QCoreApplication([])
    output = Path(sys.argv[1])
    manager = FileManager(output)
    bus = QDBusConnection.sessionBus()
    if not bus.registerService("org.freedesktop.FileManager1"):
        raise RuntimeError(bus.lastError().message())
    if not bus.registerObject("/org/freedesktop/FileManager1", manager,
                              QDBusConnection.RegisterOption.ExportAllSlots):
        raise RuntimeError(bus.lastError().message())
    with _atomic_file(output.with_suffix(".ready"), encoding="utf-8") as stream:
        stream.write("ready")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
