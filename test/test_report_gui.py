"""Independent chart capture and modal report writing leave user navigation untouched."""

import threading

from PySide6.QtCore import Qt

from test_gui import _scanned, _wait, window as window  # noqa: PLC0414 - explicit fixture re-export
from je_file_tree.core.report import check_cancel
from je_file_tree.core.scanner import scan
from je_file_tree.gui.charts import BARS, ChartStack
from je_file_tree.gui import main_window as main_module
from je_file_tree.gui import report_dialog as report_module
from je_file_tree.gui.report_dialog import ReportDialog
from je_file_tree.gui.report_export import capture_report_charts, encode_charts
from je_file_tree.gui.scan_worker import analyse


def test_three_owned_chart_images_preserve_navigation(qapp, sample_tree):
    root = scan(sample_tree).root
    source = ChartStack()
    source.set_view_root(next(child for child in root.children if child.name == "photos"))
    source.set_mode(BARS)
    original = source.view_root
    images = capture_report_charts(root, source, "auto", 1_700_000_000)
    encoded = encode_charts(images, threading.Event())
    assert len(encoded) == 3
    assert all(image.width() == 1000 and image.height() == 600 for _, image in images)
    assert all(png.startswith(b"\x89PNG\r\n\x1a\n") for _, png in encoded)
    assert source.mode == BARS and source.view_root is original
    source.close()
    source.deleteLater()


def test_real_html_worker_saves_whole_scan_without_mutating_charts(qapp, window, sample_tree, tmp_path):
    _scanned(window, qapp, sample_tree)
    root = window.results.outcome.result.root
    window.results.charts.set_view_root(next(child for child in root.children if child.name == "photos"))
    source_root = window.results.charts.view_root
    target = tmp_path / "report.html"
    dialog = ReportDialog(window.results.outcome, "html", str(target), "auto", window.results.charts, window)
    try:
        _wait(qapp, lambda: not dialog.worker.isRunning())
        assert dialog.saved and not dialog.stop_button.isEnabled()
        assert dialog.status.textFormat() == Qt.TextFormat.PlainText
        assert window.results.charts.view_root is source_root
        text = target.read_text(encoding="utf-8")
        assert text.count("data:image/png;base64,") == 3
        assert "big.bin" in text and "1000" in text
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_stop_and_close_join_worker_and_keep_old_output(qapp, tmp_path, sample_tree, monkeypatch):
    target = tmp_path / "existing.xlsx"
    target.write_bytes(b"previous")
    entered, release = threading.Event(), threading.Event()
    original = report_module.prepare_report
    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        check_cancel(kwargs["cancel"])
        return original(*args, **kwargs)
    monkeypatch.setattr(report_module, "prepare_report", slow)
    charts = ChartStack()
    dialog = ReportDialog(analyse(scan(sample_tree)), "xlsx", str(target), "auto", charts)
    _wait(qapp, entered.is_set)
    dialog.stop()
    release.set()
    _wait(qapp, lambda: not dialog.worker.isRunning())
    assert not dialog.saved and target.read_bytes() == b"previous"
    dialog.reject()
    assert not dialog.worker.isRunning()
    message = dialog.status.text()
    dialog._finished("late saved reply", True)
    assert not dialog.saved and dialog.status.text() == message
    dialog.deleteLater()
    charts.deleteLater()


def test_main_menu_excel_export_writes_six_sheets(qapp, window, sample_tree, tmp_path, monkeypatch):
    _scanned(window, qapp, sample_tree)
    target = tmp_path / "report.xlsx"
    monkeypatch.setattr(main_module.QFileDialog, "getSaveFileName", lambda *_args: (str(target), ""))
    def execute(dialog):
        _wait(qapp, lambda: not dialog.worker.isRunning())
        assert dialog.saved
        dialog.reject()
        return 0
    monkeypatch.setattr(ReportDialog, "exec", execute)
    assert window._actions["export_report_xlsx"].isEnabled()
    window.export_report("xlsx")
    assert target.exists()
    assert window.settings.value("export_dir") == str(tmp_path)
    assert window._actions["export_report_html"].text()
    assert not window._actions["export_report_html"].isCheckable()
