"""Fresh comparisons, explicit hash selection, CSV and dialog lifetime under Qt."""

import csv
import time

from PySide6.QtCore import Qt

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.live_compare import FolderComparison
from je_file_tree.gui import live_compare
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.live_compare import LiveCompareDialog


def _wait(app, ready):
    deadline = time.monotonic() + 15
    while not ready():
        assert time.monotonic() < deadline
        app.processEvents()
        time.sleep(.005)
    app.processEvents()


def _folders(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for folder in (left, right):
        (folder / "same.txt").write_bytes(b"same")
        (folder / "other.txt").write_bytes(b"other")
    return str(left), str(right)


def test_requested_pairs_only_and_csv_export(qapp, tmp_path, monkeypatch):
    dialog = LiveCompareDialog(_folders(tmp_path), "auto")
    try:
        _wait(qapp, lambda: not dialog.worker.isRunning())
        assert dialog.model.rowCount() == 2
        assert all(row.state != "identical" for row in dialog.model.rows())
        selected = dialog.proxy.index(0, 0).data()
        dialog.view.selectRow(0)
        dialog.hash_selected()
        _wait(qapp, lambda: not dialog.worker.isRunning())
        states = {row.relative: row.state for row in dialog.model.rows()}
        assert states[selected] == "identical"
        assert next(state for path, state in states.items() if path != selected) != "identical"
        target = tmp_path / "comparison.csv"
        monkeypatch.setattr(live_compare.QFileDialog, "getSaveFileName", lambda *_args: (str(target), ""))
        dialog.export_rows()
        _wait(qapp, lambda: not dialog._exports)
        with target.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        assert len(rows) == 3 and str(target) in dialog.status.text()
    finally:
        dialog.reject()
        assert not dialog.worker.isRunning()
        dialog.deleteLater()


def test_stop_and_close_reject_late_replies(qapp, tmp_path):
    dialog = LiveCompareDialog(_folders(tmp_path), "auto")
    dialog.stop()
    _wait(qapp, lambda: not dialog.worker.isRunning())
    assert dialog.model.rowCount() == 0
    assert dialog.status.text() == tr("scan_cancelled")
    dialog.reject()
    dialog._show(FolderComparison([], 123, True))
    assert dialog._count == 0 and dialog._closed
    dialog.deleteLater()


def test_choose_comparison_canceled_at_either_folder_starts_no_scan(window, monkeypatch):
    choices, calls = iter(("", "left", "")), []
    def choose(*_args):
        calls.append(True)
        return next(choices)
    monkeypatch.setattr(live_compare.QFileDialog, "getExistingDirectory", choose)
    assert window._actions["live_compare"].isEnabled()
    window.compare_live_folders()
    assert len(calls) == 1 and window._worker is None
    window.compare_live_folders()
    assert len(calls) == 3 and window._worker is None


def test_comparison_table_is_read_only_and_has_two_metadata_sides(qapp, tmp_path):
    dialog = LiveCompareDialog(_folders(tmp_path), "auto")
    try:
        _wait(qapp, lambda: not dialog.worker.isRunning())
        assert dialog.model.columnCount() == 6
        assert not dialog.model.flags(dialog.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
        assert "Equal size/time" in dialog.hint.text()
        assert "10,000" in dialog.status.text()
    finally:
        dialog.reject()
        dialog.deleteLater()
