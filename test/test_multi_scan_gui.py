"""Combined result lifetimes preserve physical sources and never dispatch the virtual label as a path."""

import json

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox
import pytest

from test_gui import _wait, window as window  # noqa: PLC0414 - shared pytest fixture
from test_multi_scan import sources as sources  # noqa: PLC0414 - shared pytest fixture
from je_file_tree import cli
from je_file_tree.core.history import ScanHistory
from je_file_tree.core.scanner import ScanOptions
from je_file_tree.gui import file_actions
from je_file_tree.gui.welcome import DriveSnapshot
from je_file_tree.gui.charts import MODES
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.multi_scan import MultiScanDialog
from je_file_tree.gui.scan_worker import ScanWorker


def test_accepted_folder_list_is_bounded_literal_and_frozen(qapp, sources):
    dialog = MultiScanDialog()
    try:
        assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        for path in [sources[0], sources[0], sources[1]]:
            dialog.add_root(str(path))
        _wait(qapp, lambda: not dialog._pending)
        assert dialog.list.count() == 2
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted and dialog.roots == tuple(map(str, sources))
        dialog.list.clear()
        assert dialog.roots == tuple(map(str, sources))
    finally:
        dialog.deleteLater()
        qapp.processEvents()


def test_owned_folder_review_releases_guard_before_dispatching_combined_scan(window, qapp, sources, monkeypatch):
    paths = tuple(map(str, sources))

    def approve(dialog):
        assert window.operation_busy
        for path in paths:
            dialog.add_root(path)
        _wait(qapp, lambda: not dialog._pending)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(MultiScanDialog, "exec", approve)
    window.choose_roots()
    _wait(qapp, lambda: window._worker is None)
    assert not window.operation_busy and not window._path_dialogs
    assert window._last_roots == paths and window.results.outcome.result.root.size == 3


def test_combined_window_renders_all_charts_and_rescans_captured_roots(window, qapp, sources, monkeypatch):
    paths = tuple(map(str, sources))
    window.start_scan_roots(paths)
    _wait(qapp, lambda: window._worker is None)
    outcome = window.results.outcome
    assert outcome is not None and outcome.result.root.path is None and outcome.result.root.size == 3
    root = outcome.result.root
    assert tr("multi_roots") in window.results.summary.toolTip()
    index = window.results.tree_model.index(0, 0)
    assert index.data(Qt.ItemDataRole.DisplayRole) == tr("multi_roots")
    assert index.data(Qt.ItemDataRole.ToolTipRole) == tr("multi_roots")
    for mode in MODES:
        window.results.charts.set_mode(mode)
        assert not window.results.charts._charts[mode].grab().isNull()
    assert not window._actions["trash"].isEnabled() and not window._actions["history"].isEnabled()
    monkeypatch.setattr(file_actions, "trash_receipt", lambda _path: pytest.fail("Combined source mutated"))
    window.move_to_trash(list(root.iter_files()))
    window.show_menu_for(root, [root], QPoint())
    (sources[0] / "new.bin").write_bytes(b"new")
    window.rescan()
    _wait(qapp, lambda: window._worker is None)
    assert window.results.outcome.result.root.size == 6 and window._last_roots == paths


def test_scan_all_drives_captures_cached_roots_and_normal_scan_restores_source_scope(
        window, qapp, sources, monkeypatch):
    window.welcome.drive_rows = tuple(DriveSnapshot(str(path), "", 1000, 500) for path in sources)
    window.welcome.drives_changed.emit()
    window.welcome.scan_all.click()
    _wait(qapp, lambda: window._worker is None)
    assert window.results.outcome.result.root.path is None
    window.start_scan(str(sources[0]))
    _wait(qapp, lambda: window._worker is None)
    assert window.results.outcome.result.root.path == str(sources[0]) and not window._last_roots
    assert window._actions["trash"].isEnabled()


def test_multi_worker_saves_only_actual_source_history(qapp, sources, tmp_path):
    store = ScanHistory(tmp_path / "owned-history")
    worker = ScanWorker(tuple(map(str, sources)), ScanOptions(workers=1), history=store)
    outcomes, failures = [], []
    worker.succeeded.connect(outcomes.append)
    worker.failed.connect(failures.append)
    worker.history_failed.connect(failures.append)
    worker.run()
    assert not failures and outcomes[0].result.root.path is None
    assert {entry.root for path in sources for entry in store.read(str(path)).entries} == set(map(str, sources))


def test_closing_combined_scan_joins_current_worker_and_ignores_late_results(window, sources, qapp):
    window.start_scan_roots(tuple(map(str, sources)))
    cancelled = window._worker._cancel
    window.close()
    _wait(qapp, lambda: window._close_ready)
    assert cancelled.is_set()
    assert window._worker is None
    qapp.processEvents()
    assert window._closing


def test_cli_also_preserves_null_virtual_path_explicit_sources_and_partial_exit(sources, tmp_path, capsys):
    missing = tmp_path / "unavailable"
    assert cli.main(["scan", str(sources[0]), "--also", str(sources[1]), "--also", str(missing)]) == cli.INCOMPLETE
    report = json.loads(capsys.readouterr().out)
    assert report["root"] is None and set(report["roots"]) == {*map(str, sources), str(missing)}
    assert report["partial"] and report["files"] == 2 and report["capacity"]["status"] == "multiple_roots"
    assert report["capacity"]["total"] is report["capacity"]["free"] is None
