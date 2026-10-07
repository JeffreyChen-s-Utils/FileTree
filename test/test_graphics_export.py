"""Owned captures export atomically; SVG retains shapes/text instead of a chart bitmap."""

import threading
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import QSaveFile
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog

from test_gui import _wait
from je_file_tree.core.node import Node
from je_file_tree.gui.app import create_window
from je_file_tree.gui.charts import ChartStack
from je_file_tree.gui.graphics_export import capture_svg, save_graphic
from je_file_tree.gui.i18n import current_language, set_language
from je_file_tree.gui.qt_translation import apply_qt_translation
from je_file_tree.gui.scan_worker import ExportWorker, wait_for


def _charts(mode):
    chart = ChartStack()
    chart.resize(640, 480)
    root = Node("root", True, size=15, children=[])
    for name, size in (("large.txt", 10), ("small.txt", 5)):
        root.children.append(Node(name, False, size=size, parent=root))
    chart.set_view_root(root)
    chart.set_mode(mode)
    return chart


@pytest.mark.parametrize("mode", ["bars", "sunburst"])
def test_svg_contains_chart_shapes_and_text_without_a_full_bitmap(qapp, tmp_path, mode) -> None:
    chart = _charts(mode)
    data = capture_svg(chart)
    document = ET.fromstring(data)  # noqa: S314 - trusted bytes from our own Qt SVG generator
    assert document.tag.endswith("svg") and b"large.txt" in data
    assert b"<image" not in data and (b"<path" in data or b"<rect" in data)
    target = tmp_path / "chart.svg"
    save_graphic(str(target), data)
    assert target.read_bytes() == data
    chart.deleteLater()


def test_png_keeps_owned_pixels_after_view_changes_and_writes_on_worker(qapp, tmp_path) -> None:
    chart = _charts("treemap")
    owned = chart.currentWidget().grab().toImage()
    chart.set_view_root(None)
    target = tmp_path / "chart.png"
    threads, results = [], []

    def write():
        threads.append(threading.get_ident())
        return save_graphic(str(target), owned)

    worker = ExportWorker(write)
    worker.done.connect(results.append)
    worker.start()
    _wait(qapp, lambda: bool(results))
    wait_for(worker)
    assert threads == [threads[0]] and threads[0] != threading.get_ident()
    exported = QImage(str(target))
    assert exported.size() == owned.size() and exported == owned.convertToFormat(exported.format())
    worker.deleteLater()
    chart.deleteLater()


def test_atomic_image_write_failure_preserves_an_existing_report(qapp, tmp_path, monkeypatch) -> None:
    target = tmp_path / "chart.svg"
    target.write_bytes(b"previous complete report")
    monkeypatch.setattr(QSaveFile, "write", lambda self, data: len(data) - 1)
    with pytest.raises(OSError):
        save_graphic(str(target), b"new report")
    assert target.read_bytes() == b"previous complete report"


def test_only_supported_modes_offer_vector_export(qapp) -> None:
    chart = _charts("treemap")
    with pytest.raises(ValueError):
        capture_svg(chart)
    chart.deleteLater()


def test_window_chart_menu_actions_track_current_mode_and_cancel_creates_no_worker(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtCore import QSettings  # noqa: PLC0415 - fixture-local settings
    from je_file_tree.core.scanner import scan  # noqa: PLC0415
    from je_file_tree.gui.scan_worker import analyse  # noqa: PLC0415

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    previous = current_language()
    window = create_window(settings)
    try:
        window.results.show_outcome(analyse(scan(tmp_path)))
        window._update_actions()
        assert window._actions["export_chart_png"].isEnabled()
        assert not window._actions["export_chart_svg"].isEnabled()
        window.results.charts.set_mode("sunburst")
        assert window._actions["export_chart_svg"].isEnabled()
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))
        window.export_chart("svg")
        assert not window._exports
    finally:
        window.close()
        window.deleteLater()
        set_language(previous)
        apply_qt_translation(previous)
