"""The icon: drawn at every size, packed into a valid .ico, used by the window and the build."""

from __future__ import annotations

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
])
def test_the_build_writes_and_passes_the_icon(qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                              platform: str, option: str, file: str) -> None:
    build = _build_script()
    monkeypatch.setattr(sys, "platform", platform)
    options = build.icon_options(tmp_path, [])
    assert options == [f"{option}{tmp_path / file}"]
    assert (tmp_path / file).stat().st_size > 0


def test_the_build_leaves_macos_and_an_icon_given_by_hand_alone(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    build = _build_script()
    monkeypatch.setattr(sys, "platform", "darwin")
    assert build.icon_options(tmp_path, []) == []
    monkeypatch.setattr(sys, "platform", "win32")
    assert build.icon_options(tmp_path, ["--windows-icon-from-ico=mine.ico"]) == []
    assert list(tmp_path.iterdir()) == []
