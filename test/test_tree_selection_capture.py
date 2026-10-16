"""Range capture preserves Qt fallback semantics and freezes selected node references."""

import pytest
from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, Qt
from PySide6.QtWidgets import QTreeView

from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_filter import TreeFilter
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, FolderTreeModel


@pytest.fixture
def capture(qapp):
    root = Node("root", True, children=[])
    root.children.extend(Node(f"file-{row:02d}", False, size=30-row, parent=root) for row in range(30))
    source = FolderTreeModel()
    source.set_root(root)
    tree = QTreeView()
    tree.setModel(source)
    controller = TreeFilter(tree, source, tree)
    tree.expand(source.index_for(root))
    controller.proxy.allowed = frozenset(id(node) for node in root.children)
    controller.proxy.setSourceModel(source)
    yield controller, source, root
    controller.shutdown()
    tree.close()


def _pick(controller, first=4, last=20):
    model = controller.tree.model()
    parent = controller.index_for(controller.source.root)
    selection = controller.tree.selectionModel()
    selection.select(QItemSelection(model.index(first, 0, parent),
                                    model.index(last, model.columnCount()-1, parent)),
                     QItemSelectionModel.SelectionFlag.ClearAndSelect)
    return selection


@pytest.mark.parametrize("filtered", [False, True])
@pytest.mark.parametrize("custom", ["partial", "data", "entry_data", "flags", "node_role", "proxy_data", "proxy_flags"])
def test_partial_cells_and_custom_semantics_keep_qt_row_capture(capture, monkeypatch, filtered, custom):
    controller, source, root = capture
    if filtered:
        controller._switch(True)
    selection = _pick(controller)
    if custom == "partial":
        model = controller.tree.model()
        parent = controller.index_for(root)
        selection.select(QItemSelection(model.index(0, 0, parent), model.index(10, 3, parent)),
                         QItemSelectionModel.SelectionFlag.ClearAndSelect)
        selection.select(QItemSelection(model.index(5, 4, parent), model.index(15, model.columnCount()-1, parent)),
                         QItemSelectionModel.SelectionFlag.Select)
    elif custom == "node_role":
        source._roles[NODE_ROLE] = lambda node, _column: None if node is root.children[8] else node
    else:
        target, name = ((controller.proxy, custom.removeprefix("proxy_")) if custom.startswith("proxy_")
                        else (source, custom))
        if custom.startswith("proxy_") and not filtered:
            controller._switch(True)
            selection = _pick(controller)
        original = getattr(target, name)
        monkeypatch.setattr(target, name, original)
    expected = [node for index in selection.selectedRows() if isinstance(node := index.data(NODE_ROLE), Node)]
    original_rows, calls = selection.selectedRows, []

    def selected_rows(*args):
        calls.append(True)
        return original_rows(*args)

    monkeypatch.setattr(selection, "selectedRows", selected_rows)
    assert controller._selected_nodes() == expected
    assert calls == [True]
    if custom == "partial":
        assert set(expected) == set(root.children[5:11])


@pytest.mark.parametrize("filtered", [False, True])
def test_captured_selection_survives_sort_and_arrivals_during_switch(capture, filtered):
    controller, source, root = capture
    if filtered:
        controller._switch(True)
    _pick(controller)
    wanted = set(root.children[4:21])
    removed = root.children[8]
    arrival = Node("arrival", False, size=15, parent=root)

    def change():
        source.remove_many([removed])
        root.children.append(arrival)
        source.refresh()
        source.sort(NAME, Qt.SortOrder.DescendingOrder)

    controller.selection_model_changed.connect(change)
    controller._switch(not filtered)
    selected = {index.data(NODE_ROLE) for index in controller.tree.selectionModel().selectedRows()}
    assert selected == wanted - {removed}
    assert arrival not in selected and removed.parent is None


def test_range_rows_exclude_virtual_foreign_and_invalid_parents(capture):
    controller, source, root = capture
    archive = root.children[0]
    folder = VirtualEntry("folder", True, children=[], parent=archive)
    member = VirtualEntry("member", False, parent=folder)
    folder.children.append(member)
    source.set_archive(archive, [folder])
    assert source.row_nodes(0, 99, QModelIndex()) == [root]
    assert source.row_nodes(0, 99, source.index_for(archive)) == []
    assert source.row_nodes(0, 99, source.index_for(folder)) == []
    assert source.row_nodes(-1, 3, QModelIndex()) == []
    proxy = controller.proxy
    assert proxy.row_nodes(0, 99, QModelIndex()) == [root]
    assert source.row_nodes(0, 4, proxy.index(0, 0)) == []
    assert proxy.row_nodes(0, 4, source.index_for(root)) == []
    assert source.row_nodes(0, 4, source.index_for(root).siblingAtColumn(1)) == []
    saved = source.row_nodes(3, 10, source.index_for(root))
    root.children.reverse()
    assert saved == list(reversed(root.children))[3:11]
    source.set_root(folder)
    assert source.row_nodes(0, 10, QModelIndex()) == []
    assert proxy.row_nodes(0, 10, QModelIndex()) == []
    source.set_root(None)
    assert source.row_nodes(0, 10, QModelIndex()) == []
    assert proxy.row_nodes(0, 10, QModelIndex()) == []


def test_foreign_proxy_keeps_its_own_node_role_semantics(capture):
    controller, _source, root = capture
    from je_file_tree.gui.tree_projection import ExpandedTreeProxy

    other = FolderTreeModel(controller.tree)
    other.set_root(root)
    other._roles[NODE_ROLE] = lambda _node, _column: None
    proxy = ExpandedTreeProxy(other, controller.tree)
    proxy.allowed = frozenset(id(node) for node in root.children)
    controller.tree.setModel(proxy)
    parent = proxy.index(0, 0)
    controller.tree.selectionModel().select(
        QItemSelection(proxy.index(0, 0, parent), proxy.index(5, proxy.columnCount()-1, parent)),
        QItemSelectionModel.SelectionFlag.ClearAndSelect)
    assert controller.tree.selectionModel().selectedRows()
    assert controller._selected_nodes() == []


def test_custom_source_class_uses_its_node_data(qapp):
    class CustomSource(FolderTreeModel):
        def data(self, index, role=Qt.ItemDataRole.DisplayRole):
            return None if role == NODE_ROLE else super().data(index, role)

    root = Node("root", True, children=[])
    root.children.extend(Node(str(row), False, parent=root) for row in range(5))
    source = CustomSource()
    source.set_root(root)
    tree = QTreeView()
    tree.setModel(source)
    controller = TreeFilter(tree, source, tree)
    try:
        tree.expand(source.index_for(root))
        _pick(controller, 0, 4)
        assert tree.selectionModel().selectedRows()
        assert controller._selected_nodes() == []
    finally:
        controller.shutdown()
        tree.close()
