"""Expanded archive previews stay read-only and need no hidden-member filter mapping."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeView

from test_tree_child_presence import _settle
from test_tree_row_identity import model as model  # noqa: PLC0414 - shared cleanup fixture
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_filter import ExpandedTreeProxy, TreeFilter
from je_file_tree.gui.tree_model import NAME, NODE_ROLE


def _archive():
    root = Node("root", True, children=[], size=4096, file_count=1)
    archive = Node("archive.zip", False, size=4096, file_count=1, parent=root)
    root.children.append(archive)
    members = [VirtualEntry(f"member-{40-number:03d}", False, size=1000, parent=archive) for number in range(40)]
    return root, archive, members


@pytest.mark.parametrize("as_root", [False, True])
def test_expanded_preview_does_not_query_member_rows_for_filter_presence(model, monkeypatch, as_root):
    root, archive, members = _archive()
    model.set_root(archive if as_root else root)
    model.set_archive(archive, members)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset({id(root), id(archive)})
    proxy.searched = frozenset({root, archive})
    parent = proxy.mapFromSource(model.index_for(archive))
    queried = []
    original = model.node_at

    def observed(row, source_parent):
        if source_parent.isValid() and source_parent.internalPointer() is archive:
            queried.append(row)
        return original(row, source_parent)

    monkeypatch.setattr(model, "node_at", observed)
    assert not proxy.hasChildren(parent)
    assert not queried, "all preview members are hidden; do not map them to check the expander"
    assert id(archive) not in model._orders and archive not in model._queried_parents
    assert archive.parent is root and archive.children == ()
    assert (root.size, root.file_count, archive.size) == (4096, 1, 4096)


def test_searched_archive_keeps_fetch_offer_until_preview_is_available(model):
    root, archive, members = _archive()
    archive.snapshot = b"captured metadata"
    model.set_root(root)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset({id(root), id(archive)})
    proxy.searched = frozenset({root, archive})
    parent = proxy.mapFromSource(model.index_for(archive))
    requested = []
    model.archive_requested.connect(requested.append)
    assert proxy.hasChildren(parent) and proxy.canFetchMore(parent) and not requested
    model.fetchMore(model.index_for(archive))
    assert requested == [archive] and not proxy.hasChildren(parent)
    model.set_archive(archive, members)
    assert not proxy.hasChildren(parent) and not proxy.canFetchMore(parent)
    assert requested == [archive] and archive.children == ()


def test_captured_non_directory_with_real_children_keeps_filtered_mapping(model):
    root, entry, _members = _archive()
    child = Node("captured child", False, parent=entry)
    entry.children = [child]
    model.set_root(root)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset({id(root), id(entry), id(child)})
    proxy.searched = frozenset({root, entry})
    parent = proxy.mapFromSource(model.index_for(entry))
    assert proxy.hasChildren(parent) and proxy.rowCount(parent) == 1
    assert proxy.index(0, 0, parent).data(NODE_ROLE) is child


def test_view_restores_expanded_preview_after_clearing_filter(model, qapp, monkeypatch):
    root, archive, members = _archive()
    model.set_root(root)
    model.set_archive(archive, members)
    view = QTreeView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    view.setUniformRowHeights(True)
    view.setModel(model)
    view.sortByColumn(NAME, Qt.SortOrder.AscendingOrder)
    view.setSortingEnabled(True)
    controller = TreeFilter(view, model, view)
    controller.line.setParent(view)
    counts = []
    lookup = model.node_at

    def observed(row, parent):
        if parent.isValid() and parent.internalPointer() is archive:
            counts.append(row)
        return lookup(row, parent)

    monkeypatch.setattr(model, "node_at", observed)
    try:
        view.expand(model.index_for(root))
        view.expand(model.index_for(archive))
        view.setCurrentIndex(model.index_for(archive))
        view.show()
        qapp.processEvents()
        assert model.rowCount(model.index_for(archive)) == 40
        for _cycle in range(2):
            controller.line.setText("archive")
            _settle(qapp, controller)
            assert archive in controller.proxy.searched
            assert not controller.proxy.hasChildren(controller.index_for(archive)) and not counts
            assert view.currentIndex().data(NODE_ROLE) is archive
            controller.line.clear()
            qapp.processEvents()
            assert view.isExpanded(model.index_for(archive))
            assert model.rowCount(model.index_for(archive)) == 40
            assert model.index(0, 0, model.index_for(archive)).data(NODE_ROLE) is None
        assert (root.size, root.file_count, archive.size, archive.children) == (4096, 1, 4096, ())
    finally:
        controller.shutdown()
        view.setModel(None)
        controller.proxy.setSourceModel(None)
        view.close()
        view.deleteLater()
