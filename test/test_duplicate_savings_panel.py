"""Replacing a tree discards late duplicate estimates and cancellation leaves extras unselected."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QItemSelectionModel, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QApplication

from je_file_tree.core.duplicates import DuplicateGroup, DuplicateResult, DuplicateSavings
from je_file_tree.core.node import Node
from je_file_tree.core.savings import Savings
from je_file_tree.core.scanner import scan
from je_file_tree.gui import duplicate_savings_worker
from je_file_tree.gui.duplicates_panel import LISTED_GROUPS, DuplicatesPanel
from je_file_tree.gui.tree_model import NODE_ROLE
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


def _captured_groups(group_count: int = 3, members: int = 120) -> tuple[Node, list[DuplicateGroup]]:
    root = Node("captured", True, children=[])
    groups = []
    for number in range(group_count):
        files = [Node(f"{number}-{row:04}", False, size=10, modified=row, parent=root) for row in range(members)]
        root.children.extend(files)
        groups.append(DuplicateGroup(10, files, kept=files[0]))
    return root, groups


def test_finishing_estimate_preserves_selection_current_row_and_view_state(qapp, monkeypatch) -> None:
    started, release = threading.Event(), threading.Event()
    root, groups = _captured_groups()
    value = Savings(1190, 4096, 0, 4096, 1000, False)
    savings = DuplicateSavings(value, [value] * 3, [None, "protected", None])

    def blocked(*_args, **_kwargs):
        started.set()
        assert release.wait(10)
        return savings

    monkeypatch.setattr(duplicate_savings_worker, "estimate_duplicate_savings", blocked)
    monkeypatch.setattr(duplicate_savings_worker, "check_group",
                        lambda group, *_args, **_kwargs: "protected" if group is groups[1] else None)
    panel = DuplicatesPanel()
    panel.setAttribute(Qt.WA_DontShowOnScreen)
    panel.resize(900, 450)
    try:
        panel.set_root(root)
        panel.show()
        panel._show_result(DuplicateResult(groups, 360, 3600, 0))
        _wait(qapp, started.is_set)
        parent = panel.model.index(2, 0)
        current = panel.model.index(119, 2, parent)
        selection = panel.view.selectionModel()
        selection.setCurrentIndex(current, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        pinned = QPersistentModelIndex(current)
        panel.view.collapse(panel.model.index(0, 0))
        panel.view.setColumnWidth(0, 317)
        panel.view.scrollTo(current)
        qapp.processEvents()
        scroll = panel.view.verticalScrollBar().value()
        titles = [panel.model.index(row, 0).data() for row in range(3)]
        resets = []
        panel.model.modelReset.connect(lambda: resets.append(True))
        release.set()
        _wait(qapp, lambda: not panel.running)
        assert [index.data(NODE_ROLE) for index in selection.selectedRows()] == [groups[2].files[-1]]
        assert pinned.isValid() and selection.currentIndex() == pinned
        assert not resets and panel.view.selectionModel() is selection
        assert not panel.view.isExpanded(panel.model.index(0, 0))
        assert panel.view.isExpanded(parent) and panel.view.columnWidth(0) == 317
        assert scroll > 0 and panel.view.verticalScrollBar().value() == scroll
        for row in range(3):
            header = panel.model.index(row, 0)
            assert header.data() != titles[row] and header.data(Qt.ToolTipRole) == header.data()
            assert header.data(NODE_ROLE) is None and panel.model.rowCount(header) == 120
            assert panel.model.index(0, 0, header).data(Qt.FontRole).bold()
        assert panel.select_extra.isEnabled() and panel._savings == savings
    finally:
        release.set()
        panel.stop(wait=True)
        panel.close()


@pytest.mark.parametrize("count", [0, 1, LISTED_GROUPS + 1])
def test_estimate_labels_follow_the_displayed_group_bound(qapp, count) -> None:
    root, groups = _captured_groups(count, 2)
    panel = DuplicatesPanel()
    try:
        panel._root, panel._groups = root, groups
        panel._rebuild()
        value = Savings(10, 4096, 0, 4096, 1000, False)
        shown = min(count, LISTED_GROUPS)
        panel._show_savings(DuplicateSavings(value, [value] * shown, [None] * shown))
        assert panel.model.rowCount() == shown and len(panel.groups) == count
        for row in range(shown):
            parent = panel.model.index(row, 0)
            assert parent.data() == panel._group_title(row, groups[row])
            assert parent.data(Qt.ToolTipRole) == parent.data()
            assert panel.model.rowCount(parent) == 2
            assert panel.model.index(1, 0, parent).data(NODE_ROLE) is groups[row].files[1]
    finally:
        panel.stop(wait=True)
        panel.close()
