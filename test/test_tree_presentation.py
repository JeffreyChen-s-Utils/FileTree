"""Presentation changes repaint queried row groups without structural layout or subtree traversal."""

import pytest
from PySide6.QtCore import (
    QCoreApplication, QEvent, QItemSelection, QItemSelectionModel, QModelIndex, QPersistentModelIndex, Qt,
)

from je_file_tree.core.node import Node
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.gui.tree_filter import ExpandedTreeProxy
from je_file_tree.gui.tree_model import (
    ACCOUNTED_ALLOCATED, ACCOUNTED_SIZE, ALLOCATED, DRIVE_SHARE, NAME, NODE_ROLE, SHARE_ROLE, SIZE, FolderTreeModel,
)


class _UnopenedRows(list):
    def __iter__(self):
        raise AssertionError("A presentation update traversed an unopened branch")


def _tree():
    root = Node("root", True, children=[])
    root.children.extend(Node(f"file-{number:02d}", False, size=2048, allocated=4096, parent=root)
                         for number in range(40))
    branch = Node("branch", True, children=[], parent=root)
    branch.children.append(Node("nested", False, size=2048, allocated=4096, parent=branch))
    unopened = Node("unopened", True, children=_UnopenedRows(), parent=root)
    root.children.extend((branch, unopened))
    return root, branch


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("filtered", [False, True])
def test_units_and_capacity_emit_data_ranges_without_relayout_or_selection_changes(qapp, live, filtered):
    root, branch = _tree()
    model = FolderTreeModel()
    model.set_root(root, live=live)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset(id(node) for node in (*root.children, branch.children[0]))
    displayed = proxy if filtered else model
    selection = QItemSelectionModel(displayed)
    pins = [QPersistentModelIndex(model.index_for(node)) for node in root.children[:30]]
    nested = model.index(0, NAME, model.index_for(branch))
    assert nested.data(NODE_ROLE) is branch.children[0]
    picked = QItemSelection()
    for pin in pins:
        index = proxy.mapFromSource(pin) if filtered else pin
        picked.select(index, index)
    selection.select(picked, QItemSelectionModel.SelectionFlag.ClearAndSelect
                     | QItemSelectionModel.SelectionFlag.Rows)
    layouts, changes = [], []
    model.layoutChanged.connect(lambda: layouts.append(True))
    model.dataChanged.connect(lambda first, last, roles: changes.append((first, last, roles)))
    try:
        model.set_unit("KB")
        assert not layouts, "unit changes alter text, not row structure"
        assert changes
        groups = {model._entry(first.parent()) for first, _last, _roles in changes}
        assert groups == {None, root, branch}
        assert all(first.parent() == last.parent() for first, last, _roles in changes)
        assert all(roles == [Qt.ItemDataRole.DisplayRole] for _first, _last, roles in changes)
        assert {(first.column(), last.column()) for first, last, _roles in changes} == {
            (SIZE, ALLOCATED), (ACCOUNTED_SIZE, ACCOUNTED_ALLOCATED)}
        assert nested.siblingAtColumn(SIZE).data() == "2.0 KB"
        changes.clear()
        model.set_unit("KB")
        assert not changes and not layouts
        model.set_drive_total(10000)
        assert changes and not layouts
        assert all(first.column() == last.column() == DRIVE_SHARE for first, last, _roles in changes)
        assert all(roles == [Qt.ItemDataRole.DisplayRole, SHARE_ROLE] for _first, _last, roles in changes)
        changes.clear()
        model.set_drive_total(10000)
        assert not changes and not layouts
        model.set_drive_total(None)
        assert changes and not layouts
        assert all(pin.isValid() and pin.data(NODE_ROLE) is node
                   for pin, node in zip(pins, root.children[:30], strict=True))
        assert {index.data(NODE_ROLE) for index in selection.selectedRows()} == set(root.children[:30])
    finally:
        selection.setModel(None)
        proxy.setSourceModel(None)
        selection.deleteLater()
        model.deleteLater()
        QCoreApplication.sendPostedEvents(selection, QEvent.Type.DeferredDelete)
        QCoreApplication.sendPostedEvents(model, QEvent.Type.DeferredDelete)


def test_live_unit_change_keeps_the_frozen_rows_until_explicit_refresh(qapp):
    root, branch = _tree()
    model = FolderTreeModel()
    model.set_root(root, live=True)
    parent = model.index_for(branch)
    kept = QPersistentModelIndex(model.index(0, NAME, parent))
    arrival = Node("arrival", False, size=10000, parent=branch)
    branch.children.append(arrival)
    model.set_unit("KB")
    assert model.rowCount(parent) == 1 and kept.row() == 0
    assert QModelIndex(kept).siblingAtColumn(SIZE).data() == "2.0 KB"
    model.refresh()
    assert model.rowCount(parent) == 2 and kept.row() == 1
    assert model.index(0, NAME, parent).data(NODE_ROLE) is arrival
    model.deleteLater()


def test_archive_refresh_removal_and_new_root_prune_obsolete_presentation_groups(qapp):
    root, branch = _tree()
    model = FolderTreeModel()
    model.set_root(root)
    archive = root.children[0]
    folder = VirtualEntry("folder", True, parent=archive, children=[])
    folder.children.append(VirtualEntry("nested", False, size=2048, parent=folder, member="folder/nested"))
    model.set_archive(archive, [folder])
    model.index(0, SIZE, model.index_for(folder))
    model.index(0, SIZE, model.index_for(branch))
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    changes = []
    model.dataChanged.connect(lambda first, last, _roles: changes.append((first, last)))
    model.set_unit("KB")
    assert any(model._entry(first.parent()) is folder for first, _last in changes)
    assert model.index_for(folder.children[0]).siblingAtColumn(SIZE).data() == "2.0 KB"
    model.set_archive(archive, [VirtualEntry("new", False, parent=archive)])
    model.remove_many([branch])
    assert folder not in model._queried_parents and branch not in model._queried_parents
    changes.clear()
    model.set_unit("MB")
    assert all(model._entry(first.parent()) not in (folder, branch) for first, _last in changes)
    assert all(parent in (root, archive) for parent in model._queried_parents)
    model.set_root(Node("new-root", True, children=_UnopenedRows()))
    assert not model._queried_parents
    model.set_root(None)
    changes.clear()
    model.set_unit("KB")
    model.set_drive_total(1000)
    assert not changes and not model._queried_parents
    model.deleteLater()


def test_display_roles_do_not_refilter_prepared_node_identities(qapp):
    class CountedProxy(ExpandedTreeProxy):
        calls = 0

        def filterAcceptsRow(self, row, parent):  # noqa: N802 - Qt virtual method
            self.calls += 1
            return super().filterAcceptsRow(row, parent)

    root, _branch = _tree()
    model = FolderTreeModel()
    model.set_root(root)
    proxy = CountedProxy(model, model)
    proxy.allowed = frozenset(id(node) for node in root.children)
    parent = proxy.index(0, NAME)
    assert proxy.rowCount(parent) == len(root.children)
    proxy.calls = 0
    try:
        model.set_unit("KB")
        model.set_drive_total(1000)
        assert proxy.calls == 0, "text and capacity do not change prepared name-filter membership"
        assert proxy.rowCount(parent) == len(root.children)
        proxy.allowed = frozenset({id(root.children[0])})
        proxy.invalidate()
        assert proxy.rowCount(proxy.index(0, NAME)) == 1 and proxy.calls > 0
    finally:
        proxy.setSourceModel(None)
        model.deleteLater()
        QCoreApplication.sendPostedEvents(model, QEvent.Type.DeferredDelete)
