"""Choosing an explicit duplicate keeper preserves the captured list and checks the new decision."""

from __future__ import annotations

import threading

import pytest
from PySide6.QtCore import QItemSelectionModel, QPersistentModelIndex, Qt

from je_file_tree.core.duplicates import DuplicateGroup, DuplicateResult, DuplicateSavings
from je_file_tree.core.node import Node
from je_file_tree.core.savings import Savings
from je_file_tree.gui import duplicate_savings_worker
from je_file_tree.gui.duplicates_panel import DuplicatesPanel
from je_file_tree.gui.tree_model import NODE_ROLE
from test_gui import _wait


@pytest.fixture
def panel(qapp):
    root = Node("captured", True, children=[])
    groups = []
    for number in range(3):
        files = [Node(f"{number}-{row:04}", False, size=10, modified=row, parent=root) for row in range(120)]
        root.children.extend(files)
        groups.append(DuplicateGroup(10, list(reversed(files)), kept=files[0]))
    widget = DuplicatesPanel()
    widget.setAttribute(Qt.WA_DontShowOnScreen)
    widget.resize(900, 450)
    widget._root, widget._groups = root, list(groups)
    widget._found = DuplicateResult(groups, 360, 3600, 0)
    value = Savings(1190, 4096, 0, 4096, 1000, False)
    widget._savings = DuplicateSavings(value, [value] * 3, [None] * 3)
    widget._rebuild()
    widget._update()
    widget.show()
    yield widget
    widget.stop(wait=True)
    widget.close()


@pytest.mark.parametrize("position", [90, 119])
def test_choose_keeper_preserves_view_and_rechecks_the_updated_decision(panel, qapp, monkeypatch, position):
    started, release = threading.Event(), threading.Event()
    checked = []

    def blocked(*_args, **_kwargs):
        started.set()
        assert release.wait(10)
        return DuplicateSavings(Savings(3570, 4096, 0, 4096, 1000, False), [], [])

    monkeypatch.setattr(duplicate_savings_worker, "estimate_duplicate_savings", blocked)
    monkeypatch.setattr(duplicate_savings_worker, "check_group",
                        lambda group, *_args, **_kwargs: checked.append(group) or None)
    parent = panel.model.index(2, 0)
    current = panel.model.index(position, 2, parent)
    chosen = current.data(NODE_ROLE)
    old = panel.groups[2].kept
    selection = panel.view.selectionModel()
    selection.setCurrentIndex(current, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
    pinned = QPersistentModelIndex(current)
    panel.view.collapse(panel.model.index(0, 0))
    panel.view.setColumnWidth(0, 317)
    panel.view.scrollTo(current)
    qapp.processEvents()
    scroll = panel.view.verticalScrollBar().value()
    resets = []
    panel.model.modelReset.connect(lambda: resets.append(True))
    try:
        panel.choose_kept_copy()
        _wait(qapp, started.is_set)
        assert [index.data(NODE_ROLE) for index in selection.selectedRows()] == [chosen]
        assert pinned.isValid() and selection.currentIndex() == pinned and not resets
        assert panel.groups[2].kept is chosen and panel._savings is None
        assert panel.running and not panel.select_extra.isEnabled()
        assert not panel.view.isExpanded(panel.model.index(0, 0)) and panel.view.isExpanded(parent)
        assert panel.view.columnWidth(0) == 317
        assert panel.view.verticalScrollBar().value() == min(scroll, panel.view.verticalScrollBar().maximum()) > 0
        _assert_keeper_roles(panel, old, chosen, position)
        assert panel._found.groups[2].kept is old
        assert all(panel.model.index(row, 0).data() == panel._group_title(row, group)
                   for row, group in enumerate(panel.groups))
        release.set()
        _wait(qapp, lambda: not panel.running)
        assert checked == panel.groups and checked[2].kept is chosen and panel.select_extra.isEnabled()
        assert [index.data(NODE_ROLE) for index in selection.selectedRows()] == [chosen]
        panel.select_extra_copies()
        assert chosen not in [index.data(NODE_ROLE) for index in selection.selectedRows()]
        assert old in [index.data(NODE_ROLE) for index in selection.selectedRows()]
        assert selection.currentIndex() == pinned
    finally:
        release.set()
        panel.stop(wait=True)


def _assert_keeper_roles(panel: DuplicatesPanel, old: Node, chosen: Node, position: int) -> None:
    parent = panel.model.index(2, 0)
    first, last = panel.model.index(0, 0, parent), panel.model.index(position, 0, parent)
    assert first.data(NODE_ROLE) is old and first.data() == old.name and first.data(Qt.FontRole) is None
    assert last.data(NODE_ROLE) is chosen and last.data() != chosen.name and last.data(Qt.FontRole).bold()
