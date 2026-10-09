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


def test_user_can_keep_a_newer_copy_and_pruning_never_chooses_a_replacement(qapp, tmp_path) -> None:
    import os

    for name in ("old", "new", "third"):
        (tmp_path / name).write_bytes(b"same contents")
    os.utime(tmp_path / "old", (1_600_000_000, 1_600_000_000))
    root = scan(tmp_path).root
    panel = DuplicatesPanel()
    try:
        panel.set_root(root)
        panel.min_size.setCurrentIndex(0)
        panel.start()
        _wait(qapp, lambda: not panel.running)
        assert not panel.select_extra.isEnabled()
        parent = panel.model.index(0, 0)
        row = next(index for index in range(panel.model.rowCount(parent))
                   if panel.model.index(index, 0, parent).data() == "new")
        panel.view.setCurrentIndex(panel.model.index(row, 0, parent))
        panel.choose_kept_copy()
        _wait(qapp, lambda: not panel.running)
        keeper = panel.groups[0].kept
        assert keeper.name == "new" and keeper.path in panel.model.index(0, 0).data()
        panel.select_extra_copies()
        from je_file_tree.gui.tree_model import NODE_ROLE

        selected = [index.data(NODE_ROLE).name for index in panel.view.selectionModel().selectedRows()]
        assert set(selected) == {"old", "third"}
        root.children.remove(keeper)
        keeper.parent = None
        panel.prune()
        _wait(qapp, lambda: not panel.running)
        assert panel.groups[0].kept is None and not panel.select_extra.isEnabled()
    finally:
        panel.stop(wait=True)
        panel.close()
