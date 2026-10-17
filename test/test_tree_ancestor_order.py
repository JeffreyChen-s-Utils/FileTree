"""Post-scan mutations invalidate only affected default sibling-order shortcuts."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QItemSelectionModel, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QTreeView

from je_file_tree.core.node import Node
from je_file_tree.gui.tree_model import DRIVE_SHARE, NAME, NODE_ROLE, SHARE, SIZE, FolderTreeModel


class _UnopenedRows(list):
    def __iter__(self):
        raise AssertionError("Ancestor reordering traversed an unrelated subtree")


class _CountedRows(list):
    visited = 0

    def __iter__(self):
        for entry in super().__iter__():
            self.visited += 1
            yield entry


def _tree():
    root = Node("root", True, size=300, allocated=600, file_count=4, dir_count=4, children=[])
    a = Node("A", True, size=180, allocated=360, file_count=3, dir_count=2, parent=root, children=[])
    b = Node("B", True, size=120, allocated=240, file_count=1, parent=root, children=_UnopenedRows())
    inner = Node("inner", True, size=100, allocated=200, file_count=2, parent=a, children=[])
    peer = Node("peer", True, size=80, allocated=160, file_count=1, parent=a, children=_UnopenedRows())
    moved = Node("moved", False, size=90, allocated=180, file_count=1, parent=inner)
    kept = Node("kept", False, size=10, allocated=20, file_count=1, parent=inner)
    inner.children.extend((moved, kept))
    a.children.extend((inner, peer))
    root.children.extend((a, b))
    return root, a, b, inner, peer, moved, kept


def _shown(model, folder):
    parent = model.index_for(folder)
    return [model.index(row, NAME, parent).data(NODE_ROLE) for row in range(model.rowCount(parent))]


@pytest.mark.parametrize("column", [SIZE, SHARE, DRIVE_SHARE])
@pytest.mark.parametrize("mutation", ["remove", "grow", "shrink"])
def test_mutations_restore_default_ancestor_order_and_preserve_unaffected_indexes(qapp, column, mutation):
    root, a, b, inner, peer, moved, kept = _tree()
    model = FolderTreeModel()
    model.set_root(root)
    model.sort(column, Qt.SortOrder.DescendingOrder)
    watched = a if mutation == "grow" else b
    retained = QPersistentModelIndex(model.index_for(watched))
    obsolete = QPersistentModelIndex(model.index_for(b if mutation == "grow" else moved))
    children = root.children
    if mutation == "remove":
        model.remove_many([moved])
        assert _shown(model, root) == [b, a]
        assert _shown(model, a) == [peer, inner]
        assert (root.size, root.allocated, root.file_count, root.dir_count) == (210, 420, 3, 4)
        assert moved.parent is None and kept.parent is inner
    else:
        old, size = (b, 220) if mutation == "grow" else (a, 5)
        fresh = Node("fresh absolute root", True, size=size, allocated=size*2, file_count=1, children=[])
        fresh.children.append(Node("fresh", False, size=size, allocated=size*2, file_count=1, parent=fresh))
        model.replace(old, fresh)
        assert _shown(model, root) == ([fresh, a] if mutation == "grow" else [b, fresh])
        expected = (400, 800, 4, 4) if mutation == "grow" else (125, 250, 2, 2)
        assert (root.size, root.allocated, root.file_count, root.dir_count) == expected
        assert fresh.name == old.name and fresh.parent is root and old.parent is None
    assert retained.isValid() and retained.data(NODE_ROLE) is watched
    assert retained.row() == (1 if mutation == "grow" else 0)
    assert not obsolete.isValid() and root.children is children
    model.deleteLater()


def test_changed_default_order_survives_other_sorts_and_new_roots_restore_scanner_shortcut(qapp):
    root, a, b, _inner, _peer, moved, _kept = _tree()
    model = FolderTreeModel()
    model.set_root(root)
    model.remove(moved)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    assert _shown(model, root) == [a, b]
    model.sort(SIZE, Qt.SortOrder.DescendingOrder)
    assert _shown(model, root) == [b, a]
    model.remove_many([a])
    assert a not in model._size_order_changed and _shown(model, root) == [b]
    fresh, *_rest = _tree()
    model.set_root(fresh)
    assert not model._size_order_changed
    assert model._ordered(fresh) is fresh.children
    model.deleteLater()


def test_ancestor_sorting_is_deferred_and_does_not_walk_unopened_children(qapp):
    root, a, b, inner, peer, moved, _kept = _tree()
    root.children = _CountedRows(root.children)
    a.children = _CountedRows(a.children)
    model = FolderTreeModel()
    model.set_root(root)
    model.remove_many([moved])
    assert root.children.visited == a.children.visited == 0
    assert _shown(model, root) == [b, a]
    assert _shown(model, a) == [peer, inner]
    assert root.children.visited == a.children.visited == 2
    model.deleteLater()


def test_direct_sibling_removals_keep_the_default_scanner_order_without_an_order_copy(qapp):
    root = Node("root", True, size=5050, file_count=100, children=[])
    root.children.extend(Node(str(number), False, size=100-number, file_count=1, parent=root)
                         for number in range(100))
    model = FolderTreeModel()
    model.set_root(root)
    model.remove_many(root.children[::4])
    assert model._ordered(root) is root.children
    assert [node.size for node in root.children] == sorted((node.size for node in root.children), reverse=True)
    model.deleteLater()


def test_changed_expanded_ancestors_keep_the_current_row_and_visible_selection(qapp):
    root, a, _b, inner, _peer, moved, _kept = _tree()
    model = FolderTreeModel()
    model.set_root(root)
    view = QTreeView()
    view.setModel(model)
    view.expand(model.index_for(root))
    view.expand(model.index_for(a))
    view.expand(model.index_for(inner))
    view.selectionModel().setCurrentIndex(model.index_for(a), QItemSelectionModel.SelectionFlag.ClearAndSelect
                                         | QItemSelectionModel.SelectionFlag.Rows)
    try:
        model.remove_many([moved])
        assert view.currentIndex().data(NODE_ROLE) is a and view.currentIndex().row() == 1
        assert view.isExpanded(model.index_for(a)) and view.isExpanded(model.index_for(inner))
        assert {index.data(NODE_ROLE) for index in view.selectionModel().selectedRows()} == {a}
    finally:
        view.setModel(None)
        view.deleteLater()
        model.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
