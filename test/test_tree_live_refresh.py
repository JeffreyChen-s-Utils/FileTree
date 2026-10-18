"""Live ticks repaint unchanged shown rows and relayout every structural change (U-20261017-76)."""

from PySide6.QtCore import Qt

from je_file_tree.core.node import Node
from je_file_tree.gui.tree_model import NAME, NODE_ROLE, SIZE, FolderTreeModel


def _live_tree():
    root = Node("root", True, size=60, children=[])
    folder = Node("folder", True, size=30, children=[], parent=root)
    empty = Node("empty", True, size=0, children=[], parent=root)
    files = [Node(f"file{n}", False, size=10 * (n + 1), parent=root) for n in range(2)]
    root.children.extend([folder, empty, *files])
    model = FolderTreeModel()
    model.set_root(root, live=True)
    model.sort(SIZE, Qt.SortOrder.DescendingOrder)
    return model, root, folder, empty


def _show(model, node):
    parent = model.index_for(node)
    return [model.index(row, NAME, parent).data(NODE_ROLE) for row in range(model.rowCount(parent))]


def _record(model):
    events = {"layouts": 0, "changes": []}
    model.layoutChanged.connect(lambda *_: events.__setitem__("layouts", events["layouts"] + 1))
    model.dataChanged.connect(lambda first, last, _roles=None: events["changes"].append(
        (first.data(NODE_ROLE), last.data(NODE_ROLE), first.column(), last.column())))
    return events


def test_unchanged_members_and_order_only_repaint_root_and_folder_rows(qapp):
    model, root, folder, empty = _live_tree()
    _show(model, root)
    model.refresh()  # the first live tick learns which shown folders have entries
    events = _record(model)
    folder.size = 31
    root.size = 61
    model.refresh()
    assert events["layouts"] == 0
    # Rows by size: folder (31), file1 (20), file0 (10), empty (0): two folder runs; file rows are not notified.
    assert [change[:2] for change in events["changes"]] == [(root, root), (folder, folder), (empty, empty)]
    assert all(change[2:] == (0, model.columnCount() - 1) for change in events["changes"])
    assert _show(model, root) == [folder, root.children[3], root.children[2], empty]


def test_new_rows_reordering_and_first_entries_relayout(qapp):
    model, root, folder, empty = _live_tree()
    _show(model, root)
    model.refresh()
    events = _record(model)
    root.children.append(Node("arrival", False, size=5, parent=root))
    model.refresh()
    assert events["layouts"] == 1 and [node.name for node in _show(model, root)][-2:] == ["arrival", "empty"]
    root.children[-1].size = 500  # now the largest entry under the size-descending order
    model.refresh()
    assert events["layouts"] == 2 and _show(model, root)[0].name == "arrival"
    empty.children.append(Node("first", False, size=1, parent=empty))
    model.refresh()
    assert events["layouts"] == 3 and model.hasChildren(model.index_for(empty))


def test_a_finished_scan_never_takes_the_live_repaint_path(qapp):
    model, root, folder, _empty = _live_tree()
    _show(model, root)
    model.finish_live()
    events = _record(model)
    model.refresh()
    assert events["layouts"] == 1
