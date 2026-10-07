"""The window and its models, on Qt's offscreen platform."""

from __future__ import annotations

import functools
import json
import math
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import (
    QAbstractEventDispatcher,
    QEventLoop,
    QItemSelectionModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QSettings,
    Qt,
    QThread,
    QTimer,
    QUrl,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMenu, QMessageBox, QSizePolicy

from conftest import make_tree
from test_cleanup import age_tree
from je_file_tree.core.analysis import CATEGORIES
from je_file_tree.core.formatting import format_size
from je_file_tree.core import pacing
from je_file_tree.core.node import Node
from je_file_tree.core.protected import PROGRAMS, Protection
from je_file_tree.core import scanner
from je_file_tree.core.scanner import ScanCancelledError, ScanOptions, scan
from je_file_tree.gui import file_actions, i18n, scan_worker
from je_file_tree.gui import main_window as main_window_module
from je_file_tree.gui.app import create_window
from je_file_tree.gui.elided_label import ElidedLabel
from je_file_tree.gui.help_dialog import HelpDialog
from je_file_tree.gui.main_window import RESULTS_PAGE, WELCOME_PAGE, MainWindow, _dropped_folder
from je_file_tree.gui.qt_translation import apply_qt_translation
from je_file_tree.gui.results_view import (
    CHANGES_TAB,
    CHART_TAB,
    CLEANUP_TAB,
    LARGEST_TAB,
    SEARCH_TAB,
    _selected_in,
)
from je_file_tree.gui.scan_worker import analyse, pace_workers, wait_for
from je_file_tree.gui.tables import SORT_ROLE, FileTypesModel, LargestFilesModel
from je_file_tree.gui.tree_model import ALLOCATED, NAME, NODE_ROLE, SHARE_ROLE, SIZE, FolderTreeModel
from je_file_tree.gui import bar_chart
from je_file_tree.gui.charts import BARS, SUNBURST, TREE, TREEMAP, ChartStack
from je_file_tree.gui.sunburst_widget import SunburstWidget
from je_file_tree.gui.treemap_widget import BY_FOLDER, CATEGORY_COLOURS, MIN_SIDE, TreemapWidget


def _wait(app: QApplication, done: Callable[[], bool], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not done():
        assert time.monotonic() < deadline, "timed out"
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    main = create_window(settings)
    yield main
    main.close()
    main.deleteLater()
    i18n.set_language(i18n.DEFAULT_LANGUAGE)
    apply_qt_translation(i18n.DEFAULT_LANGUAGE)


def _scanned(window: MainWindow, qapp: QApplication, folder: Path) -> None:
    window.start_scan(str(folder))
    _wait(qapp, lambda: window.results.outcome is not None)


def _child(node: Node, name: str) -> Node:
    return next(child for child in node.children if child.name == name)


def _select(window: MainWindow, *nodes: Node) -> None:
    """Add ``nodes`` to the tree's selection, as Ctrl+click does."""
    selection = window.results.tree.selectionModel()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    for node in nodes:
        selection.select(window.results.tree_model.index_for(node), flags)


# --- models -----------------------------------------------------------------


def test_tree_model_shows_the_scanned_folder_as_its_only_top_row(qapp: QApplication, sample_tree: Path) -> None:
    model = FolderTreeModel()
    assert model.rowCount() == 0
    root = scan(sample_tree).root
    model.set_root(root)
    top = model.index(0, 0)
    assert model.rowCount() == 1
    assert model.data(top) == str(sample_tree)
    assert model.rowCount(top) == 4
    assert [model.index(row, NAME, top).data() for row in range(4)] == ["big.bin", "photos", "code", "notes.txt"]
    assert model.index(1, SIZE, top).data() == "250 B"
    assert model.index(1, NAME, top).data(SHARE_ROLE) == pytest.approx(0.25)
    assert model.index(0, NAME, top).data(Qt.ItemDataRole.ToolTipRole) == str(sample_tree / "big.bin")


def test_tree_model_index_and_parent_round_trip(qapp: QApplication, sample_tree: Path) -> None:
    model = FolderTreeModel()
    root = scan(sample_tree).root
    model.set_root(root)
    for node in root.iter_nodes():
        index = model.index_for(node)
        assert model.node(index) is node
        parent = model.parent(index)
        assert model.node(parent) is node.parent
        assert model.index(index.row(), 0, parent).data(NODE_ROLE) is node


def test_tree_model_sorts_each_folder_and_keeps_the_selection(qapp: QApplication, sample_tree: Path) -> None:
    model = FolderTreeModel()
    root = scan(sample_tree).root
    model.set_root(root)
    top = model.index(0, 0)
    code = next(child for child in root.children if child.name == "code")
    kept = model.index_for(code)
    persistent = QPersistentModelIndex(kept)
    model.sort(NAME, Qt.SortOrder.AscendingOrder)
    names = [model.index(row, NAME, top).data() for row in range(4)]
    assert names == ["code", "photos", "big.bin", "notes.txt"]  # folders first, then files, by name
    assert persistent.row() == 0 and model.node(QModelIndex(persistent)) is code
    assert [child.name for child in root.children][0] == "big.bin", "the tree itself stays largest first"


def test_removing_an_entry_updates_every_total_above(qapp: QApplication, sample_tree: Path) -> None:
    model = FolderTreeModel()
    root = scan(sample_tree).root
    model.set_root(root)
    photos = next(child for child in root.children if child.name == "photos")
    model.remove(photos)
    top = model.index(0, 0)
    assert model.rowCount(top) == 3
    assert root.size == 750
    assert model.index(0, SIZE).data() == "750 B"


def test_table_models(qapp: QApplication, sample_tree: Path) -> None:
    outcome = analyse(scan(sample_tree))
    largest = LargestFilesModel()
    largest.set_rows(outcome.largest)
    assert largest.rowCount() == 6
    assert largest.index(0, 0).data() == "big.bin"
    assert largest.index(0, 1).data(SORT_ROLE) == 500
    assert isinstance(largest.index(0, 0).data(NODE_ROLE), Node)
    types = FileTypesModel()
    types.set_rows(outcome.extensions)
    shares = [types.index(row, 3).data(SHARE_ROLE) for row in range(types.rowCount())]
    assert sum(shares) == pytest.approx(1.0)
    assert types.headerData(3, Qt.Orientation.Horizontal) == "% of total"


# --- background work gives way ------------------------------------------------


def test_workers_wait_while_the_window_handles_something(qapp: QApplication) -> None:
    pace_workers()
    try:
        seen: list[bool] = []
        QTimer.singleShot(0, lambda: seen.append(pacing.WINDOW.is_open))
        _wait(qapp, lambda: bool(seen))
        assert seen == [False], "the gate is closed while the window handles an event"
        loop = QEventLoop()
        idle_states: list[bool] = []
        dispatcher = QAbstractEventDispatcher.instance()

        def observe_idle() -> None:
            idle_states.append(pacing.WINDOW.is_open)
            loop.quit()

        # Observe after pace_workers' native signal handler. A polling thread
        # can miss a 300 ms idle interval entirely on a loaded host.
        dispatcher.aboutToBlock.connect(observe_idle)
        guard = QTimer(loop)
        guard.setSingleShot(True)
        guard.timeout.connect(loop.quit)
        guard.start(10000)
        try:
            loop.exec()
        finally:
            guard.stop()
            dispatcher.aboutToBlock.disconnect(observe_idle)
        assert idle_states and all(idle_states), "the gate opens whenever the window becomes idle"
    finally:
        pace_workers(connect=False)
    assert pacing.WINDOW.is_open


class _GivingWay(QThread):
    def run(self) -> None:
        pacing.give_way()


def test_waiting_for_a_worker_opens_the_gate_first(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pacing, "PAUSE_LIMIT", 10.0)
    pacing.WINDOW.close()
    worker = _GivingWay()
    try:
        worker.start()
        started = time.monotonic()
        wait_for(worker)  # the window blocks on the worker: holding the gate shut would only stall it
        assert time.monotonic() - started < 2.0
    finally:
        pacing.WINDOW.open()


# --- treemap ----------------------------------------------------------------


def test_every_file_type_group_has_a_colour() -> None:
    assert set(CATEGORY_COLOURS) == set(CATEGORIES)


def test_treemap_lays_out_on_paint_and_finds_tiles(qapp: QApplication, sample_tree: Path) -> None:
    root = scan(sample_tree).root
    widget = TreemapWidget()
    widget.resize(400, 300)
    clicked: list[Node] = []
    widget.node_clicked.connect(clicked.append)
    widget.set_view_root(root)
    widget.grab()
    tile = widget.tile_at(5, 5)
    assert tile is not None
    assert tile.node.name == "big.bin"
    photos = next(child for child in root.children if child.name == "photos")
    widget.set_view_root(next(iter(photos.children)))  # a file: its folder is shown
    assert widget.view_root is photos
    widget.zoom_out()
    assert widget.view_root is root
    widget.deleteLater()


def test_the_bar_chart_lists_a_folder_largest_first(qapp: QApplication, sample_tree: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    root = scan(sample_tree).root
    chart = bar_chart.BarChartWidget()
    chart.resize(500, 300)
    chart.set_view_root(root)
    line = chart.sizeHint().height() / 4
    assert [chart.node_at(line * row + 1).name for row in range(4)] == ["big.bin", "photos", "code", "notes.txt"]
    assert chart.node_at(line * 4 + 1) is None
    chart.grab()  # paints without error
    monkeypatch.setattr(bar_chart, "MAX_BARS", 2)
    chart.invalidate()
    assert chart.sizeHint().height() == 3 * line, "two bars and one line for the other two entries"
    chart.set_view_root(next(child for child in root.children if child.name == "code").children[0])
    assert chart.view_root is not None
    assert chart.view_root.name == "code", "a file shows its folder"
    chart.deleteLater()


def test_the_sunburst_finds_arcs_under_the_mouse_and_zooms(qapp: QApplication, sample_tree: Path) -> None:
    root = scan(sample_tree).root
    widget = SunburstWidget()
    widget.resize(400, 400)
    widget.set_view_root(root)
    widget.grab()
    inner, ring = widget._radii()

    def point(depth: int, fraction: float) -> QPoint:
        radius = inner + (depth - 0.5) * ring
        return QPoint(round(200 + radius * math.sin(fraction * 2 * math.pi)),
                      round(200 - radius * math.cos(fraction * 2 * math.pi)))

    assert widget.hit(200, 200) is root, "the centre is the folder shown"
    photos = widget.hit(point(1, 0.6).x(), point(1, 0.6).y())
    assert photos is not None
    assert photos.node.name == "photos"
    picture = widget.hit(point(2, 0.72).x(), point(2, 0.72).y())
    assert picture is not None
    assert picture.node.name == "b.png"
    assert widget.hit(2, 2) is None, "outside the rings"
    QTest.mouseDClick(widget, Qt.MouseButton.LeftButton, pos=point(1, 0.6))
    assert widget.view_root is photos.node
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(200, 200))
    assert widget.view_root is root, "a click on the centre goes up"
    widget.deleteLater()


def test_the_chart_views_move_together(qapp: QApplication, sample_tree: Path) -> None:
    root = scan(sample_tree).root
    photos = next(child for child in root.children if child.name == "photos")
    charts = ChartStack()
    charts.resize(500, 300)
    moves: list[Node | None] = []
    charts.view_root_changed.connect(moves.append)
    charts.set_view_root(root)
    charts.set_mode(BARS)
    assert charts.mode == BARS
    charts.bars.set_view_root(photos)  # as a double-click in the bars does
    assert charts.view_root is photos
    assert charts.treemap.view_root is photos
    assert charts.sunburst.view_root is photos
    assert charts.tree.view_root is photos
    charts.zoom_out()
    assert charts.bars.view_root is root
    assert charts.treemap.view_root is root
    assert charts.tree.view_root is root
    assert moves == [root, photos, root], "one signal per move, not one per view"
    charts.deleteLater()


# --- the window -------------------------------------------------------------


def test_a_scan_shows_the_results_and_is_remembered(window: MainWindow, qapp: QApplication,
                                                    sample_tree: Path) -> None:
    assert window.pages.currentIndex() == WELCOME_PAGE
    _scanned(window, qapp, sample_tree)
    assert "1,000 B" in window.results.summary.text()
    assert window.results.tree_model.root is not None
    assert window.results.largest_model.rowCount() == 6
    assert window.settings.value("recent") in ([str(sample_tree)], str(sample_tree))
    assert window.results.selected_node() is window.results.tree_model.root


def test_a_missing_folder_is_reported_without_leaving_the_page(window: MainWindow, tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    window.start_scan(str(tmp_path / "missing"))
    assert window.pages.currentIndex() == WELCOME_PAGE
    assert warnings and "missing" in warnings[0]


def test_a_stop_before_anything_was_read_returns_to_the_start_page(window: MainWindow, qapp: QApplication,
                                                                    sample_tree: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    def endless(_path: str, *, cancel, **_kwargs: object) -> None:
        while not cancel.wait(0.01):
            pass
        raise ScanCancelledError

    monkeypatch.setattr(scan_worker, "scan", endless)
    window.start_scan(str(sample_tree))
    assert window.pages.currentIndex() == RESULTS_PAGE
    assert window.results.scan_bar.isVisibleTo(window.results)
    window.stop_scan()
    _wait(qapp, lambda: window.pages.currentIndex() == WELCOME_PAGE)
    assert window.statusBar().currentMessage() == "Scan stopped."
    assert window.results.tree_model.root is None


def _gated_scan(monkeypatch: pytest.MonkeyPatch, root: Path) -> threading.Event:
    """Scan with one worker and hold every folder but the root until the returned gate opens.

    The live tests must see the scan still running when they act, whatever the
    machine's speed; a sleep only makes that likely (a slow CI runner once
    finished the scan before Stop arrived).
    """
    gate = threading.Event()
    real = scanner._read_folder

    def gated(folder, path, *rest):
        if path != str(root):
            gate.wait(10)
        return real(folder, path, *rest)

    monkeypatch.setattr(scanner, "_read_folder", gated)
    monkeypatch.setattr(main_window_module, "ScanOptions", functools.partial(ScanOptions, workers=1))
    return gate


def test_the_tree_shows_and_grows_while_the_scan_runs(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _gated_scan(monkeypatch, sample_tree)
    window.start_scan(str(sample_tree))
    model = window.results.tree_model
    _wait(qapp, lambda: model.root is not None and model.root.file_count > 0)
    _wait(qapp, lambda: "so far" in window.results.summary.text())
    assert model.live and window.results.outcome is None
    window.results.refresh_live()
    top = model.index(0, 0)
    assert model.rowCount(top) == len(model.root.children) > 0
    window.results.tree.expand(top)
    gate.set()
    _wait(qapp, lambda: window.results.outcome is not None, timeout=15)
    assert not model.live
    assert window.results.tree.isExpanded(model.index(0, 0)), "what was opened during the scan stays open"
    assert "1,000 B" in window.results.summary.text()
    assert not window.results.scan_bar.isVisibleTo(window.results)


def test_stopping_keeps_what_was_read(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _gated_scan(monkeypatch, sample_tree)
    window.start_scan(str(sample_tree))
    model = window.results.tree_model
    _wait(qapp, lambda: model.root is not None and model.root.file_count > 0)
    window.stop_scan()
    gate.set()  # the one folder being read finishes; the rest stay unread
    _wait(qapp, lambda: window.results.outcome is not None, timeout=15)
    outcome = window.results.outcome
    assert outcome.partial
    assert window.pages.currentIndex() == RESULTS_PAGE
    assert "incomplete" in window.results.summary.text()
    assert window.statusBar().currentMessage().startswith("Scan stopped: the results show")
    unread = [node for node in outcome.result.root.iter_nodes() if node.error == scanner.NOT_SCANNED]
    assert unread
    tip = model.index_for(unread[0]).data(Qt.ItemDataRole.ToolTipRole)
    assert "Not scanned" in tip


def test_switching_language_and_unit(window: MainWindow, qapp: QApplication, sample_tree: Path) -> None:
    _scanned(window, qapp, sample_tree)
    window.change_language("zh-TW")
    assert window.menuBar().actions()[0].text() == "檔案(&F)"
    assert window.results.tabs.tabText(1) == "最大的檔案"
    assert window.results.tree_model.headerData(SIZE, Qt.Orientation.Horizontal) == "大小"
    window.set_unit("KB")
    assert window.results.tree_model.index(0, SIZE).data() == "1.0 KB"
    assert window.settings.value("unit") == "KB"


def test_export_writes_the_chosen_file(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                       tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scanned(window, qapp, sample_tree)
    target = tmp_path / "out.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args: (str(target), ""))
    window.export_results("folders")  # written on a worker thread
    _wait(qapp, lambda: "4 rows" in window.statusBar().currentMessage())
    assert target.read_text(encoding="utf-8-sig").startswith("path,size_bytes")
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args: (str(tmp_path / "missing" / "x.csv"), ""))
    window.export_results("largest")
    _wait(qapp, lambda: bool(warnings))
    assert warnings[0].startswith("The file could not be saved.")


def test_move_to_trash_asks_then_updates_the_results(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    _scanned(window, qapp, sample_tree)
    root = window.results.tree_model.root
    assert root is not None
    big = root.children[0]
    trashed: list[str] = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    window.move_to_trash([big])
    _wait(qapp, lambda: window._trash_worker is None)
    assert root.size == 1000
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: trashed.append(path) or True)
    monkeypatch.setattr(window, 'rescan_folder', lambda _node: None)
    window.move_to_trash([big])
    _wait(qapp, lambda: window._trash_worker is None)
    assert trashed == [str(sample_tree / "big.bin")]
    assert root.size == 500
    assert [node.name for node in window.results.largest_model.rows()][0] == "a.jpg"
    assert all(stat.extension != ".bin" for stat in window.results.types_model.rows())
    assert "500 B" in window.statusBar().currentMessage()


@pytest.mark.parametrize("qt_result,expected", [(False, False), (True, True),
                                               ((False, ""), False), ((True, "trash-path"), True)])
def test_trash_wrapper_reports_qt_tuple_failures(qt_result, expected, monkeypatch) -> None:
    monkeypatch.setattr(file_actions.QFile, "moveToTrash", lambda _path: qt_result)
    assert file_actions.move_to_trash("unused") is expected


def test_failed_trash_reports_holders_from_worker(window, qapp, sample_tree, monkeypatch) -> None:
    from je_file_tree.core.lock_holders import Holder, LockReport
    from je_file_tree.gui import trash_worker

    _scanned(window, qapp, sample_tree)
    root = window.results.tree_model.root
    node = root.children[0]
    warnings, threads = [], []

    def diagnose(entry, *, cancel):
        threads.append(threading.get_ident())
        return LockReport([Holder(123, "Editor")], incomplete=True)

    monkeypatch.setattr(trash_worker, "find_holders", diagnose)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: False)
    monkeypatch.setattr(window, "rescan_folder", lambda node: None)
    window.move_to_trash([node])
    _wait(qapp, lambda: window._trash_worker is None)
    assert "Editor (PID 123)" in warnings[0] and "visibility is limited" in warnings[0]
    assert threads and threads[0] != threading.get_ident()
    assert node in root.children and Path(node.path).is_file()


def test_file_replaced_during_confirmation_is_skipped_and_parent_rescanned(
        window: MainWindow, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file = tmp_path / "chosen"
    file.write_bytes(b"old")
    _scanned(window, qapp, tmp_path)
    root = window.results.tree_model.root
    node = _child(root, "chosen")
    warnings, moved, rescanned = [], [], []

    def replace_during_question(*_args):
        file.rename(tmp_path / "previous")
        file.write_bytes(b"new")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", replace_during_question)
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    monkeypatch.setattr(window, "rescan_folder", rescanned.append)
    window.move_to_trash([node])
    _wait(qapp, lambda: window._trash_worker is None and bool(rescanned))
    assert moved == [] and file.read_bytes() == b"new"
    assert warnings and "entry was replaced" in warnings[0]
    assert rescanned == [root]
    assert "skipped 1" in window.statusBar().currentMessage()


def test_move_batch_rescans_the_actual_affected_parent(
        window: MainWindow, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "scan"
    folder.mkdir()
    (folder / "chosen").write_bytes(b"data")
    _scanned(window, qapp, folder)
    node = window.results.tree_model.root.children[0]
    old_root = window.results.tree_model.root
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)

    def moved(path):
        Path(path).rename(tmp_path / "moved")
        return True

    monkeypatch.setattr(file_actions, "trash_receipt", moved)
    window.move_to_trash([node])
    _wait(qapp, lambda: window._trash_worker is None and window._worker is None
          and window.results.tree_model.root is not old_root)
    assert window.results.tree_model.root.file_count == 0
    assert (tmp_path / "moved").read_bytes() == b"data"


def test_system_and_program_folders_are_asked_about_twice(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    _scanned(window, qapp, sample_tree)
    root = window.results.tree_model.root
    assert root is not None
    photos, big = _child(root, "photos"), _child(root, "big.bin")
    window._protected = [Protection(str(sample_tree / "photos"), PROGRAMS)]
    asked: list[str] = []
    warnings: list[str] = []
    trashed: list[str] = []
    answers = iter([QMessageBox.StandardButton.No])
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text, *_buttons: warnings.append(text)
                        or next(answers))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda _parent, _title, text: asked.append(text) or QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: trashed.append(path) or True)
    monkeypatch.setattr(window, 'rescan_folder', lambda _node: None)
    window.move_to_trash([photos, big])
    _wait(qapp, lambda: window._trash_worker is None)
    assert len(warnings) == 1
    assert f"• {sample_tree / 'photos'} — installed programs" in warnings[0]
    assert "big.bin" not in warnings[0], "only the protected entries are named"
    assert asked == [], "No to the first question: the usual question is not even asked"
    assert trashed == []
    answers = iter([QMessageBox.StandardButton.Yes])
    window.move_to_trash([photos, big])
    _wait(qapp, lambda: window._trash_worker is None)
    assert len(asked) == 1, "Yes: then the usual question"
    assert sorted(trashed) == sorted([str(sample_tree / "photos"), str(sample_tree / "big.bin")])
    window.move_to_trash([_child(root, "notes.txt")])
    _wait(qapp, lambda: window._trash_worker is None)
    assert len(warnings) == 2, "nothing protected: no extra question"


def test_several_selected_entries_go_to_the_recycle_bin_after_one_question(
        window: MainWindow, qapp: QApplication, sample_tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scanned(window, qapp, sample_tree)
    root = window.results.tree_model.root
    assert root is not None
    photos = _child(root, "photos")
    window.results.tree.selectionModel().clearSelection()
    _select(window, _child(root, "big.bin"), photos, _child(photos, "a.jpg"), _child(root, "notes.txt"))
    assert window.statusBar().currentMessage() == "4 items selected: 850 B", "a.jpg is inside photos: counted once"
    _select(window, root)
    questions: list[str] = []
    warnings: list[str] = []
    trashed: list[str] = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda _parent, _title, text: questions.append(text) or QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    monkeypatch.setattr(file_actions, "trash_receipt",
                        lambda path: trashed.append(path) or not path.endswith("notes.txt"))
    monkeypatch.setattr(window, 'rescan_folder', lambda _node: None)
    window._trash_selected()  # what Delete does
    _wait(qapp, lambda: window._trash_worker is None)
    assert len(questions) == 1
    assert "3 items (850 B in total)" in questions[0]
    assert questions[0].index("• big.bin (500 B)") < questions[0].index("• photos (250 B)")
    assert "a.jpg" not in questions[0]
    assert sorted(trashed) == sorted(str(sample_tree / name) for name in ("big.bin", "photos", "notes.txt"))
    assert len(warnings) == 1 and "notes.txt" in warnings[0], "the refused entry is named"
    assert root.size == 250
    assert {child.name for child in root.children} == {"code", "notes.txt"}
    assert {node.name for node in window.results.largest_model.rows()} == {"notes.txt", "main.py", "Makefile"}
    assert not {".bin", ".jpg", ".png"} & {stat.extension for stat in window.results.types_model.rows()}
    assert window.statusBar().currentMessage() == "Moved 2, skipped 0, failed 1; 750 B moved to the Recycle Bin."


def test_the_context_menu_acts_on_the_selection_it_was_opened_on(
        window: MainWindow, qapp: QApplication, sample_tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scanned(window, qapp, sample_tree)
    window.resize(1000, 700)
    window.show()
    results = window.results
    root = results.tree_model.root
    assert root is not None
    big, notes, photos = (_child(root, name) for name in ("big.bin", "notes.txt", "photos"))
    results.tree.expand(results.tree_model.index_for(root))
    qapp.processEvents()
    results.tree.selectionModel().clearSelection()
    _select(window, big, notes)
    menus: list[list[str]] = []

    class RecordingMenu(QMenu):
        def exec(self, *_args: object) -> None:  # instead of popping up and waiting for a click
            menus.append([action.text() for action in self.actions()])

    monkeypatch.setattr(main_window_module, "QMenu", RecordingMenu)
    requests: list[tuple[Node, list[Node]]] = []
    results.node_menu_requested.connect(lambda node, picked, _point: requests.append((node, picked)))
    for node in (notes, photos):
        results._menu_for(results.tree, results.tree.visualRect(results.tree_model.index_for(node)).center())
    assert requests[0][0] is notes and {id(node) for node in requests[0][1]} == {id(big), id(notes)}
    assert requests[1][0] is photos and requests[1][1] == [photos], "a click outside the selection acts alone"
    assert menus[0][-1] == "Move 2 items to Recycle Bin"
    assert menus[1][-1] == "Move to Recycle Bin"
    window.show_menu_for(root, [root], QPoint())
    assert "Move to Recycle Bin" not in menus[2], "the scanned folder itself cannot be moved"


def test_search_finds_entries_anywhere_and_follows_changes_to_the_tree(
        window: MainWindow, qapp: QApplication, sample_tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scanned(window, qapp, sample_tree)
    results = window.results
    panel = results.search
    root = results.tree_model.root
    assert root is not None
    window._find()  # what Ctrl+F does
    assert results.tabs.currentIndex() == SEARCH_TAB
    panel.box.setText("*.jpg;*.png")  # searched once typing pauses
    _wait(qapp, lambda: len(results.search_model.rows()) == 2 and not panel.busy)
    assert [node.name for node in results.search_model.rows()] == ["a.jpg", "b.png"]
    assert panel.summary.text() == "2 matches, 250 B in total."
    panel.box.setText("photos")
    panel.box.returnPressed.emit()  # Enter searches at once
    _wait(qapp, lambda: not panel.busy)
    photos = _child(root, "photos")
    assert results.search_model.rows() == [photos]
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda _path: True)
    monkeypatch.setattr(window, 'rescan_folder', lambda _node: None)
    window.move_to_trash([photos])
    _wait(qapp, lambda: window._trash_worker is None)
    _wait(qapp, lambda: not panel.busy)
    assert panel.summary.text() == "Nothing matches.", "the search runs again after the tree changed"
    window.start_scan(str(sample_tree))  # the folder is still there: moving it was pretended
    assert not panel.box.isEnabled(), "no searching while a scan fills the tree"
    _wait(qapp, lambda: window.results.outcome is not None and not panel.busy)
    assert panel.box.isEnabled()
    assert [node.name for node in results.search_model.rows()] == ["photos"]


def test_the_tree_and_the_summary_show_the_space_taken_on_disk(window: MainWindow, qapp: QApplication,
                                                                  sample_tree: Path) -> None:
    _scanned(window, qapp, sample_tree)
    model = window.results.tree_model
    root = model.root
    assert root is not None and root.allocated > 0
    assert model.headerData(ALLOCATED, Qt.Orientation.Horizontal) == "On disk"
    assert model.index(0, ALLOCATED).data() == format_size(root.allocated)
    assert f"({format_size(root.allocated)} on disk)" in window.results.summary.text()


def test_duplicates_are_found_on_request_and_their_extra_copies_trashed(
        window: MainWindow, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "copies"
    folder.mkdir()
    for name in ("photo.jpg", "photo (1).jpg", "photo (2).jpg"):
        (folder / name).write_bytes(b"p" * 5000)
    (folder / "notes.txt").write_bytes(b"n" * 300)
    (folder / "notes-old.txt").write_bytes(b"n" * 300)
    for oldest in ("photo.jpg", "notes-old.txt"):  # the oldest copy of each is the one kept
        os.utime(folder / oldest, (1_600_000_000, 1_600_000_000))
    _scanned(window, qapp, folder)
    panel = window.results.duplicates
    assert panel.start_button.isEnabled()
    assert not panel.groups
    assert panel.status.text().startswith("Finds files with the same content")
    panel.min_size.setCurrentIndex(0)  # any size: these files are small
    panel.start()
    _wait(qapp, lambda: not panel.running)
    assert [len(group.files) for group in panel.groups] == [3, 2]
    assert panel.status.text() == "2 groups of duplicates: 10.1 KB logical size in extra copies."
    assert panel.model.index(0, 0).data().startswith("3 copies × 4.9 KB: 9.8 KB logical extra-copy size.")
    assert "undecided groups are unknown" in panel.estimate.text()
    assert panel.model.index(0, 0, panel.model.index(0, 0)).data() == "photo.jpg", "oldest first"
    assert not panel.select_extra.isEnabled()
    for row in range(2):
        panel.view.setCurrentIndex(panel.model.index(0, 0, panel.model.index(row, 0)))
        panel.choose_kept_copy()
        _wait(qapp, lambda: not panel.running)
    assert panel.model.index(0, 0, panel.model.index(0, 0)).data() == "Kept: photo.jpg"
    panel.select_extra_copies()
    picked = _selected_in(panel.view)
    assert sorted(node.name for node in picked) == ["notes.txt", "photo (1).jpg", "photo (2).jpg"]
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda _path: True)
    monkeypatch.setattr(window, 'rescan_folder', lambda _node: None)
    window.move_to_trash(picked)
    _wait(qapp, lambda: window._trash_worker is None)
    assert panel.groups == [], "every group is down to one file"
    assert panel.status.text() == "No duplicate files found."
    panel.start()
    panel.stop()
    assert panel.status.text() == "The search was stopped."
    assert not panel.running


def test_comparing_with_a_saved_scan_shows_what_changed(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                                       tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    saved = tmp_path / "before.json"
    _scanned(window, qapp, sample_tree)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args: (str(saved), ""))
    window.export_results("json")  # the scan saved for later
    _wait(qapp, lambda: "Saved" in window.statusBar().currentMessage())
    results = window.results
    assert not results.tabs.isTabVisible(CHANGES_TAB), "no comparison yet"
    (sample_tree / "photos" / "c.jpg").write_bytes(b"j" * 300)
    (sample_tree / "big.bin").unlink()
    window.rescan()
    _wait(qapp, lambda: results.outcome is not None and results.tree_model.root.size == 800)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(saved), ""))
    window._actions["compare"].trigger()
    _wait(qapp, lambda: results.tabs.isTabVisible(CHANGES_TAB) and not results.changes.busy)
    assert results.tabs.currentIndex() == CHANGES_TAB
    rows = {change.path: (change.before, change.after) for change in results.changes_model.rows()}
    assert rows == {"": (1000, 800), "photos": (250, 550)}
    assert "1,000 B then, 800 B now (−200 B); 2 folders changed." in results.changes.summary.text()
    (sample_tree / "photos" / "c.jpg").unlink()
    window.rescan()  # the comparison follows the new scan
    _wait(qapp, lambda: results.outcome is not None and not results.changes.busy
          and len(results.changes_model.rows()) == 1)
    assert [change.path for change in results.changes_model.rows()] == [""]
    results.changes.stop_comparing()
    assert not results.tabs.isTabVisible(CHANGES_TAB)
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    (tmp_path / "other.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(tmp_path / "other.json"), ""))
    window._actions["compare"].trigger()
    _wait(qapp, lambda: bool(warnings))
    assert "not a scan saved by FileTree" in warnings[0]
    assert not results.tabs.isTabVisible(CHANGES_TAB)


def test_the_treemap_draws_a_folder_s_specks_as_one_group_tile(qapp: QApplication) -> None:
    root = Node("root", True, children=[])
    many = Node("many", True, children=[], parent=root)
    many.children.extend(Node(f"f{index}.txt", False, size=1, parent=many) for index in range(300))
    many.children.append(Node("big.bin", False, size=5000, parent=many))
    many.size = 5300
    root.children.extend([many, Node("other.bin", False, size=5300, parent=root)])
    root.size = 10600
    widget = TreemapWidget()
    widget.resize(400, 300)
    widget.set_view_root(root)
    widget.grab()
    assert all(min(tile.rect.width, tile.rect.height) >= MIN_SIDE for tile in widget._tiles)
    group = next(tile for tile in widget._tiles if tile.grouped)
    assert (group.node, group.grouped, group.grouped_size) == (many, 300, 300)
    assert "300" in widget._describe(group) and i18n.tr("treemap_more_open") in widget._describe(group)
    centre = QPoint(int(group.rect.x + group.rect.width / 2), int(group.rect.y + group.rect.height / 2))
    assert widget.tile_at(centre.x(), centre.y()) is group
    widget.set_selected(many)
    assert widget._tile_of(many) is not group, "selecting the folder outlines the folder, not its group"
    QTest.mouseDClick(widget, Qt.MouseButton.LeftButton, pos=centre)
    assert widget.view_root is many, "double-clicking the group shows its folder on its own"
    widget.grab()
    inside = next(tile for tile in widget._tiles if tile.grouped)
    assert inside.node is many
    assert i18n.tr("treemap_more_open") not in widget._describe(inside), "already shown on its own"
    widget.deleteLater()


def test_the_treemap_levels_and_colours(qapp: QApplication, sample_tree: Path) -> None:
    root = scan(sample_tree).root
    widget = TreemapWidget()
    widget.resize(400, 300)
    widget.set_view_root(root)
    assert widget.levels == 2
    widget.grab()
    assert {tile.depth for tile in widget._tiles} == {1, 2}
    widget.set_levels(1)
    widget.grab()
    assert {tile.depth for tile in widget._tiles} == {1}
    widget.set_levels(5)  # not offered: ignored
    assert widget.levels == 1
    widget.set_levels(2)
    widget.set_colour_mode(BY_FOLDER)
    widget.grab()
    photos, code = (next(child for child in root.children if child.name == name) for name in ("photos", "code"))
    assert widget._colour(photos.children[0], 2).hue() != widget._colour(code.children[0], 2).hue(), (
        "files take the hue of their top-level folder")
    assert widget._colour(photos.children[0], 2).hue() == widget._colour(photos.children[1], 2).hue()
    widget.set_colour_mode("rainbow")  # not offered: ignored
    assert widget.colour_mode == BY_FOLDER
    widget.deleteLater()


def test_the_chart_mode_is_remembered(window: MainWindow, qapp: QApplication, sample_tree: Path) -> None:
    _scanned(window, qapp, sample_tree)
    assert window.results.charts.mode == TREEMAP, "the treemap comes first"
    assert window.results._chart_buttons[TREEMAP].isChecked()
    assert not window.results._treemap_options.isHidden(), "the treemap options come with the treemap"
    window.results._levels_combo.setCurrentIndex(window.results._levels_combo.findData(3))
    window.results._colours_combo.setCurrentIndex(window.results._colours_combo.findData(BY_FOLDER))
    assert (window.settings.value("treemap_levels"), window.settings.value("treemap_colours")) == (3, BY_FOLDER)
    assert window.results._legend.isHidden(), "no file-type legend when colouring by folder"
    window.results._chart_buttons[BARS].click()
    assert window.results.charts.mode == BARS
    assert window.settings.value("chart_mode") == BARS
    assert not window.results._legend.isHidden(), "the bars keep the file-type colours"
    assert window.results._treemap_options.isHidden()
    again = create_window(window.settings)
    assert again.results.charts.mode == BARS, "the view chosen last comes back"
    assert (again.results.charts.treemap.levels, again.results.charts.treemap.colour_mode) == (3, BY_FOLDER)
    again.results.apply_chart_settings({"treemap_levels": "many", "chart_mode": "pie"})  # hand-edited: ignored
    assert again.results.charts.treemap.levels == 3
    assert again.results.charts.mode == BARS
    again.results._chart_buttons[SUNBURST].click()
    assert again.results._legend.isHidden(), "the sunburst colours by folder"
    again.results._chart_buttons[TREE].click()
    assert again.results.charts.mode == TREE
    assert not again.results._tree_options.isHidden()
    again.results._tree_orientation_combo.setCurrentIndex(
        again.results._tree_orientation_combo.findData("vertical"))
    assert again.settings.value("tree_orientation") == "vertical"
    restored = create_window(again.settings)
    assert restored.results.charts.mode == TREE
    assert restored.results.charts.tree.orientation == "vertical"
    restored.close()
    restored.deleteLater()
    again.close()
    again.deleteLater()


def test_exclusions_are_skipped_greyed_out_and_saved(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    window.settings.setValue("exclusions", "photos")  # what an INI file gives back for a one-item list
    assert window.exclusions() == ["photos"]
    _scanned(window, qapp, sample_tree)
    model = window.results.tree_model
    root = model.root
    assert root is not None
    photos = _child(root, "photos")
    assert photos.error == scanner.EXCLUDED
    assert root.size == 750
    index = model.index_for(photos)
    assert "Skipped: it is in View → Skip while scanning" in index.data(Qt.ItemDataRole.ToolTipRole)
    assert index.data(Qt.ItemDataRole.ForegroundRole) is not None, "greyed out"
    assert window.results.problems_model.rowCount() == 0, "skipping is not a problem"

    class Editing(main_window_module.ExclusionsDialog):
        def exec(self) -> int:
            self.add("node_modules")
            self.add("NODE_MODULES")  # already listed, whatever the case
            self.add("   ")
            self.list.item(0).setSelected(True)
            self.remove_selected()  # photos goes
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_module, "ExclusionsDialog", Editing)
    window.edit_exclusions()
    assert window.exclusions() == ["node_modules"]
    assert "1 exclusions saved" in window.statusBar().currentMessage()
    window.rescan()
    _wait(qapp, lambda: window.results.outcome is not None and window.results.tree_model.root.size == 1000)


def test_the_lists_can_cover_the_selected_folder_only(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    _scanned(window, qapp, sample_tree)
    results = window.results
    root = results.tree_model.root
    assert root is not None
    button = results._scope_button
    assert button.isHidden(), "not on the Chart tab"
    results.tabs.setCurrentIndex(LARGEST_TAB)
    assert not button.isHidden()

    def largest() -> list[str]:
        return [node.name for node in results.largest_model.rows()]

    photos, code = _child(root, "photos"), _child(root, "code")
    results.select_node(photos)
    button.click()
    _wait(qapp, lambda: largest() == ["a.jpg", "b.png"])
    assert {stat.extension for stat in results.types_model.rows()} == {".jpg", ".png"}
    assert button.text() == "Only in photos"
    results.select_node(code)  # the lists follow the selection, once it settles
    _wait(qapp, lambda: largest() == ["main.py", "Makefile"])
    results.select_node(_child(code, "main.py"))  # a file: its folder
    qapp.processEvents()
    _wait(qapp, lambda: not results._scope_timer.isActive() and results._scope_worker is None)
    assert largest() == ["main.py", "Makefile"]
    results.show_largest_of_type(".jpg")
    _wait(qapp, lambda: results._focus_worker is None)
    assert largest() == [], "a type's largest files within the folder shown"
    results.show_all_largest()
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda _path: True)
    monkeypatch.setattr(window, 'rescan_folder', lambda _node: None)
    window.move_to_trash([_child(code, "Makefile")])
    _wait(qapp, lambda: window._trash_worker is None)
    _wait(qapp, lambda: largest() == ["main.py"])
    assert sum(stat.size for stat in results.types_model.rows()) == 100, "the folder's types after the move"
    button.click()  # back to the whole scan, whose totals followed the move too
    assert sorted(largest()) == ["a.jpg", "b.png", "big.bin", "main.py", "notes.txt"], "Makefile is gone"
    assert largest()[:2] == ["big.bin", "a.jpg"]
    assert sum(stat.size for stat in results.types_model.rows()) == 950


def test_search_conditions_and_saved_searches(window: MainWindow, qapp: QApplication, sample_tree: Path) -> None:
    _scanned(window, qapp, sample_tree)
    panel = window.results.search

    def found() -> list[str]:
        _wait(qapp, lambda: not panel.busy)
        return sorted(node.name for node in window.results.search_model.rows())

    filters = panel.filters
    filters.category.setCurrentIndex(filters.category.findData("images"))  # a condition alone searches
    assert found() == ["a.jpg", "b.png"]
    filters.kind.setCurrentIndex(filters.kind.findData("folders"))
    assert found() == [], "a file type means files"
    filters.apply({})  # back to any
    filters.kind.setCurrentIndex(filters.kind.findData("folders"))
    assert found() == ["code", "empty", "photos"]
    filters.min_size.setCurrentIndex(filters.min_size.findData(10 << 30))  # 10 GB: nothing that big here
    assert found() == []
    assert filters.min_size.currentData() == 10 << 30, "sizes beyond 32 bits survive the list"
    filters.apply({"kind": "files"})
    panel.box.setText("*.p*")
    panel.rerun()
    assert found() == ["b.png", "main.py"]
    panel.save("Pictures and code")
    saved = json.loads(window.settings.value("saved_searches"))
    assert saved == {"Pictures and code": {"text": "*.p*", "min_size": None, "max_size": None, "changed": "any",
                                           "category": None, "kind": "files"}}
    again = create_window(window.settings)  # a new window finds it in the settings
    assert again.results.search.saved.findData("Pictures and code") > 0
    again.close()
    again.deleteLater()
    panel.box.setText("")
    filters.apply({})
    panel.saved.setCurrentIndex(panel.saved.findData("Pictures and code"))
    panel._load_saved()
    assert panel.box.text() == "*.p*"
    assert filters.kind.currentData() == "files"
    assert found() == ["b.png", "main.py"]
    panel.delete_saved()
    assert json.loads(window.settings.value("saved_searches")) == {}
    window.settings.setValue("saved_searches", "not json")
    assert main_window_module._saved_searches(window.settings) == {}, "a damaged setting counts as none"


def test_clean_up_suggestions_are_found_after_a_scan_and_follow_moves(
        window: MainWindow, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "work"
    folder.mkdir()
    make_tree(folder, {"site": {"package.json": b"{}", "node_modules": {"lib.js": b"j" * 400}},
                       "old": {"nothing": {}}, "memory.dmp": b"d" * 50, "keep.txt": b"k"})
    age_tree(folder)
    _scanned(window, qapp, folder)
    results = window.results
    assert results.tabs.tabText(CLEANUP_TAB) == "Clean up"
    assert results.cleanup_pages.tabText(0) == "Suggestions"
    assert results.cleanup_pages.tabText(1) == "Duplicates"
    panel = results.cleanup
    _wait(qapp, lambda: not panel.busy and bool(panel.groups))
    assert [(group.key, [node.name for node in group.nodes]) for group in panel.groups] == [
        ("build_output", ["node_modules"]), ("crash_dumps", ["memory.dmp"]), ("empty_folders", ["old"])]
    assert panel.model.index(0, 0).data() == "Build output (can be rebuilt) — 400 B (1)"
    assert "building the project again" in panel.model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole)
    assert panel.status.text().startswith("450 B logical size in 3 groups.")
    monkeypatch.setattr(main_window_module.CleanupReview, "exec", lambda _self: QDialog.DialogCode.Rejected)
    panel.view.setCurrentIndex(panel.model.index(0, 0, panel.model.index(0, 0)))
    panel.select_current_group()
    picked = _selected_in(panel.view)
    assert [node.name for node in picked] == ["node_modules"]
    def check_manually(dialog):
        dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_module.CleanupReview, "exec", check_manually)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda _path: True)
    monkeypatch.setattr(window, 'rescan_folder', lambda _node: None)
    window.move_to_trash(picked)
    _wait(qapp, lambda: window._trash_worker is None)
    _wait(qapp, lambda: not panel.busy and [group.key for group in panel.groups] == ["crash_dumps", "empty_folders"])
    monkeypatch.setattr(main_window_module.CleanupReview, "exec", lambda _self: QDialog.DialogCode.Rejected)
    panel.select_all_entries()
    assert not panel.select_all.isEnabled(), "manual groups cannot be bulk-selected"


def test_incomplete_cleanup_disables_bulk_selection_and_discards_stale_rows(
        window: MainWindow, qapp: QApplication, tmp_path: Path) -> None:
    make_tree(tmp_path, {"memory.dmp": b"x", "node_modules": {"skipped": {"file": b"important"}}})
    age_tree(tmp_path)
    outcome = analyse(scan(tmp_path, options=ScanOptions(exclude=("skipped",))))
    window.results.show_outcome(outcome)
    panel = window.results.cleanup
    _wait(qapp, lambda: not panel.busy)
    assert [group.key for group in panel.groups] == ["crash_dumps"]
    assert not panel.select_all.isEnabled()


    assert "Omitted bytes are unknown" in panel.coverage_banner.text()
    panel.select_all_entries()
    assert _selected_in(panel.view) == []
    panel.refresh()
    assert panel.groups == [] and panel.model.rowCount() == 0
    assert not panel.select_group.isEnabled()
    _wait(qapp, lambda: not panel.busy)
    panel.set_root(outcome.result.root, partial=True)
    _wait(qapp, lambda: not panel.busy)
    assert not panel.select_all.isEnabled()


def test_cleanup_review_can_remove_protected_entries_from_a_mixed_batch(
        window: MainWindow, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_tree(tmp_path, {"memory.dmp": b"dump", "guarded": {"program": b"important"}})
    age_tree(tmp_path)
    _scanned(window, qapp, tmp_path)
    _wait(qapp, lambda: not window.results.cleanup.busy)
    root = window.results.tree_model.root
    safe, protected = _child(root, "memory.dmp"), _child(root, "guarded")
    window._protected = [Protection(protected.path, PROGRAMS)]
    reviewed, moved, questions = [], [], []

    def review(dialog):
        dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        reviewed.append(dialog.model.data(dialog.model.index(1, 7)))
        dialog.model.setData(dialog.model.index(1, 0), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_module.CleanupReview, "exec", review)
    monkeypatch.setattr(QMessageBox, "question", lambda _parent, _title, text:
                        questions.append(text) or QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    monkeypatch.setattr(window, "rescan_folder", lambda _node: None)
    window.move_to_trash([safe, protected])
    _wait(qapp, lambda: window._trash_worker is None)
    assert reviewed == ["installed programs"]
    assert moved == [str(tmp_path / "memory.dmp")] and len(questions) == 1
    assert protected.is_in(root) and (tmp_path / "guarded" / "program").read_bytes() == b"important"


def test_cancelling_cleanup_review_never_opens_trash_confirmation(
        window: MainWindow, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "memory.dmp").write_bytes(b"dump")
    age_tree(tmp_path)
    _scanned(window, qapp, tmp_path)
    _wait(qapp, lambda: not window.results.cleanup.busy)
    node = _child(window.results.tree_model.root, "memory.dmp")
    reviewed, questions, moved = [], [], []

    def cancel(dialog):
        reviewed.append(dialog.model.data(dialog.model.index(0, 1)))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window_module.CleanupReview, "exec", cancel)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: questions.append(True))
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    window.move_to_trash([node])
    assert reviewed == [node.path] and questions == [] and moved == []
    assert (tmp_path / "memory.dmp").read_bytes() == b"dump"


def test_replacing_the_selected_scan_while_review_is_open_invalidates_the_batch(
        window: MainWindow, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "memory.dmp").write_bytes(b"dump")
    age_tree(tmp_path)
    _scanned(window, qapp, tmp_path)
    _wait(qapp, lambda: not window.results.cleanup.busy)
    node = _child(window.results.tree_model.root, "memory.dmp")
    warnings, moved = [], []

    def replace_scan(dialog):
        dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        window.results.show_outcome(analyse(scan(tmp_path)))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_module.CleanupReview, "exec", replace_scan)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    window.move_to_trash([node])
    assert moved == [] and warnings and "outside the current scan" in warnings[0]


def test_long_paths_are_shortened_not_widening_the_window(window: MainWindow, qapp: QApplication,
                                                          tmp_path: Path) -> None:
    label = ElidedLabel()
    label.resize(300, 20)
    long_path = "C:\\" + "\\".join(["a-rather-long-folder-name"] * 8) + "\\photos"
    label.setText(long_path)
    assert label.full_text() == long_path
    assert label.toolTip() == long_path
    assert "…" in label.text()
    assert label.text().endswith("photos"), "shortened in the middle: the end of a path says the most"
    assert label.minimumSizeHint().width() < 300
    label.deleteLater()
    deep = tmp_path.joinpath(*["a-rather-long-folder-name"] * 6, "R&D")
    deep.mkdir(parents=True)
    (deep / "x.txt").write_bytes(b"x")
    _scanned(window, qapp, deep)
    results = window.results
    path_width = results.breadcrumbs.fontMetrics().horizontalAdvance(str(deep))
    assert results.tabs.widget(CHART_TAB).minimumSizeHint().width() < path_width, "breadcrumbs keep paths bounded"
    assert results.summary.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert "R&amp;D" in results.summary.text(), "the path is escaped in the rich-text summary"
    assert results.summary.toolTip() == str(deep)


def test_dropped_urls_and_the_help_dialog(window: MainWindow, sample_tree: Path) -> None:
    urls = [QUrl.fromLocalFile(str(sample_tree / "big.bin")), QUrl.fromLocalFile(str(sample_tree / "code"))]
    assert _dropped_folder(urls) == str(sample_tree / "code")
    assert _dropped_folder([QUrl("https://example.com/")]) is None
    dialog = HelpDialog(window)
    assert "FileTree" in dialog.browser.toPlainText()
    dialog.deleteLater()


def test_linux_asks_the_file_manager_to_select_before_opening_the_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(file_actions.sys, "platform", "linux")
    monkeypatch.setattr(file_actions, "open_path", lambda path: opened.append(path) or True)
    monkeypatch.setattr(file_actions, "show_items", lambda _path: True)
    assert file_actions.reveal_in_file_manager("/home/me/photos/a.jpg")
    assert opened == [], "the file manager showed it selected"
    monkeypatch.setattr(file_actions, "show_items", lambda _path: False)
    assert file_actions.reveal_in_file_manager("/home/me/photos/a.jpg")
    assert opened == ["/home/me/photos"], "no file manager answered: its folder is opened"


def test_show_items_needs_a_session_bus(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_actions, "QDBusConnection", None)
    assert file_actions.show_items("/home/me/x") is False


def test_explorer_command_always_quotes_the_path() -> None:
    assert file_actions.explorer_command("C:\\trip,day1\\a.jpg") == 'explorer /select,"C:\\trip,day1\\a.jpg"'


def test_double_clicking_a_type_or_an_age_lists_its_largest_files(window: MainWindow, qapp: QApplication,
                                                                  sample_tree: Path) -> None:
    _scanned(window, qapp, sample_tree)
    results = window.results
    assert results.age_model.rowCount() == 5
    results.show_largest_of_type(".jpg")
    _wait(qapp, lambda: results._focus_worker is None)
    assert [node.name for node in results.largest_model.rows()] == ["a.jpg"]
    assert results.tabs.currentIndex() == 1
    assert "Showing only: .jpg" in results._focus_label.text()
    results.show_largest_of_type("")
    _wait(qapp, lambda: results._focus_worker is None)
    assert [node.name for node in results.largest_model.rows()] == ["Makefile"]
    assert "(no extension)" in results._focus_label.text()
    results.show_largest_of_age("month")
    _wait(qapp, lambda: results._focus_worker is None)
    assert len(results.largest_model.rows()) == 6, "the sample files were all written just now"
    results.show_all_largest()
    assert results.largest_model.rowCount() == 6 and results._focus_bar.isHidden()
    types_index = results.types_table.model().index(0, 0)
    results.types_table.doubleClicked.emit(types_index)
    assert not results._focus_bar.isHidden()


def test_rescanning_one_folder_swaps_it_in_and_updates_every_list(window: MainWindow, qapp: QApplication,
                                                                   sample_tree: Path) -> None:
    _scanned(window, qapp, sample_tree)
    results = window.results
    root = results.tree_model.root
    code = next(child for child in root.children if child.name == "code")
    results.select_node(code)
    (sample_tree / "photos" / "new.mov").write_bytes(b"v" * 700)
    photos = next(child for child in root.children if child.name == "photos")
    window.rescan_folder(photos)
    _wait(qapp, lambda: any(node.name == "new.mov" for node in results.largest_model.rows()), timeout=15)
    fresh = next(child for child in root.children if child.name == "photos")
    assert fresh is not photos and fresh.size == 950
    assert root.size == 1700 and root.file_count == 7
    assert results.largest_model.rows()[0].name == "new.mov"
    assert any(stat.extension == ".mov" for stat in results.types_model.rows())
    assert results.selected_node() is code, "the selection outside the rescanned folder stays"
    assert "Rescanned photos: 250 B → 950 B" in window.statusBar().currentMessage()
    assert results.tree_model.index(0, 0).data() == str(sample_tree)

