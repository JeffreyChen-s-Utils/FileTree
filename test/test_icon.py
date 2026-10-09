"""The icon: drawn at every size, packed into a valid .ico, used by the window and the build."""

from __future__ import annotations

import ctypes
import importlib.util
import struct
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication

from je_file_tree.gui import icon
from je_file_tree.gui.app import create_window

_SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "build_nuitka.py"


def test_every_size_is_drawn_with_a_transparent_corner(qapp: QApplication) -> None:
    for size in icon.SIZES:
        image = icon.draw(size)
        assert (image.width(), image.height()) == (size, size)
        # the rounded corner is see-through; at 16 px anti-aliasing leaves a trace of it
        assert image.pixelColor(0, 0).alpha() < 32
        assert image.pixelColor(size // 3, size // 2).alpha() == 255


def test_the_ico_holds_every_size_and_windows_can_read_it(qapp: QApplication, tmp_path: Path) -> None:
    data = icon.ico_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind, count) == (0, 1, len(icon.SIZES))
    sides = [data[6 + 16 * n] for n in range(count)]
    assert sides == [size if size < 256 else 0 for size in icon.SIZES]
    last_size, last_offset = struct.unpack_from("<II", data, 6 + 16 * (count - 1) + 8)
    assert last_offset + last_size == len(data)
    path = tmp_path / "FileTree.ico"
    path.write_bytes(data)
    assert QImageReader(str(path)).imageCount() == len(icon.SIZES)


def test_the_window_has_the_icon(qapp: QApplication, tmp_path: Path) -> None:
    window = create_window(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    assert not window.windowIcon().isNull()
    window.deleteLater()


def _build_script():
    spec = importlib.util.spec_from_file_location("build_nuitka", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("platform", "option", "file"), [
    ("win32", "--windows-icon-from-ico=", "FileTree.ico"),
    ("linux", "--linux-icon=", "FileTree.png"),
    ("darwin", "--macos-app-icon=", "FileTree.icns"),
])
def test_the_build_writes_and_passes_the_icon(qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                              platform: str, option: str, file: str) -> None:
    build = _build_script()
    monkeypatch.setattr(sys, "platform", platform)
    options = build.icon_options(tmp_path, [])
    assert options == [f"{option}{tmp_path / file}"]
    assert (tmp_path / file).stat().st_size > 0


def test_native_icns_has_four_readable_sizes_and_complete_bounds(qapp: QApplication, tmp_path: Path) -> None:
    data = icon.icns_bytes()
    assert data[:4] == b"icns" and struct.unpack_from(">I", data, 4)[0] == len(data)
    at = 8
    for kind, size in ((b"ic07", 128), (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024)):
        length = struct.unpack_from(">I", data, at + 4)[0]
        assert data[at:at + 4] == kind and data[at + 8:at + 16] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack_from(">II", data, at + 24) == (size, size)
        at += length
    assert at == len(data)
    path = tmp_path / "FileTree.icns"
    path.write_bytes(data)
    reader = QImageReader(str(path))
    assert reader.canRead() and reader.imageCount() == 4
    for index, size in enumerate((128, 256, 512, 1024)):
        assert reader.jumpToImage(index)
        image = reader.read()
        assert image.width() == image.height() == size and image.pixelColor(0, 0).alpha() < 32


@pytest.mark.parametrize("platform, option", [("win32", "--windows-icon-from-ico=mine.ico"),
                                            ("linux", "--linux-icon=mine.png"),
                                            ("darwin", "--macos-app-icon=mine.icns")])
def test_the_build_leaves_an_icon_given_by_hand_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                    platform: str, option: str) -> None:
    build = _build_script()
    monkeypatch.setattr(sys, "platform", platform)
    assert build.icon_options(tmp_path, [option]) == []
    assert list(tmp_path.iterdir()) == []


def test_the_taskbar_button_is_filetree_s_own(monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform != "win32":
        assert icon.claim_taskbar_button() is False
        return
    assert icon.claim_taskbar_button() is True
    shell32 = ctypes.windll.shell32
    value = ctypes.c_wchar_p()
    shell32.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
    shell32.GetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
    assert shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(value)) == 0
    assert value.value == icon.APP_USER_MODEL_ID
    ctypes.windll.ole32.CoTaskMemFree(value)
    monkeypatch.setattr(icon.sys, "platform", "linux")
    assert icon.claim_taskbar_button() is False, "nothing to claim elsewhere"
