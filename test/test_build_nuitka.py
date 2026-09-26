"""``tools/build_nuitka.py`` builds the Nuitka command, Qt's translation catalogues included."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from je_file_tree.gui.qt_translation import CATALOGUES

_SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "build_nuitka.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_nuitka", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_command_copies_every_qt_catalogue_and_ends_with_the_entry_point() -> None:
    build = _load()
    command = build.nuitka_command("standalone", ["--windows-icon-from-ico=icon.ico"])
    assert "--mode=standalone" in command and "--enable-plugin=pyside6" in command
    assert "--output-filename=FileTree" in command
    assert "--output-dir=build/standalone" in command
    copies = [option for option in command if option.startswith("--include-data-files=")]
    assert len(copies) == len(CATALOGUES)
    for catalogue in CATALOGUES.values():
        source, target = next(option for option in copies if catalogue in option).split("=", 1)[1].rsplit("=", 1)
        assert Path(source).is_file()
        # PySide6/translations on Windows, PySide6/Qt/translations on Linux.
        assert target.startswith("PySide6/") and target.endswith(f"translations/{catalogue}.qm")
    assert command[-2] == "--windows-icon-from-ico=icon.ico"
    assert command[-1].endswith("start_file_tree.py")
    assert Path(command[-1]).is_file()


def test_modes() -> None:
    build = _load()
    onefile = build.nuitka_command("onefile", [])
    assert "--mode=onefile" in onefile and "--output-dir=build/onefile" in onefile
    assert "--macos-app-name=FileTree" in build.nuitka_command("app", [])
    assert "--macos-app-name=FileTree" not in build.nuitka_command("standalone", [])


def test_the_catalogues_keep_their_place_relative_to_the_package(tmp_path: Path) -> None:
    translations = tmp_path / "PySide6" / "Qt" / "translations"
    translations.mkdir(parents=True)
    for catalogue in CATALOGUES.values():
        (translations / f"{catalogue}.qm").write_bytes(b"")
    options = _load().translation_options(translations, tmp_path)
    assert [option.rsplit("=", 1)[1] for option in options] == [
        f"PySide6/Qt/translations/{catalogue}.qm" for catalogue in CATALOGUES.values()]


def test_a_missing_catalogue_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="qtbase_zh"):
        _load().translation_options(tmp_path, tmp_path)
