"""Similar-photo mode captures options and leaves exact-duplicate decisions unavailable."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QItemSelectionModel

from je_file_tree.core.scanner import scan
from je_file_tree.core.similar_photos import PhotoSearchCancelledError
from je_file_tree.gui.duplicates_panel import DuplicatesPanel
from je_file_tree.gui.tree_model import NODE_ROLE

from test_similar_photos import _photos


def _wait(qapp, predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(.005)
    assert predicate()


def test_similar_mode_has_thumbnails_but_no_exact_keeper_or_extra_selection(qapp, tmp_path):
    root = _photos(tmp_path)
    panel = DuplicatesPanel()
    panel.set_root(root)
    panel.kind.setCurrentIndex(panel.kind.findData("photos"))
    panel.min_size.setCurrentIndex(0)
    panel.start()
    _wait(qapp, lambda: not panel.running)
    assert panel._photos.files_read == 3
    assert panel.model.rowCount() == 1
    item = panel.model.item(0).child(0, 0)
    assert not item.icon().isNull()
    assert item.data(NODE_ROLE).is_in(root)
    panel.view.selectionModel().setCurrentIndex(item.index(), QItemSelectionModel.SelectionFlag.ClearAndSelect)
    assert not panel.keep_selected.isEnabled()
    assert not panel.select_extra.isEnabled()
    assert panel.decisions_for([item.data(NODE_ROLE)]) == []
    assert panel.groups == []
    panel.choose_kept_copy()
    panel.select_extra_copies()
    assert panel._savings is None
    panel.prune()
    assert panel._photos is None
    panel.kind.setCurrentIndex(panel.kind.findData("exact"))
    assert panel._photos is None
    assert panel.model.rowCount() == 0
    panel.stop(wait=True)
    panel.close()


def test_captured_threshold_and_stop_ignore_late_photo_result(qapp, tmp_path, monkeypatch):
    root = _photos(tmp_path)
    panel = DuplicatesPanel()
    panel.set_root(root)
    panel.kind.setCurrentIndex(panel.kind.findData("photos"))
    panel.min_size.setCurrentIndex(0)
    captured, started = [], threading.Event()
    def blocked(_root, *, min_size, distance, cancel, progress):
        captured.append((min_size, distance))
        started.set()
        cancel.wait(5)
        raise PhotoSearchCancelledError
    monkeypatch.setattr("je_file_tree.photo_reader.find_similar_photos", blocked)
    panel.distance.setValue(3)
    panel.start()
    _wait(qapp, started.is_set)
    assert not panel.kind.isEnabled()
    assert not panel.distance.isEnabled()
    panel.distance.setValue(12)
    panel.set_root(scan(tmp_path).root)
    panel.stop(wait=True)
    assert captured == [(1, 3)]
    assert panel._photos is None
    assert panel.model.rowCount() == 0
    assert all(not worker.isRunning() for worker in panel._search_workers)
    panel.close()
