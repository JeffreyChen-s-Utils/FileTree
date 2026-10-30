"""History save ownership, modal comparison, settings and canceled late replies."""

import threading

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog

from test_gui import _scanned, _wait, window as window  # noqa: PLC0414
from je_file_tree.core.history import ScanHistory
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.gui import history
from je_file_tree.gui.background_worker import ScheduledWorker
from je_file_tree.gui.history import HistoryDialog, HistorySettings, configured_history
from je_file_tree.gui.scan_worker import ScanWorker, wait_for


def test_full_scan_history_chart_and_modal_comparison_use_earlier_saved_tree(
        window, qapp, sample_tree, tmp_path, monkeypatch):
    _scanned(window, qapp, sample_tree)
    store = ScanHistory(tmp_path / "history")
    first = store.read(str(sample_tree)).entries[0]
    (sample_tree / "photos" / "more.jpg").write_bytes(b"j" * 300)
    _scanned(window, qapp, sample_tree)
    assert store.read(str(sample_tree)).count == 2
    assert window._actions["history"].isEnabled()

    def select_earlier(dialog):
        _wait(qapp, lambda: not dialog._running)
        assert dialog.model.rowCount() == 2
        assert dialog.chart.points[0].size == 1000 and dialog.chart.points[-1].size == 1300
        assert "1,000 B" in dialog.chart.accessibleDescription()
        assert dialog.trend_view.item(1, 1).text() == '1.3 KB'
        dialog.resize(870, 640)
        dialog.show()
        qapp.processEvents()
        assert not dialog.chart.grab().isNull()
        dialog.tabs.setCurrentWidget(dialog.view)
        dialog.view.setCurrentIndex(dialog.model.index(0, 0))
        assert dialog.compare_button.isEnabled()
        dialog.compare_selected()
        _wait(qapp, lambda: dialog._closed)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(HistoryDialog, "exec", select_earlier)
    window.show_history()
    _wait(qapp, lambda: window.results.changes.saved is not None)
    assert window.results.changes.saved.saved == first.saved
    assert window.results.changes_model.rows()[0].change == 300
    assert (sample_tree / "photos" / "more.jpg").read_bytes() == b"j" * 300


def test_trend_apply_before_header_read_restores_comparison_and_invalid_retry(
        window, qapp, sample_tree, tmp_path):
    store = ScanHistory(tmp_path / "history")
    store.save(scan(sample_tree).root, options=ScanOptions())
    (sample_tree / "photos" / "extra.jpg").write_bytes(b"x" * 17)
    store.save(scan(sample_tree).root, options=ScanOptions())
    dialog = HistoryDialog(store, str(sample_tree), "auto", window, folder="photos")
    try:
        assert dialog.folder_input.text() == "photos"
        dialog.apply_trend()
        _wait(qapp, lambda: not dialog._running)
        assert dialog.trend_view.rowCount() == 2
        assert dialog.model.rowCount() == 2
        assert dialog.chart.points[-1].change == 17
        assert dialog.tabs.count() == 3 and dialog.tabs.currentWidget() is dialog.trend_view
        dialog.tabs.setCurrentWidget(dialog.view)
        dialog.view.setCurrentIndex(dialog.model.index(0, 0))
        assert dialog.compare_button.isEnabled()
        dialog.start_input.setText("bad-date")
        dialog.apply_trend()
        qapp.processEvents()
        assert dialog.model.rowCount() == 0 and dialog.trend_view.rowCount() == 0
        assert not dialog.compare_button.isEnabled()
        dialog.start_input.clear()
        dialog.apply_trend()
        _wait(qapp, lambda: not dialog._running)
        assert dialog.model.rowCount() == 2 and dialog.trend_view.rowCount() == 2
    finally:
        dialog.reject()
        _wait(qapp, lambda: not dialog._finish_waiting)
        dialog.deleteLater()


def test_history_settings_accept_cancel_and_running_scan_capture(window, monkeypatch):
    captured = configured_history(window.settings)
    assert captured is not None and captured.max_bytes == 1024 ** 3
    worker = ScanWorker("owned-unstarted", ScanOptions(), history=captured)

    def disable(dialog):
        dialog.enabled.setChecked(False)
        dialog.limit.setValue(2)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(HistorySettings, "exec", disable)
    window.configure_history()
    assert configured_history(window.settings) is None
    assert worker._history is captured and captured.max_bytes == 1024 ** 3

    def decline(dialog):
        dialog.enabled.setChecked(True)
        dialog.limit.setValue(3)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(HistorySettings, "exec", decline)
    window.configure_history()
    assert configured_history(window.settings) is None and history.history_limit(window.settings) == 2
    worker.deleteLater()


def test_both_scan_producers_save_actual_measurement_options(window, qapp, tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "data").write_bytes(b"x")
    store = ScanHistory(tmp_path / "history")
    ordinary = ScanWorker(str(root), ScanOptions(include_hidden=False, exclude=("unused",)), history=store)
    outcomes = []
    ordinary.succeeded.connect(outcomes.append)
    ordinary.start()
    _wait(qapp, lambda: bool(outcomes))
    wait_for(ordinary)
    first = store.read(str(root)).entries[0]
    assert first.measurement is not None
    assert first.measurement.include_hidden is False and first.measurement.exclusions == ("unused",)
    scheduled = ScheduledWorker(str(root), ScanOptions(include_hidden=True), store, window)
    scheduled.start()
    _wait(qapp, lambda: scheduled.state == "complete")
    wait_for(scheduled)
    assert scheduled.entry is not None and scheduled.entry.measurement is not None
    assert scheduled.entry.measurement.include_hidden is True
    assert scheduled.entry.measurement.exclusions == ()
    ordinary.deleteLater()
    scheduled.deleteLater()


@pytest.mark.parametrize("value", [None, True, 1.5, "bad", 0, 16385])
def test_invalid_history_limit_keeps_default(window, value):
    window.settings.setValue("history_limit_mib", value)
    assert history.history_limit(window.settings) == 1024


def test_dialog_stop_close_join_and_late_reply_are_ignored(window, qapp, sample_tree, tmp_path, monkeypatch):
    store = ScanHistory(tmp_path / "history")
    entry = store.save(scan(sample_tree).root)
    original = store.read(str(sample_tree))
    started = threading.Event()

    def waiting(_store, _query, *, cancel):
        started.set()
        assert cancel.wait(10)
        return original

    monkeypatch.setattr(history, "query_trend", waiting)
    dialog = HistoryDialog(store, str(sample_tree), "auto", window)
    _wait(qapp, started.is_set)
    dialog.stop()
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    assert not dialog.worker.isRunning()
    dialog._show(original)
    assert dialog.model.rowCount() == 0 and not dialog.compare_button.isEnabled()
    assert entry.path.exists()
    dialog.deleteLater()


def test_history_ready_waits_asynchronously_for_join_before_enabling_comparison(window, qapp, tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    kept = source / "kept"
    kept.write_bytes(b"kept")
    store = ScanHistory(tmp_path / "history")
    entry = store.save(scan(source).root)
    release, entered = threading.Event(), threading.Event()
    original = history.HistoryWorker.run

    def held(worker):
        original(worker)
        entered.set()
        release.wait(5)

    monkeypatch.setattr(history.HistoryWorker, "run", held)
    dialog = HistoryDialog(store, str(source), "auto", window)
    compared = []
    dialog.compare_requested.connect(compared.append)
    try:
        _wait(qapp, entered.is_set)
        assert dialog.worker.isRunning() and dialog._running
        assert dialog.model.rowCount() == 0 and not dialog.compare_button.isEnabled()
        QTimer.singleShot(20, release.set)
        _wait(qapp, lambda: not dialog._running)
        assert release.is_set() and dialog.worker.wait(0) and dialog.model.rowCount() == 1
        dialog.tabs.setCurrentWidget(dialog.view)
        dialog.view.setCurrentIndex(dialog.model.index(0, 0))
        dialog.compare_selected()
        _wait(qapp, lambda: bool(compared))
        assert dialog.result() == QDialog.DialogCode.Accepted and dialog.worker.wait(0)
        assert compared[0].root == str(source)
        assert entry.path.exists() and kept.read_bytes() == b"kept"
    finally:
        release.set()
        dialog.reject()
        _wait(qapp, lambda: not dialog._finish_waiting)
        dialog.deleteLater()


def test_history_save_failure_preserves_completed_scan_and_disabled_history_saves_nothing(
        window, qapp, sample_tree, tmp_path, monkeypatch):
    store = ScanHistory(tmp_path / "history", max_bytes=10)
    worker = ScanWorker(str(sample_tree), ScanOptions(), history=store)
    outcomes, errors = [], []
    worker.succeeded.connect(outcomes.append)
    worker.history_failed.connect(errors.append)
    worker.start()
    _wait(qapp, lambda: bool(outcomes))
    wait_for(worker)
    assert errors and outcomes[0].result.root.size == 1000
    assert store.read(str(sample_tree)).count == 0
    worker.deleteLater()
    window.settings.setValue("history_enabled", False)
    _scanned(window, qapp, sample_tree)
    assert store.read(str(sample_tree)).count == 0


def test_branch_rescan_does_not_create_a_mixed_time_history_snapshot(window, qapp, sample_tree, tmp_path):
    _scanned(window, qapp, sample_tree)
    store = ScanHistory(tmp_path / "history")
    before = store.read(str(sample_tree)).count
    branch = next(child for child in window.results.outcome.result.root.children if child.name == "photos")
    (sample_tree / "photos" / "more.jpg").write_bytes(b"j" * 300)
    window.rescan_folder(branch)
    _wait(qapp, lambda: window._worker is None)
    assert store.read(str(sample_tree)).count == before
    assert window.results.outcome.result.root.size == 1300


def test_stop_during_history_serialization_does_not_publish_a_snapshot(qapp, sample_tree, tmp_path, monkeypatch):
    from je_file_tree.core import history as history_core

    store = ScanHistory(tmp_path / "history")
    entered, released = threading.Event(), threading.Event()
    original = history_core._folder_json

    def waiting(root, depth):
        entered.set()
        assert released.wait(10)
        yield from original(root, depth)

    monkeypatch.setattr(history_core, "_folder_json", waiting)
    worker = ScanWorker(str(sample_tree), ScanOptions(), history=store)
    canceled, succeeded = [], []
    worker.cancelled.connect(canceled.append)
    worker.succeeded.connect(succeeded.append)
    worker.start()
    try:
        _wait(qapp, entered.is_set)
        worker.cancel()
    finally:
        released.set()
        wait_for(worker)
    qapp.processEvents()
    assert not succeeded and canceled[0].partial
    assert store.read(str(sample_tree)).count == 0
    assert not list(store.directory.rglob(".file-tree-*"))
    worker.deleteLater()


def test_mount_change_never_publishes_history_or_a_successful_outcome(qapp, sample_tree, tmp_path, monkeypatch):
    from je_file_tree.core import scanner
    from je_file_tree.gui.i18n import tr

    store = ScanHistory(tmp_path / "history")
    surveys = iter([frozenset(), frozenset({str(sample_tree / "photos")})])
    monkeypatch.setattr(scanner, "mount_points", lambda: next(surveys))
    worker = ScanWorker(str(sample_tree), ScanOptions(), history=store)
    succeeded, failed = [], []
    worker.succeeded.connect(succeeded.append)
    worker.failed.connect(failed.append)
    worker.start()
    wait_for(worker)
    qapp.processEvents()
    assert not succeeded and failed == [tr("scan_mount_changed")]
    assert store.read(str(sample_tree)).count == 0
    worker.deleteLater()
