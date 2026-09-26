"""Things the user can do with an entry: open it, show it in the file manager, copy its path, move it to the trash.

Explorer splits its command line at commas and ``=``, and only a field in
double quotes may hold them, while ``subprocess`` quotes an argument only when
it has a space; so the Windows command line is built with the path always
quoted (a Windows path cannot contain a quote itself).

On Linux and the BSDs the desktop's file manager is asked over D-Bus
(``org.freedesktop.FileManager1.ShowItems``, which Nautilus, Dolphin, Nemo, Caja
and Thunar answer) to show the entry selected; without a session bus or such a
file manager, the folder is opened instead.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - fixed file-manager commands around a local path
import sys

from PySide6.QtCore import QFile, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication

try:
    from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
except ImportError:  # a PySide6 build without QtDBus: the folder is opened instead
    QDBusConnection = None  # type: ignore[assignment,misc]

_FILE_MANAGER = ("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1")
_DBUS_TIMEOUT_MS = 3000


def explorer_command(path: str) -> str:
    """The ``explorer`` command line that opens a window with ``path`` selected."""
    return f'explorer /select,"{os.path.normpath(path)}"'


def open_path(path: str) -> bool:
    """Open a file with its default program, or a folder in the file manager."""
    return QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def reveal_in_file_manager(path: str) -> bool:
    """Show ``path`` selected in the system file manager (its folder, where selecting is not possible)."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(explorer_command(path))  # noqa: S603 # nosec B603 - no shell, quoted local path
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])  # noqa: S603,S607 # nosec B603,B607 - fixed program
            return True
    except OSError:
        return False
    return show_items(path) or open_path(os.path.dirname(path) or path)


def show_items(path: str) -> bool:
    """Ask the desktop's file manager over D-Bus to show ``path`` selected; False when nothing answered."""
    if QDBusConnection is None:
        return False
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    interface = QDBusInterface(*_FILE_MANAGER, bus)
    if not interface.isValid():
        return False
    interface.setTimeout(_DBUS_TIMEOUT_MS)
    reply = interface.call("ShowItems", [QUrl.fromLocalFile(path).toString()], "")
    return reply.type() != QDBusMessage.MessageType.ErrorMessage


def copy_path(path: str) -> None:
    """Put ``path`` on the clipboard."""
    QGuiApplication.clipboard().setText(path)


def move_to_trash(path: str) -> bool:
    """Move a file or folder to the Recycle Bin / Trash; False when the system refused."""
    return bool(QFile.moveToTrash(path))
