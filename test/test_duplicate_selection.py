"""Bulk duplicate selection replaces the view once and keeps explicit keepers excluded."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel

from je_file_tree.core.duplicates import DuplicateGroup, DuplicateSavings
from je_file_tree.core.node import Node
from je_file_tree.core.savings import Savings
from je_file_tree.gui.duplicates_panel import DuplicatesPanel
from je_file_tree.gui.tree_model import NODE_ROLE


@pytest.fixture
def panel(qapp):
    """Synthetic captured results only; no search, estimate or source operation is started."""
    widget = DuplicatesPanel()
    yield widget
    widget._estimator = None
    widget.stop(wait=True)
    widget.close()


def _show(panel, groups, issues):
    panel._root = Node("captured-root", True)
    panel._groups = groups
    panel._rebuild()
    value = Savings(0, 0, 0, None, None, True)
    panel._savings = DuplicateSavings(value, [value] * len(groups), issues)


def _selected(panel):
    return [index.data(NODE_ROLE) for index in panel.view.selectionModel().selectedRows()]


def test_bulk_selection_is_one_change_and_preserves_the_current_keeper(panel):
    files = [Node(str(i).zfill(3), False, modified=i) for i in range(32)]
    kept = files[16]
    _show(panel, [DuplicateGroup(10, list(reversed(files)), kept=kept)], [None])
    model = panel.view.selectionModel()
    parent = panel.model.index(0, 0)
    current = panel.model.index(16, 0, parent)
    model.setCurrentIndex(current, QItemSelectionModel.SelectionFlag.ClearAndSelect
                          | QItemSelectionModel.SelectionFlag.Rows)
    changes = []
    model.selectionChanged.connect(lambda *_: changes.append(1))
    panel.select_extra_copies()
    assert len(changes) == 1
    assert _selected(panel) == [node for node in files if node is not kept]
    assert len(model.selection()) == 2
    assert model.currentIndex() == current and current.data(NODE_ROLE) is kept


def test_blocked_missing_and_invalid_keeper_groups_never_select_extras(panel):
    groups = []
    for i in range(5):
        nodes = [Node(f"{i}-{j}", False, modified=j) for j in range(3)]
        groups.append(DuplicateGroup(10, nodes, kept=nodes[1]))
    groups[2] = DuplicateGroup(10, groups[2].files, kept=None)
    groups[3] = DuplicateGroup(10, groups[3].files, kept=Node("outsider", False))
    _show(panel, groups, [None, "protected", None, None])
    panel.view.selectionModel().select(panel.model.index(0, 0, panel.model.index(1, 0)),
                                      QItemSelectionModel.SelectionFlag.Select
                                      | QItemSelectionModel.SelectionFlag.Rows)
    panel.select_extra_copies()
    assert _selected(panel) == [groups[0].files[0], groups[0].files[2]]


@pytest.mark.parametrize("state", ["busy", "no_estimate"])
def test_unfinished_results_leave_existing_selection_untouched(panel, state):
    nodes = [Node(str(i), False) for i in range(3)]
    _show(panel, [DuplicateGroup(10, nodes, kept=nodes[1])], [None])
    index = panel.model.index(0, 0, panel.model.index(0, 0))
    model = panel.view.selectionModel()
    model.select(index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    changes = []
    model.selectionChanged.connect(lambda *_: changes.append(1))
    if state == "busy":
        panel._estimator = object()
    else:
        panel._savings = None
    panel.select_extra_copies()
    assert _selected(panel) == [index.data(NODE_ROLE)] and not changes


def test_repeated_keeper_identity_and_every_entry_column_are_excluded(panel):
    kept, first, second = Node("kept", False), Node("a", False), Node("z", False)
    _show(panel, [DuplicateGroup(10, [kept, first, kept, second], kept=kept)], [None])
    panel.select_extra_copies()
    assert _selected(panel) == [first, second]
    assert all(index.data(NODE_ROLE) is not kept for index in panel.view.selectionModel().selectedIndexes())


@pytest.mark.parametrize("position", [0, 10_000, 19_999])
def test_large_captured_selection_reads_no_cell_data_and_uses_at_most_two_ranges(panel, monkeypatch, position):
    files = [Node(str(i), False) for i in range(20_000)]
    kept = files[position]
    panel.model.set_groups([("captured", files)], "auto")
    files.clear()
    def unexpected_data(*_args):
        raise AssertionError("Building selection must use captured identities, not Qt cell data")
    monkeypatch.setattr(panel.model, "data", unexpected_data)
    selection = panel.model.extra_selection({-1: kept, 0: kept, 1: kept})
    assert 1 <= len(selection) <= 2
    assert sum(part.bottom() - part.top() + 1 for part in selection) == 19_999
    assert all(not part.top() <= position <= part.bottom() for part in selection)
    assert all(part.left() == 0 and part.right() == 3 for part in selection)


def test_all_ineligible_groups_clear_manual_selection_in_one_change(panel):
    nodes = [Node(str(i), False) for i in range(3)]
    _show(panel, [DuplicateGroup(10, nodes, kept=nodes[1])], ["changed"])
    selection = panel.view.selectionModel()
    selection.select(panel.model.index(0, 0, panel.model.index(0, 0)),
                     QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    changes = []
    selection.selectionChanged.connect(lambda *_: changes.append(1))
    panel.select_extra_copies()
    assert not _selected(panel) and changes == [1]
