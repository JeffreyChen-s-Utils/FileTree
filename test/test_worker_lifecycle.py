"""GUI timers must keep running while slow owned workers are being canceled or replaced."""

from __future__ import annotations

import threading
import time

import pytest
from PySide6.QtCore import QObject, QThread, QTimer
from PySide6.QtWidgets import QMessageBox
from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export

from je_file_tree.core.operation_journal import OperationJournal
from je_file_tree.core.pacing import WINDOW
from je_file_tree.core.operations import MoveReceipt
from je_file_tree.core.scanner import scan
from je_file_tree.gui import change_watch, file_actions, folder_validation, scan_worker, welcome
from je_file_tree.gui.multi_scan import MultiScanDialog
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


def test_nonblocking_thread_fence_preserves_the_gui_pacing_gate(qapp):
    owner = QObject()
    worker = HeldWorker(owner)
    callbacks = []
    worker.start()
    WINDOW.close()
    try:
        after_threads((worker,), lambda: callbacks.append(WINDOW.is_open), owner)
        assert not WINDOW.is_open, "a zero-time join must not release the GUI's worker-priority gate"
        QTimer.singleShot(20, worker.release.set)
        _pump(qapp, lambda: bool(callbacks))
        assert worker.release.is_set() and callbacks == [False]
        after_threads((), lambda: callbacks.append(WINDOW.is_open), owner)
        assert callbacks == [False, False]
    finally:
        worker.release.set()
        worker.wait()
        WINDOW.open()
        owner.deleteLater()


def _held_folder(path, monkeypatch):
    release, entered = threading.Event(), threading.Event()
    original = folder_validation.os.path.isdir
    threads = []

    def checking(candidate):
        if candidate == str(path):
            threads.append(QThread.currentThread())
            entered.set()
            release.wait(5)
        return original(candidate)

    monkeypatch.setattr(folder_validation.os.path, "isdir", checking)
    return release, entered, threads


def test_slow_drop_is_replaced_without_gui_queries_or_stale_scan(window, qapp, tmp_path, monkeypatch):
    folders = tuple(tmp_path / name for name in ("old", "middle", "latest"))
    for folder in folders:
        folder.mkdir()
        (folder / "kept").write_bytes(b"kept")
    release, entered, threads = _held_folder(folders[0], monkeypatch)
    scans = []
    monkeypatch.setattr(window, "start_scan", scans.append)
    try:
        window._folder_drops.request((str(folders[0]),))
        _pump(qapp, entered.is_set)
        assert threads[0] is not qapp.thread()
        window._folder_drops.request((str(folders[1]),))
        window._folder_drops.request((str(folders[2]),))
        assert not scans
        QTimer.singleShot(20, release.set)
        _pump(qapp, lambda: bool(scans))
        assert release.is_set() and scans == [str(folders[2])]
        assert all((folder / "kept").read_bytes() == b"kept" for folder in folders)
    finally:
        release.set()


def test_new_scan_invalidates_slow_drop_without_waiting(window, qapp, tmp_path, monkeypatch):
    old, latest = tmp_path / "old", tmp_path / "latest"
    for folder in (old, latest):
        folder.mkdir()
    (old / "kept").write_bytes(b"kept")
    release, entered, _ = _held_folder(old, monkeypatch)
    try:
        window._folder_drops.request((str(old),))
        _pump(qapp, entered.is_set)
        window.start_scan(str(latest))
        assert window._folder_drops.current is None
        QTimer.singleShot(20, release.set)
        _pump(qapp, lambda: window._worker is None and not window._folder_drops.workers)
        assert release.is_set() and window.results.outcome.result.root.path == str(latest)
        assert (old / "kept").read_bytes() == b"kept"
    finally:
        release.set()


def test_multifolder_cancel_keeps_gui_live_until_native_validation_joins(window, qapp, tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    kept = source / "kept"
    kept.write_bytes(b"kept")
    release, entered, threads = _held_folder(source, monkeypatch)
    dialog = MultiScanDialog(window)
    try:
        dialog.add_root(str(source))
        dialog.add_root(str(source))
        _pump(qapp, entered.is_set)
        assert threads[0] is not qapp.thread() and len(dialog._pending) == 1
        assert dialog.list.count() == 0
        dialog.reject()
        assert dialog._finish_waiting
        QTimer.singleShot(20, release.set)
        _pump(qapp, lambda: not dialog._finish_waiting)
        assert release.is_set() and dialog.roots == () and dialog.list.count() == 0
        assert kept.read_bytes() == b"kept"
    finally:
        release.set()
        dialog.reject()
        _pump(qapp, lambda: not dialog._finish_waiting)
        dialog.deleteLater()


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


def _held_follow(window, qapp, monkeypatch):
    release, entered = threading.Event(), threading.Event()

    def watch(_root, _changed, cancel, *, ready):
        ready("directory_changes")
        entered.set()
        cancel.wait(5)
        release.wait(5)

    monkeypatch.setattr(change_watch, "watch", watch)
    monkeypatch.setattr(change_watch, "supported", lambda: True)
    window._actions["follow_changes"].setChecked(True)
    _pump(qapp, entered.is_set)
    return release, window._follow.worker


def test_follow_reconfiguration_queues_only_latest_reader_without_gui_wait(window, qapp, tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    kept = source / "kept"
    kept.write_bytes(b"kept")
    window.results.show_outcome(scan_worker.analyse(scan(source)))
    release = threading.Event()
    calls = []

    def watch(_root, _changed, cancel, *, ready):
        calls.append(QThread.currentThread())
        ready("directory_changes")
        cancel.wait(5)
        release.wait(5)

    monkeypatch.setattr(change_watch, "watch", watch)
    monkeypatch.setattr(change_watch, "supported", lambda: True)
    action = window._actions["follow_changes"]
    try:
        action.setChecked(True)
        _pump(qapp, lambda: len(calls) == 1)
        old = window._follow.worker
        for enabled in (False, True, False, True):
            action.setChecked(enabled)
        newest = window._follow.worker
        assert old.cancel.is_set() and old.isRunning()
        assert newest is not old and calls == [old]
        QTimer.singleShot(20, release.set)
        _pump(qapp, lambda: len(calls) == 2 and bool(newest.backend))
        assert release.is_set() and calls == [old, newest]
        assert kept.read_bytes() == b"kept"
    finally:
        release.set()


@pytest.mark.parametrize("cancel", [False, True])
def test_trash_queues_behind_native_reader_without_gui_wait(window, qapp, tmp_path, monkeypatch, cancel):
    source = tmp_path / "source"
    source.mkdir()
    kept = source / "kept"
    kept.write_bytes(b"kept")
    window.results.show_outcome(scan_worker.analyse(scan(source)))
    window._journal = OperationJournal(tmp_path / "journal")
    root = window.results.tree_model.root
    calls = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: calls.append(path) or MoveReceipt(False))
    release, reader = _held_follow(window, qapp, monkeypatch)
    try:
        window.move_to_trash(root.children)
        assert reader.cancel.is_set() and reader.isRunning()
        assert window.operation_busy and not calls
        assert window._follow._pending.full
        if cancel:
            window.stop_scan()
        QTimer.singleShot(20, release.set)
        _pump(qapp, lambda: window._trash_worker is None)
        assert release.is_set() and not window.operation_busy
        assert calls == ([] if cancel else [str(kept)])
        assert kept.read_bytes() == b"kept"
        if cancel:
            assert not window._journal.recent().records
    finally:
        release.set()


def test_cancel_queued_branch_keeps_previous_result_and_clears_busy_state(window, qapp, tmp_path, monkeypatch):
    branch = tmp_path / "source" / "branch"
    branch.mkdir(parents=True)
    kept = branch / "kept"
    kept.write_bytes(b"kept")
    window.results.show_outcome(scan_worker.analyse(scan(branch.parent)))
    previous = window.results.outcome
    release, reader = _held_follow(window, qapp, monkeypatch)
    calls = []
    scanning = scan_worker.scan
    monkeypatch.setattr(scan_worker, "scan", lambda *args, **kwargs: calls.append(args) or scanning(*args, **kwargs))
    try:
        window.rescan_folder(previous.result.root.children[0])
        assert reader.cancel.is_set() and reader.isRunning()
        assert window._worker is not None and not calls
        window.stop_scan()
        QTimer.singleShot(20, release.set)
        _pump(qapp, lambda: window._worker is None)
        assert release.is_set() and not calls
        assert window.results.outcome is previous and kept.read_bytes() == b"kept"
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
