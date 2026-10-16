"""Selection mapping uses temporary requested rows without retaining every selected file."""

import pytest
from PySide6.QtCore import Qt

from test_tree_row_identity import model as model  # noqa: PLC0414 - owned cleanup
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_model import NAME, SIZE, FolderTreeModel


class _CountedRows(list):
    visited = 0

    def __iter__(self):
        for node in super().__iter__():
            self.visited += 1
            yield node


class _Unopened(list):
    def __iter__(self):
        raise AssertionError("selection mapping visited unrelated descendants")


def _root(count):
    root = Node("root", True, children=[])
    root.children = _CountedRows(Node(f"file-{row:04d}", False, size=count-row, parent=root) for row in range(count))
    return root


@pytest.mark.parametrize("step", [1, 8])
def test_bulk_selection_does_not_grow_the_shared_file_row_cache(model, step):
    root = _root(4000)
    model.set_root(root)
    model.indexes_for(root.children[:16])  # Existing cache from a separate generic index lookup stays valid.
    before = dict(model._rows)
    wanted = root.children[16::step]
    root.children.visited = 0
    groups = model.selection_rows(wanted)
    parent = model.index_for(root)
    assert groups == {parent: list(range(16, 4000, step))}
    assert root.children.visited <= len(root.children), "one sibling pass for the requested parent"
    assert model._rows == before, "a selection must not leave every requested file in the shared cache"


@pytest.mark.parametrize("count", [8, 40])
@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("column", [NAME, SIZE])
@pytest.mark.parametrize("descending", [False, True])
def test_groups_preserve_input_order_duplicates_scope_and_frozen_membership(model, count, live, column, descending):
    root = _root(count)
    outside = Node("outside", True, children=_Unopened([root]))
    root.parent = outside
    unopened = Node("unopened", True, parent=root, children=_Unopened([Node("untouched", False)]))
    root.children.append(unopened)
    model.set_root(root, live=live)
    model.sort(column, Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder)
    parent = model.index_for(root)
    model.rowCount(parent)
    arrival = Node("arrival", False, size=10000, parent=root)
    root.children.append(arrival)
    missing = Node("missing", False, parent=root)
    virtual = VirtualEntry("virtual", False, parent=root)
    wanted = [root, *reversed(root.children), root.children[0], missing, outside, virtual, root]
    actual = model.selection_rows(iter(wanted))
    expected = {}
    for node in wanted:
        if isinstance(node, VirtualEntry):
            continue
        index = model.index_for(node)
        if index.isValid():
            expected.setdefault(index.parent(), []).append(index.row())
    assert actual == expected
    assert not model.index_for(missing).isValid()
    if live:
        assert not model.index_for(arrival).isValid()
        model.refresh()
        restored = model.selection_rows([arrival, root.children[0]])
        expected_rows = [model.index_for(arrival).row(), model.index_for(root.children[0]).row()]
        assert restored == {model.index_for(root): expected_rows}


@pytest.mark.parametrize("name", ["_row_of", "_prime_rows"])
@pytest.mark.parametrize("subclass", [False, True])
def test_custom_row_lookup_keeps_its_existing_mapping_semantics(qapp, monkeypatch, name, subclass):
    root = _root(40)
    missing = root.children[0]
    original = getattr(FolderTreeModel, name)

    def row_of(self, node):
        return -1 if node is missing else original(self, node)

    def prime_rows(self, nodes):
        original(self, nodes)
        self._rows[id(missing)] = -1

    replacement = row_of if name == "_row_of" else prime_rows
    source_type = type("CustomRows", (FolderTreeModel,), {name: replacement}) if subclass else FolderTreeModel
    source = source_type()
    source.set_root(root)
    try:
        if not subclass:
            monkeypatch.setattr(source, name, replacement.__get__(source, source_type))
        assert source.selection_rows(root.children) == {source.index_for(root): list(range(1, 40))}
    finally:
        source.set_root(None)
        source.deleteLater()
