"""Numeric selection groups preserve ordinary model mapping without visiting descendants."""

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QTreeView

from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_filter import TreeFilter
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, SIZE, FolderTreeModel


class _Unopened(list):
    def __iter__(self):
        raise AssertionError("selection mapping visited unopened or out-of-scope descendants")


@pytest.fixture
def groups(qapp):
    outside = Node("outside", True, children=[])
    root = Node("root", True, children=[], parent=outside)
    outside.children = _Unopened([root])
    branches = [Node(name, True, children=[], parent=root) for name in ("alpha", "beta")]
    for branch in branches:
        branch.children.extend(Node(f"file-{row:02d}", False, size=40-row, parent=branch) for row in range(24))
        branch.size = sum(node.size for node in branch.children)
    hidden = Node("unopened", True, children=_Unopened([Node("unread", False)]), parent=root)
    root.children.extend([*branches, hidden])
    source = FolderTreeModel()
    source.set_root(root)
    tree = QTreeView()
    tree.setModel(source)
    controller = TreeFilter(tree, source, tree)
    yield controller, root, branches
    controller.shutdown()
    tree.close()


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("column", [NAME, SIZE])
@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("filtered", [False, True])
def test_numeric_selection_equals_index_mapping_for_sorted_and_frozen_rows(groups, live, column, descending, filtered):
    controller, root, branches = groups
    source, proxy = controller.source, controller.proxy
    source.set_root(root, live=live)
    source.sort(column, Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder)
    for node in [root, *branches]:
        source.rowCount(source.index_for(node))
    arrival = Node("arrival", False, size=100, parent=branches[0])
    branches[0].children.append(arrival)
    missing = Node("missing", False, parent=branches[1])
    virtual = VirtualEntry("virtual", False, parent=branches[1])
    wanted = [root, *branches, *branches[0].children[::2], *branches[1].children[1::3],
              arrival, missing, virtual, root.parent, branches[0].children[2]]
    proxy.allowed = frozenset(id(node) for node in [*root.children, *branches[0].children[::3],
                                                 *branches[1].children[1::2]])
    proxy.setSourceModel(source)
    if filtered:
        controller._switch(True)
    picked = controller._selection(list(reversed(wanted)), filtered)
    indexes = source.indexes_for([node for node in wanted if not isinstance(node, VirtualEntry)])
    mapped = [proxy.mapFromSource(index) if filtered else index for index in indexes]
    expected = {index.data(NODE_ROLE) for index in mapped if index.isValid()}
    assert {index.data(NODE_ROLE) for index in picked.indexes()} == expected
    assert len(picked.indexes()) == len(expected) * source.columnCount()
    if live:
        assert arrival not in expected
    assert missing not in expected and virtual not in expected and root.parent not in expected


@pytest.mark.parametrize("root_hidden", [False, True])
def test_projected_selection_rejects_hidden_ancestors_and_foreign_groups(groups, root_hidden):
    controller, root, branches = groups
    source, proxy = controller.source, controller.proxy
    proxy.allowed = frozenset(id(node) for node in branches[0].children)
    if root_hidden:
        proxy.filterAcceptsRow = lambda *_args: False
    proxy.setSourceModel(source)
    controller.tree.setModel(proxy)
    picked = controller._selection([root, branches[0], *branches[0].children], True)
    assert {index.data(NODE_ROLE) for index in picked.indexes()} == (set() if root_hidden else {root})
    foreign = FolderTreeModel(controller.tree)
    foreign.set_root(Node("foreign", True, children=[]))
    assert proxy.map_selection_rows({foreign.index(0, 0): [0]}) == {}
    assert proxy.map_selection_rows({source.index_for(root).siblingAtColumn(1): [0]}) == {}
    assert proxy.map_selection_rows({QModelIndex(): [-1, 1]}) == {}


@pytest.mark.parametrize("override", ["index", "parent", "index_for", "indexes_for",
                                      "proxy_index", "proxy_parent", "proxy_mapFromSource"])
def test_custom_index_mapping_uses_existing_index_delegation(groups, monkeypatch, override):
    controller, _root, branches = groups
    source, proxy = controller.source, controller.proxy
    wanted = branches[0].children[::2]
    proxy.allowed = frozenset(id(node) for node in [branches[0], *wanted])
    proxy.setSourceModel(source)
    controller._switch(True)
    target, name = (proxy, override.removeprefix("proxy_")) if override.startswith("proxy_") else (source, override)
    monkeypatch.setattr(target, name, getattr(target, name))
    original, calls = controller._index_selection, []

    def legacy(nodes, filtered):
        calls.append((nodes, filtered))
        return original(nodes, filtered)

    monkeypatch.setattr(controller, "_index_selection", legacy)
    picked = controller._selection(wanted, True)
    assert calls == [(wanted, True)]
    assert {index.data(NODE_ROLE) for index in picked.indexes()} == set(wanted)
