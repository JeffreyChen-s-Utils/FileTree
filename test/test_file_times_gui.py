"""Recorded-time controls keep worker ownership, capture settings and exact-node read-only routing."""

import threading

from PySide6.QtCore import Qt

from test_gui import _wait, window as window  # noqa: PLC0414
from je_file_tree.core.file_times import AccessPolicy, TimeInventory
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.gui import file_times as gui
from je_file_tree.gui.file_times import FileTimesDialog
from je_file_tree.gui.scan_worker import ScanWorker
from je_file_tree.gui.tree_model import ACCESSED, CREATED


def test_capture_option_is_off_until_enabled_and_running_scan_keeps_original_options(window):
    assert not window._scan_options().file_times
    original = window._scan_options()
    worker = ScanWorker("owned-unstarted", original, window)
    window._worker = worker
    try:
        window._actions["capture_file_times"].trigger()
        assert window._scan_options().file_times
        assert worker._options is original and not worker._options.file_times
        assert str(window.settings.value("capture_file_times")).lower() == "true"
    finally:
        window._worker = None
        worker.deleteLater()
    assert window.results.tree.isColumnHidden(ACCESSED) and window.results.tree.isColumnHidden(CREATED)


def test_time_table_controls_replace_workers_ignore_old_replies_and_select_exact_node(
        window, qapp, sample_tree, monkeypatch):
    root = scan(sample_tree, options=ScanOptions(file_times=True)).root
    node = next(root.iter_files())
    calls = []

    def query(_root, days, *, clock, **_kwargs):
        calls.append((clock, days))
        return TimeInventory([node], 1, node.size, 0, 1, AccessPolicy("platform"))

    monkeypatch.setattr(gui, "files_older_than", query)
    dialog = FileTimesDialog(root, "auto", parent=window)
    _wait(qapp, lambda: dialog.model.rowCount() == 1)
    original = dialog.worker
    assert not dialog.model.flags(dialog.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    dialog.mode.setCurrentIndex(1)
    dialog.days.setValue(30)
    _wait(qapp, lambda: dialog.model.rowCount() == 1)
    dialog._show(original, TimeInventory([], 0, 0, 0, 0, AccessPolicy("platform")))
    assert dialog.model.rowCount() == 1 and calls[-1] == ("created", 30)
    selected = []
    dialog.selected.connect(selected.append)
    dialog._select(dialog.proxy.index(0, 0))
    assert selected == [node] and not dialog.worker.isRunning()
    dialog.deleteLater()


def test_stop_close_joins_time_query_and_ignores_late_inventory(window, qapp, sample_tree, monkeypatch):
    entered = threading.Event()

    def waiting(_root, _days, *, cancel, **_kwargs):
        entered.set()
        assert cancel.wait(10)
        return TimeInventory([], 0, 0, 0, 0, AccessPolicy("platform"))

    monkeypatch.setattr(gui, "files_older_than", waiting)
    dialog = FileTimesDialog(scan(sample_tree).root, "auto", parent=window)
    _wait(qapp, entered.is_set)
    worker = dialog.worker
    dialog.stop()
    dialog.reject()
    dialog._show(worker, TimeInventory([dialog.root], 1, 0, 0, 1, AccessPolicy("disabled")))
    assert not worker.isRunning() and dialog.model.rowCount() == 0
    dialog.deleteLater()
