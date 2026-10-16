"""Persistent tree rows stay current without repeated full sibling searches."""

import pytest
from PySide6.QtCore import (
    QAbstractItemModel, QItemSelection, QItemSelectionModel, QModelIndex, QPersistentModelIndex, Qt,
)

from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, SIZE, FolderTreeModel


class _ProbedRows(list):
    def __init__(self, nodes):
        super().__init__(nodes)
        self.visited = 0

    def __iter__(self):
        for node in super().__iter__():
            self.visited += 1
            yield node

    def index(self, target):
        for row, node in enumerate(self):
            if node is target:
                return row
        raise ValueError("Node is not in these rows")


class _UnopenedRows(list):
    def __iter__(self):
        raise AssertionError("Remapping selected files traversed an unopened branch")


def test_large_selection_remaps_in_linear_work_without_indexing_every_file(qapp, monkeypatch):
    root = Node("root", True, children=[])
    root.children.extend(Node(f"file-{number:04d}", False, size=2000-number, parent=root)
                         for number in range(2000))
    root.children.append(Node("unopened", True, children=_UnopenedRows(), parent=root))
    model = FolderTreeModel()
    model.set_root(root)
    parent = model.index(0, NAME)
    chosen = list(range(0, 2000, 25))
    pins = [QPersistentModelIndex(model.index(row, column, parent)) for row in chosen for column in (NAME, SIZE)]
    expected = [root.children[row] for row in chosen for _column in (NAME, SIZE)]
    original, probes = model._ordered, {}

    def ordered(node):
        rows = original(node)
        key = id(rows)
        if key not in probes:
            probes[key] = _ProbedRows(rows)
        return probes[key]

    monkeypatch.setattr(model, "_ordered", ordered)
    model.sort(NAME, Qt.SortOrder.DescendingOrder)
    assert all(pin.isValid() and pin.data(NODE_ROLE) is node for pin, node in zip(pins, expected, strict=True))
    assert all(pin.column() == column for pin, column in zip(pins, (NAME, SIZE)*len(chosen), strict=True))
    assert sum(rows.visited for rows in probes.values()) < 3 * len(root.children) + 10 * len(pins)
    assert len(model._rows) <= len(chosen) + 2, "cache requested file rows, not the entire folder"
    model.deleteLater()


def test_index_lookup_rejects_foreign_and_detached_descendants(qapp):
    root = Node("root", True, children=[])
    branch = Node("branch", True, children=[], parent=root)
    leaf = Node("leaf", False, parent=branch)
    branch.children.append(leaf)
    root.children.append(branch)
    foreign = Node("foreign", True, children=[])
    other = Node("other", False, parent=foreign)
    foreign.children.append(other)
    model = FolderTreeModel()
    model.set_root(root)
    assert not model.index_for(other).isValid()
    model.replace(branch, Node("branch", True, children=[]))
    assert not model.index_for(leaf).isValid()
    model.deleteLater()


def test_archive_invalidation_drops_nested_virtual_persistent_rows(qapp):
    root = Node("root", True, children=[])
    archive = Node("archive.zip", False, parent=root)
    root.children.append(archive)
    folder = VirtualEntry("folder", True, children=[], parent=archive)
    nested = VirtualEntry("nested.txt", False, parent=folder, member="folder/nested.txt")
    folder.children.append(nested)
    model = FolderTreeModel()
    model.set_root(root)
    model.set_archive(archive, [folder])
    kept = QPersistentModelIndex(model.index_for(archive))
    virtual = QPersistentModelIndex(model.index_for(nested))
    assert virtual.isValid() and virtual.data(NODE_ROLE) is None
    model._relayout(model.invalidate_archives)
    assert kept.isValid() and kept.data(NODE_ROLE) is archive
    assert not virtual.isValid()
    assert not model.index_for(nested).isValid()
    model.deleteLater()


def test_live_refresh_and_final_order_keep_large_file_selections(qapp):
    root = Node("root", True, children=[])
    root.children.extend(Node(f"file-{number:03d}", False, size=200-number, parent=root) for number in range(200))
    model = FolderTreeModel()
    model.set_root(root, live=True)
    parent = model.index(0, NAME)
    chosen = root.children[::5]
    pins = [QPersistentModelIndex(model.index(row, NAME, parent)) for row in range(0, 200, 5)]
    added = Node("new arrival", False, size=1000, parent=root)
    root.children.append(added)
    chosen[-1].size = 2000
    model.refresh()
    assert all(pin.data(NODE_ROLE) is node for pin, node in zip(pins, chosen, strict=True))
    assert model.index_for(added).row() == 1
    root.children.sort(key=lambda node: -node.size)
    model.finish_live()
    assert not model.live
    assert all(pin.data(NODE_ROLE) is node and pin.row() == root.children.index(node)
               for pin, node in zip(pins, chosen, strict=True))
    model.deleteLater()


def test_replacing_one_branch_drops_its_selection_and_preserves_other_rows(qapp):
    root = Node("root", True, children=[])
    branches = [Node(name, True, children=[], parent=root) for name in ("changed", "kept")]
    root.children.extend(branches)
    for branch in branches:
        branch.children.extend(Node(f"file-{number:03d}", False, parent=branch) for number in range(80))
    model = FolderTreeModel()
    model.set_root(root)
    pins = [[QPersistentModelIndex(model.index(row, NAME, model.index_for(branch))) for row in range(40)]
            for branch in branches]
    expected = branches[1].children[:40]
    fresh = Node("changed", True, children=_UnopenedRows())
    model.replace(branches[0], fresh)
    assert all(not pin.isValid() for pin in pins[0])
    assert all(pin.isValid() and pin.data(NODE_ROLE) is node
               for pin, node in zip(pins[1], expected, strict=True))
    assert model.index_for(fresh).isValid()
    model.deleteLater()


def test_current_archive_rows_survive_batch_sort_and_new_inventory_invalidates_old_rows(qapp):
    root = Node("root", True, size=77, file_count=1, children=[])
    archive = Node("archive.zip", False, size=77, file_count=1, parent=root)
    root.children.append(archive)
    folder = VirtualEntry("folder", True, children=[], parent=archive)
    folder.children.extend(VirtualEntry(f"file-{number:03d}", False, size=100-number,
                                       parent=folder, member=f"folder/file-{number:03d}") for number in range(100))
    model = FolderTreeModel()
    model.set_root(root)
    model.set_archive(archive, [folder])
    parent = model.index_for(folder)
    chosen = folder.children[:40]
    pins = [QPersistentModelIndex(model.index(row, NAME, parent)) for row in range(40)]
    model.sort(NAME, Qt.SortOrder.DescendingOrder)
    assert all(pin.isValid() and model._entry(QModelIndex(pin)) is node
               for pin, node in zip(pins, chosen, strict=True))
    assert all(pin.data(NODE_ROLE) is None for pin in pins)
    model.set_archive(archive, [VirtualEntry("replacement", True, parent=archive)])
    assert all(not pin.isValid() for pin in pins)
    assert not model.index_for(chosen[0]).isValid()
    assert root.size == 77 and root.file_count == 1 and archive.children == ()
    model.deleteLater()


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("whole_rows", [False, True])
def test_sort_hint_preserves_row_and_partial_column_selections_and_excludes_live_updates(qapp, live, whole_rows):
    root = Node("root", True, children=[])
    root.children.extend(Node(f"file-{number:03d}", False, size=120-number, parent=root) for number in range(120))
    model = FolderTreeModel()
    model.set_root(root, live=live)
    selection = QItemSelectionModel(model)
    parent = model.index(0, NAME)
    picked = QItemSelection()
    chosen = root.children[::3]
    for row in range(0, 120, 3):
        picked.select(model.index(row, SIZE, parent), model.index(row, SIZE + 1, parent))
    flags = QItemSelectionModel.SelectionFlag.ClearAndSelect
    if whole_rows:
        flags |= QItemSelectionModel.SelectionFlag.Rows
    selection.select(picked, flags)
    columns = range(model.columnCount()) if whole_rows else (SIZE, SIZE + 1)
    expected = {(node, column) for node in chosen for column in columns}
    events = []
    signature = ("QList<QPersistentModelIndex>", "QAbstractItemModel::LayoutChangeHint")
    model.layoutAboutToBeChanged[signature].connect(lambda _parents, hint: events.append(hint))
    model.layoutChanged[signature].connect(lambda _parents, hint: events.append(hint))
    model.sort(NAME, Qt.SortOrder.DescendingOrder)
    hint = (QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint if live
            else QAbstractItemModel.LayoutChangeHint.VerticalSortHint)
    assert events == [hint, hint]
    assert {(index.data(NODE_ROLE), index.column()) for index in selection.selectedIndexes()} == expected
    events.clear()
    model.refresh()
    assert events == [QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint] * 2
    assert {(index.data(NODE_ROLE), index.column()) for index in selection.selectedIndexes()} == expected
    selection.deleteLater()
    model.deleteLater()


@pytest.mark.parametrize("virtual", [False, True])
def test_existing_subtree_can_be_a_model_root_without_reparenting(qapp, virtual):
    outside = Node("outside", True, children=[])
    entry_type = VirtualEntry if virtual else Node
    root = entry_type("displayed", True, children=[], parent=outside)
    leaf = entry_type("leaf", False, parent=root)
    sibling = Node("outside sibling", False, parent=outside)
    root.children.append(leaf)
    outside.children.extend((root, sibling))
    model = FolderTreeModel()
    model.set_root(root)
    top = model.index_for(root)
    assert top.isValid() and not top.parent().isValid()
    index = model.index_for(leaf)
    assert index.isValid() and index.parent() == top
    kept = QPersistentModelIndex(index)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    assert kept.isValid() and model._entry(QModelIndex(kept)) is leaf
    assert not model.index_for(sibling).isValid()
    assert root.parent is outside and leaf.parent is root
    model.deleteLater()
