"""Shared fixtures. Qt tests run on the offscreen platform so they need no display."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from je_file_tree.gui import elevation

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def no_administrator_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Fail any test that reaches the real UAC prompt (it would wait on the desktop of whoever runs the tests).

    A test that needs an answer replaces ``elevation.relaunch_elevated``; the prompt itself counts as declined.
    """
    reached: list[str] = []
    from je_file_tree.gui import main_window
    from je_file_tree.core import trash_size

    emptied: list[str] = []
    if os.name == "nt":
        def forbid_live_empty(_window, root, _flags):
            emptied.append(root)
            raise AssertionError("Tests cannot empty a real user Recycle Bin")
        monkeypatch.setattr(trash_size._shell32(), "SHEmptyRecycleBinW", forbid_live_empty)

    monkeypatch.setattr(main_window, "journal_folder", lambda: tmp_path / "journal")
    monkeypatch.setattr(elevation, "run_as_admin",
                        lambda program, _parameters, _folder: reached.append(program) and False)
    yield
    assert not reached, f"a test brought up the real administrator prompt for {reached}"
    assert not emptied, f"a test tried to empty a real user Recycle Bin for {emptied}"


def make_tree(root: Path, spec: dict) -> None:
    """Create files and folders from a nested dict: a str or bytes value is a file, a dict a folder."""
    for name, content in spec.items():
        path = root / name
        if isinstance(content, dict):
            path.mkdir()
            make_tree(path, content)
        elif isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """A small folder tree with known sizes (total 1,000 bytes in 6 files and 3 folders)."""
    root = tmp_path / "sample"
    root.mkdir()
    make_tree(root, {
        "big.bin": b"x" * 500,
        "notes.txt": b"n" * 100,
        "photos": {"a.jpg": b"j" * 200, "b.png": b"p" * 50},
        "code": {"main.py": b"c" * 100, "empty": {}, "Makefile": b"m" * 50},
    })
    return root


@pytest.fixture(scope="session")
def qapp():
    """The one QApplication of the test session."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
