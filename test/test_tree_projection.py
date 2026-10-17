"""Direct group mappings preserve Qt delegation, notifications and bounded sibling lookups."""

import pytest
from PySide6.QtCore import (
    QAbstractItemModel, QCoreApplication, QEvent, QModelIndex, QPersistentModelIndex, Qt, qInstallMessageHandler,
)
from PySide6.QtTest import QAbstractItemModelTester

from test_tree_row_identity import model as model  # noqa: PLC0414 - shared owned-model cleanup
from je_file_tree.core.node import Node
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.gui.tree_filter import ExpandedTreeProxy
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, SIZE, FolderTreeModel


def _root(count=100):
    root = Node("root", True, children=[])
    root.children.extend(Node(f"file-{row:04d}", False, size=count-row, parent=root) for row in range(count))
    return root


def _proxy(model, root, accepted=None):
    model.set_root(root)
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset(id(node) for node in (root.children if accepted is None else accepted))
    return proxy, proxy.index(0, NAME)


def test_bulk_reverse_mapping_never_searches_for_individual_file_rows(model, monkeypatch):
    root = _root(2000)
    proxy, parent = _proxy(model, root)
    assert proxy.rowCount(parent) == 2000
    lookups = []
    original = model.index_for

    def index_for(node):
        lookups.append(node)
        return original(node)

    monkeypatch.setattr(model, "index_for", index_for)
    for row in range(0, 2000, 7):
        mapped = proxy.mapToSource(proxy.index(row, SIZE, parent))
        assert mapped.isValid() and mapped.row() == row and mapped.column() == SIZE
        assert mapped.data(NODE_ROLE) is root.children[row]
    assert all(node.is_dir for node in lookups), "mapping must not repeat linear file-position searches"


def test_prepared_group_flags_and_data_do_not_dispatch_source_indexes_per_row(model, monkeypatch):
    root = _root(1000)
    proxy, parent = _proxy(model, root)
    assert proxy.rowCount(parent) == 1000
    calls = []
    original = model.index

    def index(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(model, "index", index)
    for row in range(1000):
        item = proxy.index(row, NAME, parent)
        assert proxy.flags(item) == QAbstractItemModel.flags(model, model.createIndex(row, NAME, root.children[row]))
        assert proxy.data(item, NODE_ROLE) is root.children[row]
    assert not calls


def test_display_notifications_map_only_affected_visible_rows(model):
    root = _root(10)
    proxy, parent = _proxy(model, root, root.children[::2])
    assert proxy.rowCount(parent) == 5
    notices = []
    proxy.dataChanged.connect(lambda first, last, roles: notices.append((first, last, roles)))
    source_parent = model.index(0, NAME)
    model.dataChanged.emit(model.index(3, SIZE, source_parent), model.index(7, SIZE, source_parent),
                           [Qt.ItemDataRole.DisplayRole])
    first, last, roles = notices.pop()
    assert (first.row(), last.row(), first.column(), last.column()) == (2, 3, SIZE, SIZE)
    assert first.parent() == parent and roles == [Qt.ItemDataRole.DisplayRole]
    model.dataChanged.emit(model.index(1, SIZE, source_parent), model.index(1, SIZE, source_parent), [])
    assert not notices


def test_source_overrides_keep_their_flags_and_data(model, monkeypatch):
    root = _root(3)
    proxy, parent = _proxy(model, root)
    item = proxy.index(1, NAME, parent)
    custom = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled
    monkeypatch.setattr(model, "flags", lambda _index: custom)
    original = model.data
    monkeypatch.setattr(model, "data", lambda index, role=Qt.ItemDataRole.DisplayRole:
                        "custom" if role == Qt.ItemDataRole.DisplayRole else original(index, role))
    assert proxy.flags(item) == custom and proxy.data(item) == "custom"
    assert proxy.data(item, NODE_ROLE) is root.children[1]


def test_filtered_ancestor_cannot_become_a_second_top_level_root(model):
    root = _root(1)
    branch = Node("hidden", True, children=[], parent=root)
    child = Node("accepted child", False, parent=branch)
    branch.children.append(child)
    root.children.append(branch)
    proxy, _parent = _proxy(model, root, [child])
    assert not proxy.mapFromSource(model.index_for(branch)).isValid()
    assert not proxy.mapFromSource(model.index_for(child)).isValid()


def test_custom_predicate_can_supply_membership_and_reverse_mappings(model):
    root = _root(5)
    model.set_root(root)

    class Alternate(ExpandedTreeProxy):
        def filterAcceptsRow(self, row, parent):  # noqa: N802 - retained proxy extension point
            return row % 2 == 0

    proxy = Alternate(model, model)
    parent = proxy.index(0, NAME)
    assert proxy.rowCount(parent) == 3
    for row in range(3):
        source = model.index(row*2, SIZE, model.index(0, NAME))
        mapped = proxy.mapFromSource(source)
        assert mapped.isValid() and mapped.row() == row
        assert proxy.mapToSource(mapped) == source


def test_custom_root_rejection_is_cached_until_membership_invalidation(model):
    root = _root(3)
    model.set_root(root)

    class RootChoice(ExpandedTreeProxy):
        calls = 0
        accept_root = False

        def filterAcceptsRow(self, row, parent):  # noqa: N802 - retained proxy extension point
            self.calls += 1
            return self.accept_root if not parent.isValid() else True

    proxy = RootChoice(model, model)
    assert proxy.rowCount() == 0 and not proxy.index(0, NAME).isValid()
    assert not proxy.mapFromSource(model.index_for(root)).isValid()
    calls = proxy.calls
    changes = []
    proxy.dataChanged.connect(lambda *args: changes.append(args))
    model.set_unit("KB")
    model.set_drive_total(1000)
    assert proxy.calls == calls and not changes
    proxy.accept_root = True
    proxy.invalidate()
    assert proxy.rowCount() == 1 and proxy.rowCount(proxy.index(0, NAME)) == 3


def test_nested_persistent_entries_and_source_headers_survive_branch_changes(model):
    root = _root(3)
    branch = Node("branch", True, children=[], parent=root)
    member = Node("member", False, parent=branch)
    branch.children.append(member)
    root.children.append(branch)
    proxy, parent = _proxy(model, root, [*root.children, member])
    persistent = QPersistentModelIndex(proxy.mapFromSource(model.index_for(member)))
    assert persistent.parent().data(NODE_ROLE) is branch
    headers = []
    proxy.headerDataChanged.connect(lambda *args: headers.append(args))
    model.retranslate()
    assert headers == [(Qt.Orientation.Horizontal, 0, model.columnCount()-1)]
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    assert persistent.data(NODE_ROLE) is member and persistent.parent().data(NODE_ROLE) is branch
    fresh = Node("fresh", True, children=[])
    proxy.allowed = proxy.allowed | {id(fresh)}
    model.replace(branch, fresh)
    assert not persistent.isValid()
    assert proxy.mapFromSource(model.index_for(fresh)).isValid()
    assert proxy.rowCount(parent) == 4


def test_foreign_indexes_and_display_roles_preserve_source_semantics(model):
    root = _root(3)
    proxy, parent = _proxy(model, root)
    foreign = FolderTreeModel(model)
    foreign.set_root(_root(1))
    assert not proxy.mapFromSource(foreign.index(0, NAME)).isValid()
    assert not proxy.mapToSource(foreign.index(0, NAME)).isValid()
    assert proxy.rowCount(foreign.index(0, NAME)) == 0
    assert proxy.flags(QModelIndex()) == Qt.ItemFlag.NoItemFlags
    roles = (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole, Qt.ItemDataRole.ForegroundRole,
             Qt.ItemDataRole.TextAlignmentRole, NODE_ROLE)
    for row in range(3):
        for column in range(model.columnCount()):
            item = proxy.index(row, column, parent)
            source = proxy.mapToSource(item)
            assert all(item.data(role) == source.data(role) for role in roles)


def test_explicit_row_count_skips_wholly_virtual_archive_members(model):
    class HiddenMembers(list):
        def __iter__(self):
            raise AssertionError("filtered row count walked hidden archive members")

    root = _root(1)
    archive = root.children[0]
    model.set_root(root)
    model.set_archive(archive, HiddenMembers([VirtualEntry("hidden", False, parent=archive)]))
    proxy = ExpandedTreeProxy(model, model)
    proxy.allowed = frozenset({id(root), id(archive)})
    proxy.searched = frozenset({root, archive})
    parent = proxy.mapFromSource(model.index_for(archive))
    assert proxy.rowCount(parent) == 0
    assert not proxy.hasChildren(parent)


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("column", [NAME, SIZE])
def test_qt_model_contract_through_sort_membership_refresh_and_removal(model, live, column):
    root = _root(12)
    root.size, root.file_count = sum(node.size for node in root.children), 12
    proxy, parent = _proxy(model, root)
    proxy.searched = frozenset({root})
    model.set_root(root, live=live)
    model.sort(column, Qt.SortOrder.AscendingOrder)
    parent = proxy.index(0, NAME)
    notices = []
    previous = qInstallMessageHandler(lambda _kind, context, message: notices.append((context.category, message)))
    tester = QAbstractItemModelTester(proxy, QAbstractItemModelTester.FailureReportingMode.Warning, model)
    tester.setUseFetchMore(False)
    kept = root.children[4]
    persistent = QPersistentModelIndex(proxy.mapFromSource(model.index_for(kept)))
    try:
        model.sort(column, Qt.SortOrder.DescendingOrder)
        assert persistent.isValid() and persistent.data(NODE_ROLE) is kept
        hidden = root.children[0]
        proxy.allowed = frozenset(id(node) for node in root.children if node is not hidden)
        proxy.invalidate()
        assert proxy.rowCount(parent) == 11 and not proxy.mapFromSource(model.index_for(hidden)).isValid()
        arrival = Node("arrival", False, size=20, parent=root)
        root.children.append(arrival)
        proxy.allowed = proxy.allowed | {id(arrival)}
        assert proxy.rowCount(parent) == 11
        model.refresh()
        assert proxy.rowCount(parent) == 12
        model.remove_many([root.children[1]])
        assert proxy.rowCount(parent) == 11 and persistent.data(NODE_ROLE) is kept
        archive = root.children[2]
        model.set_archive(archive, [VirtualEntry("preview", False, parent=archive)])
        assert not proxy.hasChildren(proxy.mapFromSource(model.index_for(archive)))
        model.set_root(None)
        assert not persistent.isValid() and proxy.rowCount() == 0
        assert not [message for category, message in notices if category == "qt.modeltest" and "FAIL!" in message]
    finally:
        tester.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qInstallMessageHandler(previous)


def test_source_destruction_and_rebinding_drop_cached_groups(qapp):
    owner = FolderTreeModel()
    source = FolderTreeModel()
    root = _root(3)
    proxy = ExpandedTreeProxy(source, owner)
    source.set_root(root)
    proxy.allowed = frozenset(id(node) for node in root.children)
    assert proxy.rowCount(proxy.index(0, NAME)) == 3
    source.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert proxy.sourceModel() is None and proxy.rowCount() == 0
    replacement = _root(2)
    owner.set_root(replacement)
    proxy.setSourceModel(owner)
    proxy.allowed = frozenset(id(node) for node in replacement.children)
    assert proxy.rowCount(proxy.index(0, NAME)) == 2
    proxy.setSourceModel(None)
    assert not proxy._groups and proxy._root is None
    owner.deleteLater()
