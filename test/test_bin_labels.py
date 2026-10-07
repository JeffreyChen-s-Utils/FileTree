"""Per-drive read-only snapshots distinguish unknown totals and discard replaced worker replies."""

import threading
from types import SimpleNamespace

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QWidget

from test_gui import _scanned, _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core.trash_size import TrashUsage
from je_file_tree.gui import bin_labels as labels
from je_file_tree.gui import main_window, welcome
from je_file_tree.gui.i18n import tr


def _volume(root, *, ready=True, total=1000):
    return SimpleNamespace(rootPath=lambda: root, isValid=lambda: True, isReady=lambda: ready,
                           bytesTotal=lambda: total, bytesAvailable=lambda: 500, displayName=lambda: root)


def _sources(monkeypatch, roots=("D:/", "E:/"), selected="D:/"):
    volumes = [_volume(root) for root in roots]
    class Storage:
        def __new__(cls, _path):
            return _volume(selected)
        @staticmethod
        def mountedVolumes():  # noqa: N802 - mirrors Qt's public API
            return volumes
    monkeypatch.setattr(labels, "QStorageInfo", Storage)
    monkeypatch.setattr(welcome, "drives", lambda: volumes)


def test_unknown_partial_and_empty_captions_are_distinct(window):
    root = "D:/"
    assert labels.bin_caption(root, None) == tr("bin_label_unqueried", root=root)
    assert labels.bin_caption(root, TrashUsage(0, 0, True)) == tr(
        "bin_label_total", root=root, size="0 B", count="0")
    partial = labels.bin_caption(root, TrashUsage(123, 2, False, "<denied>"))
    assert "123 B" in partial and "2" in partial and "unknown" in partial and "<denied>" in partial
    assert labels.bin_caption("", None) == tr("bin_label_scope_unknown")
    assert labels.bin_key("D:/folder/..") == labels.bin_key("D:/")


def test_worker_prioritizes_scan_scope_deduplicates_and_caps_roots(qapp, monkeypatch):
    roots = [f"/drive{index}" for index in range(300)]
    _sources(monkeypatch, roots + roots[:2], selected="/priority")
    queries, delivered = [], []
    def query(root, *, cancel):
        assert QThread.currentThread() is not qapp.thread() and not cancel.is_set()
        queries.append(root)
        return TrashUsage(123, 2, True)
    monkeypatch.setattr(labels, "trash_usage", query)
    parent = QWidget()
    worker = labels.BinLabelsWorker("/priority/folder", parent)
    worker.ready.connect(lambda rows, root: delivered.append((rows, root)))
    worker.start()
    _wait(qapp, lambda: not worker.isRunning() and bool(delivered))
    assert queries == ["/priority", *roots[:255]]
    assert len(delivered[0][0]) == 256 and delivered[0][1] == "/priority"
    parent.deleteLater()


def test_replaced_queries_do_not_publish_and_shutdown_joins(qapp, monkeypatch):
    _sources(monkeypatch, roots=("D:/",))
    entered, canceled, replies = threading.Event(), threading.Event(), []
    def query(_root, *, cancel):
        if not entered.is_set():
            entered.set()
            assert cancel.wait(10)
            canceled.set()
            return TrashUsage(99, 9, True)
        return TrashUsage(123, 2, True)
    monkeypatch.setattr(labels, "trash_usage", query)
    parent = QWidget()
    controller = labels.BinLabels(parent)
    controller.ready.connect(lambda rows, root: replies.append((rows, root)))
    controller.refresh()
    _wait(qapp, entered.is_set)
    old = controller._current
    controller.refresh()
    _wait(qapp, lambda: canceled.is_set() and not controller.busy)
    assert len(replies) == 1 and replies[0][0][labels.bin_key("D:/")].size == 123
    assert old.cancel.is_set()
    entered.clear()
    controller.refresh()
    _wait(qapp, entered.is_set)
    active = controller._current
    controller.shutdown()
    assert not active.isRunning() and active.cancel.is_set() and not controller.busy
    qapp.processEvents()
    assert len(replies) == 1
    controller.refresh()
    assert not controller.busy
    parent.deleteLater()


def test_manual_refresh_routes_drive_totals_without_scan_or_cleanup_actions(
        window, qapp, sample_tree, monkeypatch):
    _sources(monkeypatch)
    window.welcome.refresh_drives()
    calls = []
    def query(root, *, cancel):
        calls.append(root)
        return TrashUsage(123, 2, False, "<denied>") if root == "D:/" else TrashUsage(0, 0, True)
    monkeypatch.setattr(labels, "trash_usage", query)
    assert not calls and window.welcome.bin_refresh.isEnabled()
    assert not window.results.cleanup.bin_refresh.isEnabled()
    window.welcome.bin_refresh.click()
    _wait(qapp, lambda: not window._bin_labels.busy)
    caption = window.welcome._bin_labels[labels.bin_key("D:/")][1]
    assert caption.textFormat() == Qt.TextFormat.PlainText and "<denied>" in caption.text()
    assert window.results.outcome is None and calls == ["D:/", "E:/"]
    _scanned(window, qapp, sample_tree)
    assert window.results.cleanup.bin_refresh.isEnabled()
    window.results.cleanup.bin_refresh.click()
    _wait(qapp, lambda: not window._bin_labels.busy)
    assert window.results.cleanup.bin_totals.text() == caption.text()
    assert window.results.cleanup.bin_totals.textFormat() == Qt.TextFormat.PlainText
    original = window.results.outcome
    window.set_unit("KB")
    assert "KB" in window.results.cleanup.bin_totals.text()
    assert window.results.outcome is original


def test_bin_manager_close_refreshes_labels_and_scan_invalidates_late_reply(
        window, qapp, sample_tree, monkeypatch):
    _sources(monkeypatch, roots=("D:/",))
    entered = threading.Event()
    def query(_root, *, cancel):
        entered.set()
        assert cancel.wait(10)
        return TrashUsage(99, 9, True)
    monkeypatch.setattr(labels, "trash_usage", query)
    class Dialog:
        scan_requested = SimpleNamespace(connect=lambda _callback: None)
        def __init__(self, *_args):
            self.closed = False
        def exec(self):
            return 0
        def shutdown(self):
            self.closed = True
        def deleteLater(self):  # noqa: N802 - mirrors Qt's public API
            assert self.closed
    monkeypatch.setattr(main_window, "BinDialog", Dialog)
    window.show_bins()
    _wait(qapp, entered.is_set)
    _scanned(window, qapp, sample_tree)
    _wait(qapp, lambda: not window._bin_labels._running)
    assert not window.welcome._bin_data
    assert window.results.cleanup.bin_totals.text() == tr("bin_label_scope_unknown")


def test_nonready_and_zero_capacity_roots_are_not_queried(qapp, monkeypatch):
    volumes = [_volume("/denied", ready=False), _volume("/zero", total=0), _volume("/valid")]
    monkeypatch.setattr(labels, "QStorageInfo", SimpleNamespace(mountedVolumes=lambda: volumes))
    calls, replies = [], []
    monkeypatch.setattr(labels, "trash_usage", lambda root, **_kwargs: calls.append(root) or TrashUsage(0, 0, True))
    parent = QWidget()
    worker = labels.BinLabelsWorker("", parent)
    worker.ready.connect(lambda rows, root: replies.append((rows, root)))
    worker.start()
    _wait(qapp, lambda: not worker.isRunning() and bool(replies))
    assert calls == ["/valid"] and replies[0][1] == ""
    parent.deleteLater()
