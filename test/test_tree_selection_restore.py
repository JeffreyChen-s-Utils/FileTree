"""Restore large visible selections once, excluding display-only archive rows."""

import pytest
from PySide6.QtCore import QItemSelection, QItemSelectionModel
from test_gui import _wait, window as window  # noqa: PLC0414 - shared fixture

from je_file_tree.core.analysis import category_stats, summarise
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanResult
from je_file_tree.gui.scan_worker import ScanOutcome
from je_file_tree.gui.tree_model import NODE_ROLE, FolderTreeModel


class _ProbedRows(list):
    visited = 0

    def __iter__(self):
        for entry in super().__iter__():
            self.visited += 1
            yield entry

    def index(self, target):
        for row, entry in enumerate(self):
            if entry is target:
                return row
        raise ValueError("Missing captured entry")


def _outcome(count):
    root = Node("captured-selection-fixture", True, children=[], file_count=count)
    root.children.extend(Node(f"file-{number:04d}", False, size=count-number, file_count=1, parent=root)
                         for number in range(count))
    root.size = sum(node.size for node in root.children)
    summary = summarise(root, now=1_800_000_000)
    return ScanOutcome(ScanResult(root, [], 0), summary.largest, summary.extensions,
                       category_stats(summary.extensions), summary.ages, summary.now)


def test_bulk_index_lookup_is_linear_and_preserves_order_and_invalid_positions(qapp):
    root = _outcome(2000).result.root
    root.children = _ProbedRows(root.children)
    chosen = root.children[::25]
    foreign = Node("foreign", True, children=[])
    other = Node("other", False, parent=foreign)
    foreign.children.append(other)
    model = FolderTreeModel()
    model.set_root(root)
    indexes = model.indexes_for([*chosen, root, other, chosen[0]])
    assert [index.data(NODE_ROLE) for index in indexes[:len(chosen)]] == chosen
    assert indexes[-3].data(NODE_ROLE) is root and not indexes[-2].isValid()
    assert indexes[-1].data(NODE_ROLE) is chosen[0]
    assert root.children.visited <= 2*len(root.children), "one requested sibling pass, not one search per file"
    assert len(model._rows) <= len(chosen) + 1
    model.deleteLater()


def test_filter_switch_applies_one_selection_change_for_the_whole_visible_batch(window, qapp):
    results = window.results
    outcome = _outcome(400)
    results.show_outcome(outcome)
    root = outcome.result.root
    chosen = root.children[::5]
    picked = QItemSelection()
    for node in chosen:
        index = results.tree_model.index_for(node)
        picked.select(index, index)
    flags = QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
    results.tree.selectionModel().select(picked, flags)
    results.tree.selectionModel().setCurrentIndex(results.tree_model.index_for(chosen[0]),
                                                 QItemSelectionModel.SelectionFlag.NoUpdate)
    changes = []
    results.tree_filter.selection_model_changed.connect(
        lambda: results.tree.selectionModel().selectionChanged.connect(lambda *_args: changes.append(True)))
    controller = results.tree_filter
    controller.line.setText("file-")
    _wait(qapp, lambda: not controller.timer.isActive() and not controller._workers)
    assert len(changes) == 1, "restore the complete row selection in one update"
    assert set(results.selected_nodes()) == set(chosen) and results.selected_node() is chosen[0]
    expected = {(node, column) for node in chosen for column in range(results.tree_model.columnCount())}
    assert {(index.data(NODE_ROLE), index.column())
            for index in results.tree.selectionModel().selectedIndexes()} == expected
    changes.clear()
    controller.line.clear()
    assert len(changes) == 1 and set(results.selected_nodes()) == set(chosen)
    assert results.selected_node() is chosen[0]


@pytest.mark.parametrize("with_file", [False, True])
def test_switch_with_selected_virtual_preview_never_treats_it_as_a_filesystem_entry(window, with_file):
    results = window.results
    outcome = _outcome(3)
    results.show_outcome(outcome)
    root = outcome.result.root
    archive, kept = root.children[:2]
    virtual = VirtualEntry("preview", False, size=999999, member="preview", parent=archive)
    results.tree_model.set_archive(archive, [virtual])
    picked = QItemSelection()
    for node in ((virtual, kept) if with_file else (virtual,)):
        index = results.tree_model.index_for(node)
        picked.select(index, index)
    results.tree.selectionModel().select(picked, QItemSelectionModel.SelectionFlag.ClearAndSelect
                                        | QItemSelectionModel.SelectionFlag.Rows)
    controller = results.tree_filter
    controller.proxy.allowed = frozenset(id(node) for node in root.children)
    controller.proxy.setSourceModel(results.tree_model)
    controller._switch(True)
    assert results.selected_nodes() == ([kept] if with_file else [])
    controller._switch(False)
    assert results.selected_nodes() == ([kept] if with_file else [])
    assert virtual.parent is archive and archive.children == () and root.size == 6
    assert virtual not in root.children and virtual.is_dir is False


