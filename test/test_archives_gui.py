"""Lazy virtual rows stay outside all real-entry actions and stale worker replies."""

from __future__ import annotations

import threading
import time
import zipfile

from PySide6.QtCore import QModelIndex, Qt

from je_file_tree.core.archives import ArchiveCancelledError
from je_file_tree.core.scanner import scan
from je_file_tree.gui.archives import ArchiveController
from je_file_tree.gui.results_view import ResultsView
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.tree_model import ALLOCATED, NAME, NODE_ROLE, SIZE, FolderTreeModel


def _wait(qapp, predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert predicate()


def _fixture(tmp_path):
    archive = tmp_path / "清單.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr("folder/big.txt", b"x" * 2000)
        target.writestr("root.txt", b"x" * 50)
    result = scan(tmp_path)
    return result, next(result.root.iter_files())


def test_virtual_rows_expand_lazily_without_actions_or_scan_totals(qapp, tmp_path):
    result, archive = _fixture(tmp_path)
    view = ResultsView()
    view.show_outcome(analyse(result))
    view.show()
    index = view.tree_model.index_for(archive)
    qapp.processEvents()
    assert not view.archives._workers
    assert view.tree_model.hasChildren(index)
    assert view.tree_model.rowCount(index) == 0
    original = result.root.size, result.root.allocated, result.root.file_count, archive.children
    view.tree.expand(index)
    _wait(qapp, lambda: not view.archives.busy(archive) and view.tree_model.rowCount(index) == 2)
    virtual = view.tree_model.index(0, NAME, index)
    assert virtual.data(NODE_ROLE) is None
    assert view.tree_model.node(virtual) is None
    assert view.tree_model.parent(virtual) == index
    assert "virtual" in virtual.data().lower()
    assert view.tree_model.index(0, SIZE, index).data()
    assert view.tree_model.index(0, ALLOCATED, index).data() == ""
    view.tree.setCurrentIndex(virtual)
    assert view.selected_node() is None
    assert view.selected_nodes() == []
    view.tree_model.sort(NAME, Qt.SortOrder.AscendingOrder)
    folder = view.tree_model.index(0, NAME, index)
    assert view.tree_model.rowCount(folder) == 1
    assert view.tree_model.index(0, NAME, folder).data(NODE_ROLE) is None
    assert original == (result.root.size, result.root.allocated, result.root.file_count, archive.children)
    view.wait_for_lists()
    view.close()


def test_stop_and_reset_invalidate_pending_reads_and_join(qapp, tmp_path, monkeypatch):
    result, archive = _fixture(tmp_path)
    model = FolderTreeModel()
    controller = ArchiveController(model, model)
    model.set_root(result.root)
    started = threading.Event()
    def blocked(_node, *, reader, cancel):
        started.set()
        cancel.wait(5)
        raise ArchiveCancelledError
    monkeypatch.setattr("je_file_tree.gui.archives.read_archive", blocked)
    index = model.index_for(archive)
    model.fetchMore(index)
    _wait(qapp, started.is_set)
    assert controller.busy(archive)
    controller.stop(archive)
    assert not controller.busy(archive)
    assert "stopped" in model.index(0, NAME, index).data().lower()
    model.set_root(None)
    controller.shutdown()
    assert all(not worker.isRunning() for worker in controller._workers)
    assert model.rowCount(QModelIndex()) == 0


def test_rar_missing_tool_remains_a_plain_file_with_reason(qapp, tmp_path, monkeypatch):
    target = tmp_path / "missing.rar"
    target.write_bytes(b"RAR fixture")
    result = scan(tmp_path)
    archive = next(result.root.iter_files())
    model = FolderTreeModel()
    controller = ArchiveController(model, model)
    model.set_root(result.root)
    monkeypatch.setattr("je_file_tree.archive_formats.shutil.which", lambda _program: None)
    index = model.index_for(archive)
    model.fetchMore(index)
    _wait(qapp, lambda: not controller.busy(archive))
    assert model.rowCount(index) == 0
    assert not model.hasChildren(index)
    assert index.data(NODE_ROLE) is archive
    assert "unrar or bsdtar" in index.data(Qt.ItemDataRole.ToolTipRole)
    controller.shutdown()
