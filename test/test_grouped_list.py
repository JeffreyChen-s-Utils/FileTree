"""Grouped cleanup results expose all rows without eagerly formatting every cell."""

from __future__ import annotations

import weakref

import pytest
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


def test_group_labels_preserve_captured_rows_roles_and_persistent_indexes(qapp, monkeypatch):
    model = GroupedListModel()
    tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Fatal)
    nodes = [Node(str(row), False, size=row) for row in range(20_000)]
    icon = QIcon(QPixmap(8, 8))
    model.set_groups([("first", nodes), ("empty", []), ("last", [nodes[-1]])], "MB",
                     tips=["old tip", "empty tip", "last tip"], keepers=[nodes[0], None, None],
                     icons={nodes[-1]: icon})
    captured = model._groups[0].nodes
    pinned = QPersistentModelIndex(model.index(19_999, 2, model.index(0, 0)))
    notifications, resets = [], []
    model.dataChanged.connect(lambda first, last, roles: notifications.append((first, last, roles)))
    model.modelReset.connect(lambda: resets.append(True))
    monkeypatch.setattr(grouped_list, "format_size", lambda *_: pytest.fail("labels must not format file cells"))
    model.set_group_labels([("new title", "new tip"), ("empty", "empty tip"), ("last", None)])
    assert not resets and pinned.isValid() and pinned.data(NODE_ROLE) is nodes[-1]
    assert model._groups[0].nodes is captured and model.rowCount(model.index(0, 0)) == 20_000
    assert model.index(0, 0).data() == "new title" and model.index(0, 0).data(Qt.ToolTipRole) == "new tip"
    assert model.index(2, 0).data(Qt.ToolTipRole) is None
    assert model.index(0, 0).data(NODE_ROLE) is None
    assert model.index(0, 0, model.index(0, 0)).data(Qt.FontRole).bold()
    assert model.index(19_999, 0, model.index(0, 0)).data(Qt.DecorationRole).cacheKey() == icon.cacheKey()
    assert len(notifications) == 2
    for row, (first, last, roles) in zip((0, 2), notifications, strict=True):
        assert first == last == model.index(row, 0)
        assert set(roles) == {Qt.DisplayRole, Qt.ToolTipRole}
    model.set_group_labels([("new title", "new tip"), ("empty", "empty tip"), ("last", None)])
    assert len(notifications) == 2 and tester.model() is model


@pytest.mark.parametrize("labels", [[], [("one", None), ("extra", None)]])
def test_wrong_group_label_count_leaves_existing_data_intact(qapp, labels):
    model = GroupedListModel()
    model.set_groups([("original", [])], "auto", tips=["tip"])
    changed = []
    model.dataChanged.connect(lambda *_: changed.append(True))
    with pytest.raises(ValueError, match="group count"):
        model.set_group_labels(labels)
    assert model.index(0, 0).data() == "original" and model.index(0, 0).data(Qt.ToolTipRole) == "tip"
    assert not changed


def test_empty_group_labels_need_no_model_notification(qapp):
    model = GroupedListModel()
    changed = []
    model.dataChanged.connect(lambda *_: changed.append(True))
    model.set_group_labels([])
    assert model.rowCount() == 0 and not changed


@pytest.mark.parametrize("initial", ["old", "none", "same", "outside"])
def test_keeper_updates_only_matching_name_cells_without_replacing_members(qapp, initial):
    model = GroupedListModel()
    tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Fatal)
    old, chosen, other = Node("old", False), Node("chosen", False), Node("other", False)
    nodes = [old, chosen, other, chosen, old]
    kept = {"old": old, "none": None, "same": chosen, "outside": Node("outsider", False)}[initial]
    model.set_groups([("captured", nodes), ("untouched", [other])], "MB",
                     tips=["tip", "other tip"], keepers=[kept, other])
    captured = model._groups[0].nodes
    parent = model.index(0, 0)
    pinned = QPersistentModelIndex(model.index(3, 2, parent))
    changes, resets = [], []
    model.dataChanged.connect(lambda first, last, roles: changes.append((first, last, roles)))
    model.modelReset.connect(lambda: resets.append(True))
    model.set_group_keeper(0, chosen)
    expected = [] if initial == "same" else ([0, 1, 3, 4] if initial == "old" else [1, 3])
    assert [first.row() for first, _last, _roles in changes] == expected
    for first, last, roles in changes:
        assert first == last and first.parent() == parent and first.column() == 0
        assert set(roles) == {Qt.DisplayRole, Qt.FontRole}
    for row, node in enumerate(nodes):
        index = model.index(row, 0, parent)
        assert index.data(NODE_ROLE) is node
        assert bool(index.data(Qt.FontRole)) == (node is chosen)
        assert (index.data() != node.name) == (node is chosen)
    assert pinned.isValid() and pinned.data(NODE_ROLE) is chosen and not resets
    assert model._groups[0].nodes is captured and model._unit == "MB"
    assert parent.data() == "captured" and parent.data(Qt.ToolTipRole) == "tip"
    assert model.index(0, 0, model.index(1, 0)).data(Qt.FontRole).bold() and tester.model() is model


@pytest.mark.parametrize("row", [-1, 1])
def test_invalid_keeper_group_leaves_the_model_unchanged(qapp, row):
    model = GroupedListModel()
    node = Node("captured", False)
    model.set_groups([("group", [node])], "auto")
    with pytest.raises(IndexError, match="outside"):
        model.set_group_keeper(row, node)
    assert model.index(0, 0, model.index(0, 0)).data(Qt.FontRole) is None


def test_foreign_keeper_is_refused_before_existing_roles_change(qapp):
    model = GroupedListModel()
    old = Node("old", False)
    model.set_groups([("group", [old])], "auto", keepers=[old])
    changes = []
    model.dataChanged.connect(lambda *_: changes.append(True))
    with pytest.raises(ValueError, match="belong"):
        model.set_group_keeper(0, Node("old", False))
    assert model.index(0, 0, model.index(0, 0)).data(Qt.FontRole).bold() and not changes


def test_large_keeper_change_uses_captured_identities_without_formatting_members(qapp, monkeypatch):
    model = GroupedListModel()
    nodes = [Node(str(row), False) for row in range(20_000)]
    old, chosen = nodes[0], nodes[-1]
    model.set_groups([("group", nodes)], "auto", keepers=[old])
    nodes.clear()
    def unexpected(*_args):
        pytest.fail("Keeper changes must not query file cells or sort member paths")
    monkeypatch.setattr(model, "data", unexpected)
    changes = []
    model.dataChanged.connect(lambda first, _last, _roles: changes.append(first.row()))
    model.set_group_keeper(0, chosen)
    assert changes == [0, 19_999] and model.rowCount(model.index(0, 0)) == 20_000
    assert model._groups[0].kept is chosen


def test_unit_change_notifies_size_cells_and_retains_empty_groups_and_persistent_indexes(qapp):
    model = GroupedListModel()
    tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Fatal)
    nodes = [Node(str(row), False, size=1536) for row in range(3)]
    model.set_groups([("first", nodes[:2]), ("empty", []), ("last", nodes[2:])], "auto", keepers=[nodes[0], None, None])
    pinned = QPersistentModelIndex(model.index(1, 2, model.index(0, 0)))
    changes, resets = [], []
    model.dataChanged.connect(lambda first, last, roles: changes.append((first, last, roles)))
    model.modelReset.connect(lambda: resets.append(True))
    model.set_unit("B")
    assert not resets and pinned.isValid() and pinned.data(NODE_ROLE) is nodes[1]
    assert len(changes) == 2
    for (first, last, roles), row, count in zip(changes, (0, 2), (2, 1), strict=True):
        assert first.parent() == last.parent() == model.index(row, 0)
        assert first.row() == 0 and last.row() == count - 1 and first.column() == last.column() == 1
        assert roles == [Qt.DisplayRole] and first.data() == "1,536 B"
    assert model.index(0, 0, model.index(0, 0)).data(Qt.FontRole).bold()
    assert model.rowCount(model.index(1, 0)) == 0 and tester.model() is model


def test_unit_change_is_lazy_and_invalid_or_unchanged_units_leave_captured_state(qapp, monkeypatch):
    model = GroupedListModel()
    nodes = [Node(str(row), False, size=row) for row in range(20_000)]
    model.set_groups([("all", nodes)], "auto")
    captured = model._groups[0].nodes
    nodes.clear()
    calls, changes = [], []
    original = grouped_list.format_size
    monkeypatch.setattr(grouped_list, "format_size", lambda size, unit: calls.append(size) or original(size, unit))
    model.dataChanged.connect(lambda *_: changes.append(True))
    model.set_unit("MB")
    assert calls == [0] and len(changes) == 1 and model._groups[0].nodes is captured
    model.set_unit("MB")
    with pytest.raises(ValueError, match="unknown size unit"):
        model.set_unit("invalid")
    assert len(changes) == 1 and model._unit == "MB"
    assert model.index(19_999, 1, model.index(0, 0)).data() == original(19_999, "MB")
    assert calls[-1] == 19_999


def test_retranslation_notifies_headers_and_every_repeated_keeper_name_only(qapp):
    from je_file_tree.gui import i18n

    language = i18n.current_language()
    model = GroupedListModel()
    kept, extra = Node("kept", False), Node("extra", False)
    model.set_groups([("group", [kept, extra, kept]), ("empty", [])], "B", keepers=[kept, None])
    changes, headers, resets = [], [], []
    model.dataChanged.connect(lambda first, last, roles: changes.append((first, last, roles)))
    model.headerDataChanged.connect(lambda *args: headers.append(args))
    model.modelReset.connect(lambda: resets.append(True))
    try:
        i18n.set_language("ko")
        model.retranslate()
        assert headers == [(Qt.Horizontal, 0, 3)] and not resets
        assert [first.row() for first, _last, _roles in changes] == [0, 2]
        for first, last, roles in changes:
            assert first == last and first.column() == 0 and roles == [Qt.DisplayRole]
            assert first.data() == i18n.tr("duplicates_kept_name", name=kept.name)
        assert model.headerData(0, Qt.Horizontal) == i18n.tr("column_name")
        assert model.index(1, 0, model.index(0, 0)).data() == extra.name
    finally:
        i18n.set_language(language)
