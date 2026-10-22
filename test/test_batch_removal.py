"""Apply completed moves to captured records as one structural update."""

import pytest
from PySide6.QtCore import (
    QAbstractItemModel, QCoreApplication, QEvent, QItemSelection, QItemSelectionModel, QPersistentModelIndex, Qt,
)
from test_gui import window as window  # noqa: PLC0414 - shared fixture

from je_file_tree.core.analysis import category_stats, summarise
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node, detach_many
from je_file_tree.core.scanner import ScanResult
from je_file_tree.gui.scan_worker import ScanOutcome
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, FolderTreeModel


class _CountedRows(list):
    def __init__(self, entries):
        super().__init__(entries)
        self.visited = 0

    def __iter__(self):
        for entry in super().__iter__():
            self.visited += 1
            yield entry


class _UnopenedRows(list):
    def __iter__(self):
        raise AssertionError("Removing captured entries walked an unrelated subtree")


def test_detach_many_filters_each_parent_once_and_subtracts_outermost_totals():
    root = Node("root", True, size=45, allocated=29, file_count=4, dir_count=3, children=[])
    branch = Node("branch", True, size=30, allocated=20, file_count=3, dir_count=2, children=[], parent=root)
    folder = Node("folder", True, size=20, allocated=12, file_count=2, dir_count=1,
                  children=_UnopenedRows(), parent=branch)
    extra = Node("extra", False, size=10, allocated=8, file_count=1, parent=branch)
    link = Node("link", True, is_link=True, parent=root)
    kept = Node("kept", False, size=15, allocated=9, file_count=1, parent=root)
    root.children = _CountedRows([branch, kept, link])
    branch.children = _CountedRows([folder, extra])
    root_rows, branch_rows = root.children, branch.children
    detach_many([folder, extra, folder, link])
    assert root.children is root_rows and branch.children is branch_rows
    assert root_rows.visited == 3 and branch_rows.visited == 2
    assert root.children == [branch, kept] and branch.children == []
    assert all(node.parent is None for node in (folder, extra, link))
    assert (root.size, root.allocated, root.file_count, root.dir_count) == (15, 9, 1, 1)
    assert (branch.size, branch.allocated, branch.file_count, branch.dir_count) == (0, 0, 0, 0)


def test_detach_many_ignores_roots_missing_and_immutable_rows_and_keeps_descendants_attached():
    root = Node("root", True, size=10, allocated=7, file_count=1, dir_count=1, children=[])
    branch = Node("branch", True, size=10, allocated=7, file_count=1, children=[], parent=root)
    leaf = Node("leaf", False, size=10, allocated=7, file_count=1, parent=branch)
    branch.children.append(leaf)
    root.children.append(branch)
    absent = Node("absent", False, size=100, parent=root)
    immutable = Node("immutable", True)
    unlisted = Node("unlisted", False, size=100, parent=immutable)
    detach_many([absent, unlisted])
    assert root.size == 10 and absent.parent is root and unlisted.parent is immutable
    detach_many([branch, leaf, branch])
    assert root.children == [] and root.size == root.allocated == root.file_count == root.dir_count == 0
    assert branch.parent is None and leaf.parent is branch
    detach_many([root])
    assert root.parent is None


@pytest.mark.parametrize("filtered", [False, True])
def test_batch_model_remaps_whole_row_selections_and_rejects_foreign_virtual_and_root(qapp, filtered):
    from je_file_tree.gui.tree_filter import ExpandedTreeProxy

    root = Node("root", True, size=60, allocated=60, file_count=60, children=[])
    root.children.extend(Node(f"file-{number:03d}", False, size=1, allocated=1, file_count=1, parent=root)
                         for number in range(60))
    unopened = Node("unopened", True, children=_UnopenedRows(), parent=root)
    root.children.append(unopened)
    foreign = Node("foreign", True, children=[])
    other = Node("other", False, parent=foreign)
    foreign.children.append(other)
    model = FolderTreeModel()
    model.set_root(root)
    model.set_drive_total(1000)
    model.sort(NAME, Qt.SortOrder.DescendingOrder)
    virtual = VirtualEntry("preview", False, parent=root.children[0])
    model.set_archive(root.children[0], [virtual])
    preview = QPersistentModelIndex(model.index_for(virtual))
    proxy = ExpandedTreeProxy(model, model)
    proxy.setSourceModel(model)
    proxy.allowed = frozenset(id(node) for node in root.children)
    displayed = proxy if filtered else model
    selection = QItemSelectionModel(displayed)
    picked = QItemSelection()
    chosen = root.children[:40]
    moved, kept = chosen[::2], chosen[1::2]
    for node in chosen:
        source = model.index_for(node)
        index = proxy.mapFromSource(source) if filtered else source
        picked.select(index, index)
    selection.select(picked, QItemSelectionModel.SelectionFlag.ClearAndSelect
                     | QItemSelectionModel.SelectionFlag.Rows)
    model.remove_many([*moved, moved[0], virtual, other, root])
    assert {index.data(NODE_ROLE) for index in selection.selectedRows()} == set(kept)
    assert all(node.parent is None for node in moved)
    assert len(root.children) == 41 and root.size == root.allocated == root.file_count == 40
    assert not preview.isValid() and not model.index_for(virtual).isValid()
    assert other.parent is foreign and foreign.children == [other] and root.parent is None
    assert unopened.parent is root
    assert model._drive_total is None
    # Release native proxy/index ownership while the captured Python nodes are still alive.
    selection.setModel(None)
    proxy.setSourceModel(None)
    selection.deleteLater()
    model.deleteLater()
    QCoreApplication.sendPostedEvents(selection, QEvent.Type.DeferredDelete)
    QCoreApplication.sendPostedEvents(model, QEvent.Type.DeferredDelete)


def test_completed_batch_changes_layout_once_and_keeps_unmoved_selection(window):
    root = Node("captured-batch", True, children=[], file_count=400)
    root.children.extend(Node(f"file-{number:03d}.bin", False, size=400-number, allocated=400-number,
                              file_count=1, parent=root) for number in range(400))
    root.size = root.allocated = sum(node.size for node in root.children)
    summary = summarise(root, now=1_800_000_000)
    results = window.results
    results.show_outcome(ScanOutcome(ScanResult(root, [], 0), summary.largest, summary.extensions,
                                    category_stats(summary.extensions), summary.ages, summary.now))
    moved, kept = root.children[::5], root.children[1]
    removed = summarise(Node("", True, children=moved), limit=0, now=summary.now)
    results.select_node(kept)
    retained = QPersistentModelIndex(results.tree_model.index_for(kept))
    obsolete = QPersistentModelIndex(results.tree_model.index_for(moved[-1]))
    layouts = []
    signature = ("QList<QPersistentModelIndex>", "QAbstractItemModel::LayoutChangeHint")
    results.tree_model.layoutChanged[signature].connect(lambda _parents, hint: layouts.append(hint))
    results.forget(moved, removed=removed)
    assert len(layouts) == 1, "capacity invalidation and all moved entries share one layout"
    assert layouts[-1] == QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint
    assert retained.isValid() and retained.data(NODE_ROLE) is kept and not obsolete.isValid()
    assert results.selected_node() is kept
    assert all(node.parent is None for node in moved)
    assert root.file_count == 320 and len(root.children) == 320
    assert root.size == root.allocated == sum(node.size for node in root.children)
    assert sum(row.size for row in results.types_model.rows()) == root.size
    assert sum(row.count for row in results.age_model.rows()) == 320
