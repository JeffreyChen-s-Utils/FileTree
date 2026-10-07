"""Replacing a tree discards late duplicate estimates and cancellation leaves extras unselected."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtWidgets import QApplication

from je_file_tree.core.duplicates import DuplicateResult, DuplicateSavings
from je_file_tree.core.savings import Savings
from je_file_tree.core.scanner import scan
from je_file_tree.gui import duplicate_savings_worker
from je_file_tree.gui.duplicates_panel import DuplicatesPanel
from test_gui import _wait


def test_late_estimate_is_ignored_after_root_replacement(qapp: QApplication, tmp_path: Path, monkeypatch) -> None:
    started, release = threading.Event(), threading.Event()
    value = DuplicateSavings(Savings(10, 4096, 0, 4096, 1000, False), [])

    def blocked(*_args, **_kwargs):
        started.set()
        assert release.wait(5)
        return value  # deliberately ignores cancellation to exercise the late-signal guard

    monkeypatch.setattr(duplicate_savings_worker, "estimate_duplicate_savings", blocked)
    from je_file_tree.core.duplicates import DuplicateGroup
    from je_file_tree.core.node import Node

    root = scan(tmp_path).root
    first = Node("first", False, size=10, parent=root)
    extra = Node("extra", False, size=10, parent=root)
    panel = DuplicatesPanel()
    try:
        panel.set_root(root)
        panel._show_result(DuplicateResult([DuplicateGroup(10, [first, extra])], 2, 20, 0))
        _wait(qapp, started.is_set)
        assert panel.running and not panel.select_extra.isEnabled()
        panel.select_extra_copies()
        assert not panel.view.selectionModel().selectedRows()
        panel.set_root(None)
        release.set()
        _wait(qapp, lambda: not panel._estimate_workers)
        assert not panel.groups and panel._savings is None and not panel.running
    finally:
        release.set()
        panel.stop(wait=True)
        panel.close()
