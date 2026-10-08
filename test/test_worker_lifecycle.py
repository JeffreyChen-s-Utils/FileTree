"""GUI timers must keep running while slow owned workers are being canceled or replaced."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, QThread, QTimer
from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export

from je_file_tree.gui import scan_worker, welcome
from je_file_tree.gui.worker_lifecycle import after_threads


def _pump(app, done, timeout=5):
    deadline = time.monotonic() + timeout
    while not done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert done(), "GUI continuation did not complete"


class HeldWorker(QThread):
    def __init__(self, parent):
        super().__init__(parent)
        self.release = threading.Event()

    def run(self):
        self.release.wait(5)


def test_async_join_keeps_gui_timers_live_and_calls_back_once(qapp):
    owner = QObject()
    worker = HeldWorker(owner)
    callbacks = []
    worker.start()
    after_threads((worker,), lambda: callbacks.append(QThread.currentThread()), owner)
    assert not callbacks
    timer = QTimer(owner)
    timer.setSingleShot(True)
    timer.timeout.connect(worker.release.set)
    timer.start(20)
    try:
        _pump(qapp, lambda: bool(callbacks))
        assert worker.wait(0)
        assert callbacks == [qapp.thread()]
        qapp.processEvents()
        assert len(callbacks) == 1
    finally:
        worker.release.set()
        worker.wait()
        owner.deleteLater()


def test_slow_folder_check_runs_off_gui_and_can_be_canceled(window, qapp, tmp_path, monkeypatch):
    root = str(tmp_path)
    release, entered = threading.Event(), threading.Event()
    original = scan_worker.os.path.isdir
    threads = []

    def checking(path):
        if path == root:
            threads.append(QThread.currentThread())
            entered.set()
            release.wait(5)
        return original(path)

    monkeypatch.setattr(scan_worker.os.path, "isdir", checking)
    try:
        window.start_scan(root)
        _pump(qapp, entered.is_set)
        assert threads[0] is not qapp.thread()
        QTimer.singleShot(20, release.set)
        window.stop_scan()
        _pump(qapp, lambda: window._worker is None)
        assert window.results.outcome is None
    finally:
        release.set()


def test_replacing_a_scan_retains_only_latest_request_without_gui_wait(window, qapp, tmp_path, monkeypatch):
    old, middle, newest = (tmp_path / name for name in ("old", "middle", "newest"))
    for folder in (old, middle, newest):
        folder.mkdir()
        (folder / "kept").write_bytes(b"kept")
    release, entered = threading.Event(), threading.Event()
    calls = []
    original = scan_worker.scan

    def scanning(path, **kwargs):
        calls.append(path)
        if path == str(old):
            entered.set()
            release.wait(5)
        return original(path, **kwargs)

    monkeypatch.setattr(scan_worker, "scan", scanning)
    try:
        window.start_scan(str(old))
        _pump(qapp, entered.is_set)
        old_worker = window._worker
        window.start_scan(str(middle))
        window.start_scan(str(newest))
        assert calls == [str(old)]
        assert old_worker._cancel.is_set()
        assert window._pending_scan is window._worker
        QTimer.singleShot(20, release.set)
        _pump(qapp, lambda: window.results.outcome is not None and window._worker is None)
        assert calls == [str(old), str(newest)]
        assert window.results.outcome.result.root.path == str(newest)
        assert all((folder / "kept").read_bytes() == b"kept" for folder in (old, middle, newest))
    finally:
        release.set()


def test_drive_discovery_and_retranslation_never_query_storage_on_gui(window, qapp, monkeypatch):
    page = window.welcome
    _pump(qapp, lambda: page._drive_worker is None)
    release, entered = threading.Event(), threading.Event()
    threads = []

    def discovery():
        threads.append(QThread.currentThread())
        entered.set()
        release.wait(5)
        return []

    monkeypatch.setattr(welcome, "drives", discovery)
    try:
        page.refresh_drives()
        _pump(qapp, entered.is_set)
        page.retranslate()
        window._update_actions()
        assert threads == [page._drive_worker]
        QTimer.singleShot(20, release.set)
        _pump(qapp, lambda: page._drive_worker is None)
        assert not page.drive_rows
    finally:
        release.set()
