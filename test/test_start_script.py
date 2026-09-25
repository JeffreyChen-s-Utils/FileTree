"""``start_file_tree.py`` (what Nuitka compiles) starts the same application as ``python -m file_tree``."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from file_tree.gui import app

_ROOT = Path(__file__).resolve().parents[1]


def test_the_start_script_runs_the_application_entry_point(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(_ROOT))
    sys.modules.pop("start_file_tree", None)
    module = importlib.import_module("start_file_tree")  # importing must not open a window
    assert module.run is app.run
    assert importlib.import_module("file_tree.__main__").run is app.run
