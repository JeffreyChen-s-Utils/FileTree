"""The window and its models, on Qt's offscreen platform."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSettings, Qt, QUrl
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from file_tree.core.analysis import CATEGORIES
from file_tree.core.node import Node
from file_tree.core import scanner
from file_tree.core.scanner import ScanCancelledError, scan
from file_tree.gui import file_actions, i18n, scan_worker
from file_tree.gui.app import create_window
from file_tree.gui.help_dialog import HelpDialog
from file_tree.gui.main_window import RESULTS_PAGE, WELCOME_PAGE, MainWindow, _dropped_folder
from file_tree.gui.qt_translation import apply_qt_translation
from file_tree.gui.scan_worker import analyse
from file_tree.gui.tables import SORT_ROLE, FileTypesModel, LargestFilesModel
from file_tree.gui.tree_model import NAME, NODE_ROLE, SHARE_ROLE, SIZE, FolderTreeModel
from file_tree.gui.treemap_widget import CATEGORY_COLOURS, TreemapWidget


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


def _slow_reads(monkeypatch: pytest.MonkeyPatch, delay: float) -> None:
    real = scanner._read_folder

    def slow(*args: object):
        time.sleep(delay)
        return real(*args)

    monkeypatch.setattr(scanner, "_read_folder", slow)


def test_the_tree_shows_and_grows_while_the_scan_runs(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    _slow_reads(monkeypatch, 0.15)
    window.start_scan(str(sample_tree))
    model = window.results.tree_model
    _wait(qapp, lambda: model.root is not None and model.root.file_count > 0)
    assert model.live and window.results.outcome is None
    assert "so far" in window.results.summary.text()
    window.results.refresh_live()
    top = model.index(0, 0)
    assert model.rowCount(top) == len(model.root.children) > 0
    window.results.tree.expand(top)
    _wait(qapp, lambda: window.results.outcome is not None, timeout=15)
    assert not model.live
    assert window.results.tree.isExpanded(model.index(0, 0)), "what was opened during the scan stays open"
    assert "1,000 B" in window.results.summary.text()
    assert not window.results.scan_bar.isVisibleTo(window.results)


def test_stopping_keeps_what_was_read(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    _slow_reads(monkeypatch, 0.2)
    window.start_scan(str(sample_tree))
    model = window.results.tree_model
    _wait(qapp, lambda: model.root is not None and model.root.file_count > 0)
    window.stop_scan()
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
    window.export_results("folders")
    assert target.read_text(encoding="utf-8-sig").startswith("path,size_bytes")
    assert "4 rows" in window.statusBar().currentMessage()


def test_move_to_trash_asks_then_updates_the_results(window: MainWindow, qapp: QApplication, sample_tree: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    _scanned(window, qapp, sample_tree)
    root = window.results.tree_model.root
    assert root is not None
    big = root.children[0]
    trashed: list[str] = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    window.move_to_trash(big)
    assert root.size == 1000
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "move_to_trash", lambda path: trashed.append(path) or True)
    window.move_to_trash(big)
    assert trashed == [str(sample_tree / "big.bin")]
    assert root.size == 500
    assert [node.name for node in window.results.largest_model.rows()][0] == "a.jpg"
    assert all(stat.extension != ".bin" for stat in window.results.types_model.rows())
    assert "500 B" in window.statusBar().currentMessage()


def test_dropped_urls_and_the_help_dialog(window: MainWindow, sample_tree: Path) -> None:
    urls = [QUrl.fromLocalFile(str(sample_tree / "big.bin")), QUrl.fromLocalFile(str(sample_tree / "code"))]
    assert _dropped_folder(urls) == str(sample_tree / "code")
    assert _dropped_folder([QUrl("https://example.com/")]) is None
    dialog = HelpDialog(window)
    assert "FileTree" in dialog.browser.toPlainText()
    dialog.deleteLater()


def test_explorer_command_always_quotes_the_path() -> None:
    assert file_actions.explorer_command("C:\\trip,day1\\a.jpg") == 'explorer /select,"C:\\trip,day1\\a.jpg"'
