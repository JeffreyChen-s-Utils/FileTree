"""Read filter identities from the same lazy rows as Qt without allocating temporary indexes."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QModelIndex, Qt

from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_filter import ExpandedTreeProxy
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, SIZE, FolderTreeModel


def _root():
    root = Node("root", True, children=[])
    root.children.extend(Node(f"file-{number:03d}", False, size=100-number, parent=root)
                         for number in range(100))
    return root


@pytest.fixture
def model(qapp):
    source = FolderTreeModel()
    yield source
    for proxy in source.findChildren(ExpandedTreeProxy):
        proxy.setSourceModel(None)
    source.set_root(None)
    source.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_filter_predicate_does_not_allocate_indexes_or_dispatch_data_roles(model, monkeypatch):
    root = _root()
    model.set_root(root)
    model.sort(NAME, Qt.SortOrder.DescendingOrder)
    parent = model.index_for(root)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset(id(node) for node in root.children[::3])
    expected = [id(model.index(row, 0, parent).data(NODE_ROLE)) in proxy.allowed for row in range(100)]
    calls = []
    index, data = model.index, model.data

    def observed_index(*args):
        calls.append("index")
        return index(*args)

    def observed_data(*args):
        calls.append("data")
        return data(*args)

    monkeypatch.setattr(model, "index", observed_index)
    monkeypatch.setattr(model, "data", observed_data)
    assert [proxy.filterAcceptsRow(row, parent) for row in range(100)] == expected
    assert not calls, "membership checks must not cross the Qt index/data bridge for every row"


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("column", [NAME, SIZE])
@pytest.mark.parametrize("order", [Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder])
def test_direct_row_identity_matches_sorted_and_frozen_source_indexes(model, live, column, order):
    root = _root()
    model.set_root(root, live=live)
    model.sort(column, order)
    parent = model.index_for(root)
    expected = [model.index(row, 0, parent).data(NODE_ROLE) for row in range(100)]
    if live:
        root.children.append(Node("new arrival", False, size=200, parent=root))
    assert model.node_at(0, QModelIndex()) is root
    assert [model.node_at(row, parent) for row in range(100)] == expected
    assert model.node_at(-1, parent) is None and model.node_at(100, parent) is None
    assert model.node_at(1, QModelIndex()) is None
    if live:
        model.refresh()
        assert model.rowCount(parent) == 101
        assert [model.node_at(row, parent) for row in range(101)] == [
            model.index(row, 0, parent).data(NODE_ROLE) for row in range(101)]
    model.set_root(None)
    assert model.node_at(0, QModelIndex()) is None


def test_direct_row_identity_excludes_nested_virtual_rows_and_virtual_roots(model):
    root = _root()
    archive = root.children[0]
    folder = VirtualEntry("folder", True, children=[], parent=archive)
    member = VirtualEntry("member", False, parent=folder)
    folder.children.append(member)
    model.set_root(root)
    model.set_archive(archive, [folder])
    assert model.node_at(0, model.index_for(root)) is archive
    assert model.node_at(0, model.index_for(archive)) is None
    assert model.node_at(0, model.index_for(folder)) is None
    model.set_root(folder)
    assert model.node_at(0, QModelIndex()) is None
    assert model.node_at(0, model.index_for(folder)) is None
    assert root.children[0] is archive and archive.children == ()


def test_direct_row_identity_never_walks_unopened_descendants(model):
    class UnopenedRows(list):
        def __iter__(self):
            raise AssertionError("identity lookup traversed unopened descendants")

    root = _root()
    branch = Node("unopened", True, children=UnopenedRows([Node("hidden", False)]), parent=root)
    root.children.append(branch)
    model.set_root(root)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    parent = model.index_for(root)
    assert model.node_at(0, parent) is branch
    assert set(model._orders) == {id(root)}


def test_empty_source_never_accepts_a_missing_root_as_a_filter_match(model):
    proxy = ExpandedTreeProxy(model, model)
    assert not proxy.filterAcceptsRow(0, QModelIndex())
