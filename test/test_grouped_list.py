"""Grouped cleanup results expose all rows without eagerly formatting every cell."""

from __future__ import annotations

import weakref

from PySide6.QtCore import QPersistentModelIndex, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtTest import QAbstractItemModelTester

from je_file_tree.core.formatting import format_size, format_time
from je_file_tree.core.node import Node
from je_file_tree.gui import grouped_list
from je_file_tree.gui.grouped_list import GroupedListModel
from je_file_tree.gui.tree_model import NODE_ROLE


def test_complete_group_shape_and_roles(qapp):
    model = GroupedListModel()
    tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Fatal)
    root = Node("captured", True)
    node = Node("one", False, size=1500, modified=1_600_000_000, parent=root)
    model.set_groups([("first", [node]), ("empty", [])], "auto", tips=["explanation", "empty tip"])
    group = model.index(0, 0)
    assert model.rowCount() == 2 and model.columnCount() == 4
    assert group.data() == "first" and group.data(NODE_ROLE) is None
    assert group.data(Qt.ToolTipRole) == "explanation"
    assert model.hasChildren(group)
    assert not model.hasChildren(model.index(1, 0))
    assert model.rowCount(model.index(0, 1)) == 0
    for column, text in enumerate([node.name, format_size(node.size), root.path, format_time(node.modified)]):
        child = model.index(0, column, group)
        assert child.parent() == group and child.data() == text
        assert child.data(NODE_ROLE) is node and child.data(Qt.ToolTipRole) == node.path
        assert not model.hasChildren(child) and model.rowCount(child) == 0
        assert not model.flags(child) & Qt.ItemIsEditable
    assert model.index(0, 1, group).data(Qt.TextAlignmentRole) & Qt.AlignRight
    assert not model.index(-1, 0).isValid() and not model.index(2, 0).isValid()
    assert not model.index(0, 4).isValid() and not model.index(1, 0, group).isValid()
    assert tester.model() is model


def test_capture_is_lazy_and_freezes_membership(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(grouped_list, "format_size", lambda *_args: calls.append("size") or "size")
    monkeypatch.setattr(grouped_list, "format_time", lambda *_args: calls.append("time") or "time")
    model = GroupedListModel()
    nodes = [Node(str(row), False, size=row) for row in range(20_000)]
    model.set_groups([("all rows", nodes)], "auto")
    parent = model.index(0, 0)
    assert not calls and model.rowCount(parent) == 20_000
    nodes.clear()
    assert model.rowCount(parent) == 20_000
    assert model.index(19_999, 0, parent).data(NODE_ROLE).name == "19999"
    assert not calls
    assert model.index(19_999, 1, parent).data() == "size"
    assert calls == ["size"]
    assert model.index(19_999, 3, parent).data() == "time"
    assert calls == ["size", "time"]


def test_kept_label_font_and_photo_icon_are_cell_roles(qapp):
    model = GroupedListModel()
    kept, extra = Node("kept", False), Node("extra", False)
    pixmap = QPixmap(8, 8)
    pixmap.fill(Qt.red)
    icon = QIcon(pixmap)
    model.set_groups([("duplicates", [kept, extra])], "auto", keepers=[kept], icons={extra: icon})
    parent = model.index(0, 0)
    first, second = model.index(0, 0, parent), model.index(1, 0, parent)
    assert first.data().endswith(kept.name) and first.data() != kept.name
    assert first.data(Qt.FontRole).bold()
    assert first.data(NODE_ROLE) is kept
    assert second.data(Qt.FontRole) is None and second.data() == extra.name
    assert second.data(Qt.DecorationRole).cacheKey() == icon.cacheKey()
    assert model.index(1, 1, parent).data(Qt.DecorationRole) is None


def test_fill_expands_groups_and_selection_keeps_real_nodes(qapp):
    model = GroupedListModel()
    view = grouped_list.build_view(model)
    nodes = [Node(str(row), False) for row in range(5)]
    grouped_list.fill(model, view, [("first", nodes[:3]), ("second", nodes[3:]), ("empty", [])], "auto")
    assert view.isExpanded(model.index(0, 0)) and view.isExpanded(model.index(1, 0))
    assert view.isFirstColumnSpanned(0, model.index(0, 0).parent())
    grouped_list.select_entries(model, view, skip_first=True)
    assert [index.data(NODE_ROLE) for index in view.selectionModel().selectedRows()] == [nodes[1], nodes[2], nodes[4]]
    grouped_list.select_group(model, view, 1)
    assert [index.data(NODE_ROLE) for index in view.selectionModel().selectedRows()] == nodes[3:]
    pinned = QPersistentModelIndex(model.index(0, 0, model.index(0, 0)))
    grouped_list.fill(model, view, [], "auto")
    assert not pinned.isValid() and not view.selectionModel().selectedRows()
    assert model.rowCount() == 0 and model.columnCount() == 4
    view.setModel(None)
    view.close()


def test_wide_view_formats_visible_cells_only_and_releases_old_rows(qapp, monkeypatch):
    calls = []
    original = grouped_list.format_size
    monkeypatch.setattr(grouped_list, "format_size", lambda *args: calls.append(args) or original(*args))
    class CapturedNode(Node):
        pass
    model = GroupedListModel()
    view = grouped_list.build_view(model)
    view.resize(900, 400)
    nodes = [CapturedNode(str(row), False, size=row) for row in range(10_000)]
    oldest = weakref.ref(nodes[0])
    view.show()
    grouped_list.fill(model, view, [("all entries", nodes)], "auto")
    qapp.processEvents()
    assert model.rowCount(model.index(0, 0)) == 10_000
    assert 0 < len(calls) < 100
    last = model.index(9999, 0, model.index(0, 0))
    view.scrollTo(last)
    qapp.processEvents()
    assert last.data(NODE_ROLE) is nodes[-1]
    assert len(calls) < 200
    nodes.clear()
    assert oldest() is not None
    grouped_list.fill(model, view, [], "auto")
    assert oldest() is None
    view.setModel(None)
    view.close()
