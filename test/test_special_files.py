"""Special metadata is read from snapshots; recall is not a download or provider inference."""

import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core.node import Node
from je_file_tree.core.scanner import EXCLUDED, PARTIAL_FOLDER
from je_file_tree.core.snapshot import pack_snapshot
from je_file_tree.core.special_files import SpecialEntry, special_files
from je_file_tree.gui.special_files import SpecialFilesDialog, SpecialFilesModel
from je_file_tree.gui.tree_model import NODE_ROLE
from je_file_tree.gui.i18n import tr
from test_gui import _wait


def _file(root, name, size, allocation, flags=0):
    node = Node(name, False, size=size, allocated=allocation, parent=root)
    node.snapshot = pack_snapshot(SimpleNamespace(st_dev=1, st_ino=2, st_size=size, st_mode=0o100644,
                                                  st_mtime_ns=0, st_ctime_ns=0, st_nlink=1,
                                                  st_file_attributes=flags))
    root.children.append(node)
    return node


def test_recorded_flags_and_unknown_lower_allocation_without_filesystem_access(monkeypatch):
    root = Node("no-existing-folder", True, children=[])
    recall = _file(root, "cloud", 1000, 0, 0x400000 | 0x1000)
    packed = _file(root, "packed", 500, 100, 0x200 | 0x800)
    lower = _file(root, "resident-or-other", 50, 0)
    _file(root, "ordinary", 100, 4096)

    def forbidden(*_args, **_kwargs):
        pytest.fail("No filesystem/content reads are allowed in this metadata survey")

    import builtins
    import os
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(os, "stat", forbidden)
        patch.setattr(os, "lstat", forbidden)
        result = special_files(root)
    assert [(row.node, row.states) for row in result.rows] == [
        (recall, ("recall", "offline")), (packed, ("compressed", "sparse")), (lower, ("allocation_low",))]
    assert (result.count, result.logical, result.allocated, result.unknown) == (3, 1550, 100, 0)


def test_bounded_rows_preserve_complete_totals_and_partial_children():
    root = Node("fake", True, children=[], error=PARTIAL_FOLDER)
    for size in range(1, 201):
        _file(root, str(size), size, 0, 0x40000)
    omitted = Node("omitted", True, parent=root, children=[], error=EXCLUDED)
    root.children.append(omitted)
    missing = _file(root, "unavailable", 1, 1)
    missing.snapshot = None
    link = _file(root, "link", 999999, 0, 0x1000)
    link.is_link = True
    result = special_files(root, limit=7)
    assert len(result.rows) == 7 and result.rows[0].node.size == 200
    assert result.count == 200 and result.logical == sum(range(1, 201))
    assert result.unknown == 1 and result.incomplete
    cancel = threading.Event()
    cancel.set()
    assert special_files(root, cancel=cancel) is None
    with pytest.raises(ValueError):
        special_files(root, limit=0)


def test_deep_tree_is_iterative_and_cancellation_is_checked_per_entry():
    root = Node("fake", True, children=[])
    parent = root
    for level in range(1200):
        child = Node(str(level), True, parent=parent, children=[])
        parent.children.append(child)
        parent = child
    leaf = _file(parent, "leaf", 70, 0, 0x1000)
    assert special_files(root).rows[0].node is leaf


def test_model_describes_full_content_without_predicting_downloaded_allocation(qapp):
    root = Node("fake", True, children=[])
    node = _file(root, "cloud.bin", 1024, 0, 0x400000)
    model = SpecialFilesModel()
    model.set_rows([SpecialEntry(node, ("recall",))])
    assert model.index(0, 0).data(NODE_ROLE) is node
    assert model.index(0, 2).data() == "1.0 KB"
    assert model.index(0, 3).data() == "0 B"
    assert "recall" in model.index(0, 1).data().lower()


def test_dialog_worker_stop_selection_and_queued_reply_after_close(qapp):
    root = Node("fake", True, children=[])
    node = _file(root, "cloud.bin", 1024, 0, 0x400000)
    dialog = SpecialFilesDialog(root, "auto", partial=True)
    chosen = []
    dialog.selected.connect(chosen.append)
    _wait(qapp, lambda: dialog.model.rowCount() == 1)
    assert "incomplete" in dialog.status.text()
    assert "unknown" in dialog.hint.text() and "no files are opened" in dialog.hint.text()
    dialog._select(dialog.proxy.index(0, 0))
    assert chosen == [node] and not dialog.worker.isRunning()
    dialog._show(special_files(root))
    assert dialog._closed
    dialog.deleteLater()

    dialog = SpecialFilesDialog(root, "auto")
    dialog.stop()
    _wait(qapp, lambda: not dialog.worker.isRunning())
    assert dialog.model.rowCount() == 0 and dialog.status.text() == tr("scan_cancelled")
    dialog.reject()
    dialog.deleteLater()
