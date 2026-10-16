"""Restore large visible selections once, excluding display-only archive rows."""

import pytest
from PySide6.QtCore import QItemSelection, QItemSelectionModel, Qt
from test_gui import _wait, window as window  # noqa: PLC0414 - shared fixture

from je_file_tree.core.analysis import category_stats, summarise
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanResult
from je_file_tree.gui.scan_worker import ScanOutcome
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, SIZE, FolderTreeModel


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


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("column", [NAME, SIZE])
def test_filter_rebinding_keeps_existing_order_without_relayout(window, live, column):
    results = window.results
    outcome = _outcome(40)
    results.show_outcome(outcome)
    root, source = outcome.result.root, results.tree_model
    if live:
        source.set_root(root, live=True)
    results.tree.sortByColumn(column, Qt.SortOrder.DescendingOrder)
    root_index = source.index_for(root)
    results.tree.expand(root_index)
    chosen = root.children[5]
    results.select_node(chosen)
    source.rowCount(root_index)
    cached_order = source._orders.get(id(root))
    results.tree.setColumnWidth(0, 333)
    results.tree.setColumnHidden(6, True)
    controller = results.tree_filter
    controller.proxy.allowed = frozenset(id(node) for node in root.iter_nodes())
    controller.proxy.setSourceModel(source)
    layouts = []
    source.layoutChanged.connect(lambda *_args: layouts.append(True))
    for filtered in (True, False):
        controller._switch(filtered)
        assert not layouts, "rebinding the view must not repeat an unchanged sort"
        assert source._orders.get(id(root)) is cached_order
        assert results.selected_node() is chosen and results.selected_nodes() == [chosen]
        assert results.tree.isExpanded(controller.index_for(root))
        assert results.tree.columnWidth(0) == 333 and results.tree.isColumnHidden(6)
        header = results.tree.header()
        assert header.sortIndicatorSection() == column
        assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder


def test_sort_preservation_keeps_live_rows_frozen_but_allows_new_keys_and_explicit_refresh(qapp):
    root = _outcome(3).result.root
    source = FolderTreeModel()
    source.set_root(root, live=True)
    parent = source.index_for(root)
    assert source.rowCount(parent) == 3
    leaf = Node("a new file", False, size=100, parent=root)
    root.children.append(leaf)
    layouts = []
    source.layoutChanged.connect(lambda *_args: layouts.append(True))
    with source.preserve_sort():
        source.sort(SIZE, Qt.SortOrder.DescendingOrder)
        assert source.rowCount(parent) == 3 and not layouts
        source.refresh()
        assert source.rowCount(parent) == 4 and len(layouts) == 1
        assert source.index(0, 0, parent).data(NODE_ROLE) is leaf
        source.sort(NAME, Qt.SortOrder.AscendingOrder)
        assert len(layouts) == 2 and source.index(0, 0, parent).data(NODE_ROLE) is leaf
        source.sort(NAME, Qt.SortOrder.AscendingOrder)
        assert len(layouts) == 2
    # An ordinary repeated header sort still refreshes a running scan's snapshot.
    another = Node("0 newer file", False, size=200, parent=root)
    root.children.append(another)
    source.sort(NAME, Qt.SortOrder.AscendingOrder)
    assert source.rowCount(parent) == 5 and len(layouts) == 3
    assert source.index(0, 0, parent).data(NODE_ROLE) is another
    source.deleteLater()


def test_sort_preservation_restores_nested_and_exceptional_scopes(qapp):
    source = FolderTreeModel()
    source.set_root(_outcome(3).result.root)
    layouts = []
    source.layoutChanged.connect(lambda *_args: layouts.append(True))
    with pytest.raises(RuntimeError, match="outer"), source.preserve_sort():
        with pytest.raises(RuntimeError, match="inner"), source.preserve_sort():
            raise RuntimeError("inner")
        source.sort(SIZE, Qt.SortOrder.DescendingOrder)
        assert not layouts
        raise RuntimeError("outer")
    source.sort(SIZE, Qt.SortOrder.DescendingOrder)
    assert len(layouts) == 1
    source.deleteLater()


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




@pytest.mark.parametrize("filtered", [False, True])
def test_restoring_contiguous_rows_creates_only_range_endpoint_indexes(qapp, monkeypatch, filtered):
    from PySide6.QtWidgets import QTreeView
    from je_file_tree.gui.tree_filter import TreeFilter

    root = _outcome(1000).result.root
    source = FolderTreeModel()
    source.set_root(root)
    tree = QTreeView()
    tree.setModel(source)
    controller = TreeFilter(tree, source, tree)
    try:
        tree.expand(source.index_for(root))
        controller.proxy.allowed = frozenset(id(node) for node in root.children)
        controller.proxy.setSourceModel(source)
        if filtered:
            controller._switch(True)
        created = []
        with monkeypatch.context() as patch:
            for model in (source, controller.proxy):
                original = model.createIndex

                def create_index(*args, original=original):
                    created.append(True)
                    return original(*args)

                patch.setattr(model, "createIndex", create_index)
            picked = controller._selection([root, *reversed(root.children)], filtered)
            assert len(created) < 40, "selection restoration allocated an index for each selected file"
        assert len(picked) == 2
        indexes = picked.indexes()
        assert {index.data(NODE_ROLE) for index in indexes} == {root, *root.children}
        assert len(indexes) == (len(root.children)+1) * source.columnCount()
    finally:
        controller.shutdown()
        tree.close()
