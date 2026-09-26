"""FileTree's icon: a small treemap, drawn in code so no image file has to ship.

``app_icon()`` gives the window and taskbar icon; ``ico_bytes()`` packs the same
pictures into a Windows ``.ico`` for the Nuitka build (``tools/build_nuitka.py``).
"""

from __future__ import annotations

import ctypes
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap

from je_file_tree.gui.treemap_widget import CATEGORY_COLOURS

SIZES = (16, 24, 32, 48, 64, 128, 256)
APP_USER_MODEL_ID = "JE-Chen.FileTree"
_S_OK = 0

# (x, y, width, height) in a unit square and the file-type colour of each block:
# one big block and a column of smaller ones, the way a treemap of a real disk looks.
_BLOCKS = (
    ((0.00, 0.00, 0.56, 1.00), "programs"),
    ((0.56, 0.00, 0.44, 0.46), "video"),
    ((0.56, 0.46, 0.24, 0.54), "images"),
    ((0.80, 0.46, 0.20, 0.30), "documents"),
    ((0.80, 0.76, 0.20, 0.24), "archives"),
)
_BACKGROUND = "#2b2f36"
_ICO_FULL_SIDE = 256  # an .ico entry writes 0 for this size


def draw(size: int) -> QImage:
    """The icon as a ``size`` × ``size`` picture with a transparent corner."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    outer = QRectF(0, 0, size, size)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(_BACKGROUND))
    painter.drawRoundedRect(outer, size * 0.18, size * 0.18)
    margin = max(1.0, size * 0.10)
    gap = max(1.0, size * 0.035)
    inner = outer.adjusted(margin, margin, -margin, -margin)
    for (x, y, width, height), category in _BLOCKS:
        block = QRectF(inner.x() + x * inner.width(), inner.y() + y * inner.height(),
                       width * inner.width(), height * inner.height()).adjusted(0, 0, -gap, -gap)
        painter.setBrush(QColor(CATEGORY_COLOURS[category]))
        painter.drawRoundedRect(block, size * 0.03, size * 0.03)
    painter.end()
    return image


def claim_taskbar_button() -> bool:
    """Give this process FileTree's own Windows AppUserModelID; True when set, False elsewhere.

    Run from Python (``je-file-tree``, ``start_file_tree.py``), the process is ``python.exe`` or
    ``pythonw.exe``, and Windows groups its windows under Python's taskbar button with Python's icon.
    With an ID of its own FileTree gets its own button, showing the window icon. Call it before the
    first window is created; the compiled ``FileTree.exe`` gets the same grouping.
    """
    if sys.platform != "win32":
        return False
    set_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    set_id.argtypes = [ctypes.c_wchar_p]
    set_id.restype = ctypes.c_long  # an HRESULT
    return set_id(APP_USER_MODEL_ID) == _S_OK


def app_icon() -> QIcon:
    """The window and taskbar icon, in every size of ``SIZES``."""
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(QPixmap.fromImage(draw(size)))
    return icon


def png_bytes(image: QImage) -> bytes:
    """``image`` encoded as PNG."""
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data.data())


def ico_bytes(sizes: tuple[int, ...] = SIZES) -> bytes:
    """A Windows ``.ico`` holding the icon at every size, each stored as PNG (Windows Vista and later).

    Layout: a 6-byte header (reserved, type 1 = icon, count), one 16-byte entry
    per picture (width and height with 0 meaning 256, colours, reserved,
    planes, bits per pixel, byte count, offset), then the PNG data.
    """
    pictures = [(size, png_bytes(draw(size))) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(pictures))
    offset = len(header) + 16 * len(pictures)
    entries = b""
    for size, data in pictures:
        side = 0 if size >= _ICO_FULL_SIDE else size
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(data for _, data in pictures)
