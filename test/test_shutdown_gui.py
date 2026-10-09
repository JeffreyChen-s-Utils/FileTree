"""Closing retains native readers and writers while ordinary Qt timers continue running."""

import threading

from PySide6.QtCore import QTimer
from test_gui import _wait, window as window  # noqa: PLC0414 - shared fixture
from test_workspace_gui import workspace as workspace  # noqa: PLC0414 - shared fixture

from je_file_tree.gui import scan_worker, welcome
from je_file_tree.gui.background_worker import CapacityWorker
from je_file_tree.gui.scan_worker import ExportWorker


def test_single_window_close_waits_for_native_discovery_without_blocking(window, qapp, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def held_drives():
        entered.set()
        assert release.wait(5), "closing prevented the GUI timer from releasing native discovery"
        return []

    monkeypatch.setattr(welcome, "drives", held_drives)
    window.show()
    _wait(qapp, entered.is_set)
    try:
        window.close()
        window.close()  # repeat requests must neither destroy ownership nor initiate another join
        assert not window._close_ready and window.isVisible() and not release.is_set()
        assert "Closing FileTree" in window.statusBar().currentMessage()
        QTimer.singleShot(30, release.set)
        _wait(qapp, lambda: window._close_ready)
        assert release.is_set() and not window.isVisible()
    finally:
        release.set()
        _wait(qapp, lambda: window._close_ready)


def test_quit_retains_native_capacity_and_finishes_the_owned_export(workspace, qapp, tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    exported = threading.Event()
    target = tmp_path / "owned-report.txt"

    def held_capacity(_worker):
        entered.set()
        assert release.wait(5), "capacity shutdown blocked its GUI release timer"

    def write():
        assert release.wait(5), "export shutdown blocked its GUI release timer"
        target.write_text("complete owned report", encoding="utf-8")
        exported.set()
        return 1

    monkeypatch.setattr(CapacityWorker, "run", held_capacity)
    capacity = CapacityWorker(workspace.background)
    workspace.background.capacity = capacity
    writer = ExportWorker(write, workspace.current)
    workspace.current._exports.add(writer)
    capacity.start()
    writer.start()
    _wait(qapp, entered.is_set)
    try:
        workspace.quit_application()
        assert capacity.cancel.is_set() and not workspace._close_ready
        assert not exported.is_set() and not release.is_set()
        QTimer.singleShot(30, release.set)
        _wait(qapp, lambda: workspace._close_ready)
        assert exported.is_set() and target.read_text(encoding="utf-8") == "complete owned report"
    finally:
        release.set()
        _wait(qapp, lambda: workspace._close_ready)


def test_retiring_one_scan_tab_keeps_the_other_scan_running(workspace, qapp, tmp_path, monkeypatch):
    roots = [tmp_path / name for name in ("first", "second")]
    for root in roots:
        root.mkdir()
        (root / "kept").write_bytes(b"source")
    entered = [threading.Event(), threading.Event()]
    release = [threading.Event(), threading.Event()]
    original = scan_worker.scan

    def held(path, **kwargs):
        index = list(map(str, roots)).index(path)
        entered[index].set()
        assert release[index].wait(5), "tab shutdown blocked its release timer"
        return original(path, **kwargs)

    monkeypatch.setattr(scan_worker, "scan", held)
    first, second = workspace.current, workspace.add_tab()
    first.start_scan(str(roots[0]))
    second.start_scan(str(roots[1]))
    _wait(qapp, lambda: all(event.is_set() for event in entered))
    second_cancel = second._worker._cancel
    try:
        workspace.close_tab(workspace.tabs.indexOf(first))
        assert workspace.tabs.count() == 2 and not first._close_ready
        QTimer.singleShot(30, release[0].set)
        _wait(qapp, lambda: workspace.tabs.count() == 1)
        assert workspace.current is second and second._worker.isRunning()
        assert not second_cancel.is_set() and not release[1].is_set()
        assert all((root / "kept").read_bytes() == b"source" for root in roots)
    finally:
        for event in release:
            event.set()
        workspace.quit_application()
        _wait(qapp, lambda: workspace._close_ready)
