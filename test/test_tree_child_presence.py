"""Expander checks remain lazy, while explicit row queries freeze live membership."""

import time

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QTreeView

from test_tree_row_identity import model as model  # noqa: PLC0414 - shared cleanup fixture
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_filter import ExpandedTreeProxy, TreeFilter
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, SIZE


class _CountedRows(list):
    visited = 0

    def __iter__(self):
        for entry in super().__iter__():
            self.visited += 1
            yield entry


def _branch(count=40):
    root = Node("root", True, children=[])
    folder = Node("folder", True, children=[], parent=root)
    folder.children = _CountedRows(Node(f"folder-file-{count-number:03d}", False, size=count-number, parent=folder)
                                   for number in range(count))
    root.children.append(folder)
    return root, folder


def _settle(app, controller):
    deadline = time.monotonic() + 10
    while controller.timer.isActive() or controller._workers:
        assert time.monotonic() < deadline
        app.processEvents()
        time.sleep(.005)
    app.processEvents()


def _assert_fresh_filter_after_reset(model, view, controller, app):
    replacement, replacement_folder = _branch()
    model.set_root(replacement)
    view.expand(controller.index_for(replacement))
    _settle(app, controller)
    assert controller.proxy.searched == frozenset({replacement})
    assert view.isExpanded(controller.index_for(replacement))
    assert controller.proxy.rowCount(controller.index_for(replacement)) == 1
    assert replacement_folder.children.visited == 0
    model.set_root(None)
    assert controller.proxy.searched == frozenset() and not controller.expanded


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("column", [NAME, SIZE])
def test_child_presence_does_not_sort_copy_or_register_unopened_rows(model, live, column):
    root, folder = _branch()
    model.set_root(root, live=live)
    model.sort(column, Qt.SortOrder.AscendingOrder)
    parent = model.index_for(folder)
    assert model.hasChildren(parent)
    assert folder.children.visited == 0
    assert id(folder) not in model._orders and folder not in model._queried_parents
    assert not model.hasChildren(parent.siblingAtColumn(SIZE))
    assert model.hasChildren(QModelIndex())


@pytest.mark.parametrize("initial_count", [0, 1])
def test_presence_check_does_not_freeze_an_unqueried_live_group(model, initial_count):
    root, folder = _branch(initial_count)
    model.set_root(root, live=True)
    parent = model.index_for(folder)
    assert model.hasChildren(parent) is bool(initial_count)
    arrival = Node("arrival", False, size=100, parent=folder)
    folder.children.append(arrival)
    assert id(folder) not in model._orders
    assert model.rowCount(parent) == initial_count + 1
    assert model.index(0, 0, parent).data(NODE_ROLE) is arrival


def test_queried_empty_live_group_stays_empty_until_explicit_refresh(model):
    root, folder = _branch(0)
    model.set_root(root, live=True)
    parent = model.index_for(folder)
    assert model.rowCount(parent) == 0
    folder.children.append(Node("arrival", False, size=100, parent=folder))
    assert not model.hasChildren(parent)
    assert model.rowCount(parent) == 0 and not model.index(0, 0, parent).isValid()
    model.set_unit("KB")
    assert model.rowCount(parent) == 0
    model.refresh()
    assert model.hasChildren(parent) and model.rowCount(parent) == 1


def test_existing_live_rows_and_presence_use_the_same_frozen_group(model):
    root, folder = _branch(1)
    model.set_root(root, live=True)
    parent = model.index_for(folder)
    assert model.rowCount(parent) == 1
    frozen = model._orders[id(folder)]
    folder.children.append(Node("arrival", False, size=100, parent=folder))
    folder.children.visited = 0
    assert model.hasChildren(parent) and model.rowCount(parent) == 1
    assert model._orders[id(folder)] is frozen and folder.children.visited == 0
    model.finish_live()
    assert model.rowCount(parent) == 2


def test_empty_live_root_in_a_view_reveals_arrivals_only_after_refresh(model, qapp):
    root = Node("root", True, children=[])
    model.set_root(root, live=True)
    view = QTreeView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    view.setModel(model)
    try:
        parent = model.index_for(root)
        view.expand(parent)
        view.show()
        qapp.processEvents()
        assert model.rowCount(parent) == 0
        arrival = Node("arrival", False, size=100, parent=root)
        root.children.append(arrival)
        qapp.processEvents()
        assert not model.hasChildren(parent) and model.rowCount(parent) == 0
        model.refresh()
        view.expand(parent)
        qapp.processEvents()
        assert model.hasChildren(parent) and model.rowCount(parent) == 1
        assert model.index(0, 0, parent).data(NODE_ROLE) is arrival
        assert view.isExpanded(parent)
    finally:
        view.setModel(None)
        view.close()
        view.deleteLater()


def test_archive_presence_is_lazy_and_preserves_loading_virtual_and_failed_states(model):
    root = Node("root", True, children=[])
    archive = Node("archive.zip", False, snapshot=b"captured metadata", parent=root)
    root.children.append(archive)
    model.set_root(root)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    parent = model.index_for(archive)
    requested = []
    model.archive_requested.connect(requested.append)
    assert model.hasChildren(parent) and not requested and id(archive) not in model._orders
    model.fetchMore(parent)
    assert requested == [archive] and model.hasChildren(parent)
    folder = VirtualEntry("nested", True, children=[], parent=archive)
    folder.children = _CountedRows([VirtualEntry("member.zip", False, snapshot=b"metadata", parent=folder)])
    model.set_archive(archive, [folder])
    virtual_parent = model.index_for(folder)
    assert model.hasChildren(virtual_parent) and folder.children.visited == 0
    assert id(folder) not in model._orders and not model.canFetchMore(virtual_parent)
    assert not model.hasChildren(model.index_for(folder.children[0]))
    model.archive_error(archive, "unavailable")
    assert not model.hasChildren(parent) and model.rowCount(parent) == 0
    assert archive.children == () and requested == [archive]


def test_filtered_closed_folder_does_not_materialize_unsearched_source_children(model):
    root, folder = _branch()
    model.set_root(root)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset({id(root), id(folder)})
    proxy.searched = frozenset({root})
    parent = proxy.mapFromSource(model.index_for(folder))
    assert parent.isValid() and not proxy.hasChildren(parent)
    assert folder.children.visited == 0 and id(folder) not in model._orders


def test_filtered_collapsed_root_does_not_materialize_its_unsearched_rows(model):
    root, folder = _branch()
    root.children = _CountedRows([folder])
    model.set_root(root)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset({id(root)})
    proxy.searched = frozenset()
    parent = proxy.mapFromSource(model.index_for(root))
    assert parent.isValid() and not proxy.hasChildren(parent)
    assert not root.children.visited and id(root) not in model._orders


def test_proxy_without_worker_snapshot_keeps_standard_child_mapping(model):
    root, folder = _branch()
    member = folder.children[0]
    model.set_root(root)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset({id(root), id(folder), id(member)})
    parent = proxy.mapFromSource(model.index_for(folder))
    assert proxy.searched is None and proxy.hasChildren(parent)
    assert proxy.rowCount(parent) == 1 and proxy.index(0, 0, parent).data(NODE_ROLE) is member


def test_filtered_unsearched_archive_keeps_lazy_fetch_but_never_virtual_matches(model):
    root = Node("root", True, children=[])
    archive = Node("archive.zip", False, snapshot=b"captured metadata", parent=root)
    root.children.append(archive)
    model.set_root(root)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset({id(root), id(archive)})
    proxy.searched = frozenset({root})
    requested = []
    model.archive_requested.connect(requested.append)
    parent = proxy.mapFromSource(model.index_for(archive))
    assert proxy.hasChildren(parent) and proxy.canFetchMore(parent) and not requested
    assert id(archive) not in model._orders
    proxy.setSourceModel(None)
    member = VirtualEntry("member", False, parent=archive)
    model.set_archive(archive, [member])
    proxy.setSourceModel(model)
    parent = proxy.mapFromSource(model.index_for(archive))
    assert not proxy.hasChildren(parent) and not proxy.canFetchMore(parent)
    assert id(archive) not in model._orders and archive not in model._queried_parents
    assert not requested and archive.children == ()


@pytest.mark.parametrize("filtered", [False, True])
def test_real_view_keeps_closed_children_lazy_and_expands_on_request(model, qapp, filtered):
    root, folder = _branch()
    model.set_root(root)
    view = QTreeView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    view.setUniformRowHeights(True)
    view.setModel(model)
    view.sortByColumn(NAME, Qt.SortOrder.AscendingOrder)
    view.setSortingEnabled(True)
    controller = TreeFilter(view, model, view)
    controller.line.setParent(view)
    try:
        model.set_root(root)
        assert controller.proxy.searched is None
        view.expand(model.index_for(root))
        view.show()
        qapp.processEvents()
        if filtered:
            controller.line.setText("folder")
            _settle(qapp, controller)
            assert view.model() is controller.proxy
            assert controller.proxy.searched == frozenset({root})
        assert folder.children.visited == 0 and id(folder) not in model._orders
        assert folder not in model._queried_parents
        controller.line.clear()
        assert controller.proxy.searched is None
        view.expand(model.index_for(folder))
        qapp.processEvents()
        assert view.isExpanded(model.index_for(folder)) and model.rowCount(model.index_for(folder)) == 40
        assert folder.children.visited == 40 and id(folder) in model._orders
        assert model.index(0, 0, model.index_for(folder)).data(NODE_ROLE).name == "folder-file-001"
        if filtered:
            controller.line.setText("folder")
            _settle(qapp, controller)
            assert controller.proxy.searched == frozenset({root, folder})
            assert controller.proxy.rowCount(controller.index_for(folder)) == 40
            _assert_fresh_filter_after_reset(model, view, controller, qapp)
    finally:
        controller.shutdown()
        view.setModel(None)
        controller.proxy.setSourceModel(None)
        view.close()
        view.deleteLater()
