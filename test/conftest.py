"""Shared fixtures. Qt tests run on the offscreen platform so they need no display."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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
