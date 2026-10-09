"""Scan feedback and adaptive navigation retain coverage, selection and source-operation guards."""

import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
import pytest

from test_gui import _wait, window as window  # noqa: PLC0414 - shared pytest fixture
from je_file_tree.core.formatting import format_size
from je_file_tree.core.scanner import ScanProgress, scan
from je_file_tree.gui import i18n
from je_file_tree.gui.main_window import RESULTS_PAGE
from je_file_tree.gui.results_view import CHANGES_TAB, CHART_TAB, LARGEST_TAB, PROBLEMS_TAB, SEARCH_TAB
from je_file_tree.gui.result_overview import ResultOverview
from je_file_tree.gui.scan_bar import ScanBar
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.themes import theme_controller
from je_file_tree.gui.tree_model import SIZE
from je_file_tree.gui.welcome import DriveSnapshot


@pytest.mark.parametrize("language", i18n.LANGUAGES)
def test_overview_distinguishes_complete_stopped_and_unreadable_scans(window, sample_tree, language):
    i18n.set_language(language)
    window.retranslate()
    outcome = analyse(scan(sample_tree))
    results = window.results
    results.show_outcome(outcome)
    overview = results.overview
    assert overview.state.text() == i18n.tr("overview_complete")
    expected = ["1,000 B", format_size(outcome.result.root.allocated), "6", "3"]
    assert [label.text() for label in overview.values] == expected
    results.set_unit("KB")
    assert overview.values[0].text() == format_size(1000, "KB")
    assert overview.values[0].accessibleName() == i18n.tr("overview_size")
    results.show_outcome(dataclasses.replace(outcome, partial=True))
    assert overview.state.text() == i18n.tr("overview_partial")
    outcome.result.errors.append((str(sample_tree / "unreadable"), "Access denied"))
    results.show_outcome(outcome)
    assert overview.state.text() == i18n.tr("overview_partial")
    assert not overview.problems.isHidden()
    overview.problems.click()
    assert results.tabs.currentIndex() == PROBLEMS_TAB
    assert results.navigation.list.currentRow() == PROBLEMS_TAB
    results.begin_scan()
    assert overview.state.text() == i18n.tr("overview_live")
    assert all(label.text() == "—" for label in overview.values)
    assert overview.problems.isHidden()
    results.end_scan()
    assert overview.state.text() == i18n.tr("overview_empty")


def test_sidebar_keyboard_compact_chooser_and_comparison_stay_in_sync(window, qapp, sample_tree):
    results = window.results
    window.resize(1240, 800)
    window.pages.setCurrentIndex(RESULTS_PAGE)
    results.show_outcome(analyse(scan(sample_tree)))
    window.show()
    _wait(qapp, lambda: not results.navigation.compact)
    navigation = results.navigation
    assert results.tabs.tabBar().isHidden()
    assert navigation.list.item(CHANGES_TAB).isHidden()
    assert navigation.combo.findData(CHANGES_TAB) == -1
    assert results.tabs.minimumSizeHint().width() < results.tabs.widget(SEARCH_TAB).minimumSizeHint().width()
    assert results.splitter.sizes()[0] >= results.tree.columnWidth(0) + results.tree.columnWidth(SIZE)
    QTest.keyClick(navigation.list, Qt.Key.Key_Down)
    assert results.tabs.currentIndex() == LARGEST_TAB
    assert results._scope_button.isVisibleTo(results)
    results.show_search()
    assert navigation.list.currentRow() == SEARCH_TAB
    assert results.search.box.hasFocus()
    results.tabs.setCurrentIndex(CHART_TAB)
    window.resize(860, 720)
    _wait(qapp, lambda: navigation.compact)
    assert navigation.list.isHidden() and not navigation.combo.isHidden()
    navigation.combo.setCurrentIndex(navigation.combo.findData(PROBLEMS_TAB))
    assert results.tabs.currentIndex() == PROBLEMS_TAB
    results._reveal_changes = True
    results._changes_shown(True)
    assert not navigation.list.item(CHANGES_TAB).isHidden()
    assert navigation.combo.currentData() == CHANGES_TAB
    results._changes_shown(False)
    assert navigation.combo.findData(CHANGES_TAB) == -1
    assert navigation.combo.currentData() == results.tabs.currentIndex()
    window.resize(1240, 800)
    _wait(qapp, lambda: not navigation.compact)
    assert navigation.list.currentRow() == results.tabs.currentIndex()


def test_scan_feedback_ticks_during_a_stalled_read_and_retains_the_full_plain_path(qapp, monkeypatch):
    now = [100.0]
    monkeypatch.setattr("je_file_tree.gui.scan_bar.time.monotonic", lambda: now[0])
    bar = ScanBar()
    try:
        bar.resize(800, 120)
        bar.start()
        assert bar._clock.isActive()
        path = "C:/" + "long <folder>&name/" * 12
        bar.show_progress(ScanProgress(6, 3, 1000, path))
        before = bar._feedback.text()
        now[0] = 104.0
        bar._clock.timeout.emit()
        assert bar._feedback.text() != before and "4.0 s" in bar._feedback.text()
        assert bar._current.full_text() == path and bar._current.toolTip() == path
        assert bar._current.textFormat() == Qt.TextFormat.PlainText
        bar._pause.click()
        assert bar._busy.maximum() == 1 and bar._stop.isEnabled()
        bar.analysing()
        assert bar._busy.maximum() == 0 and not bar._pause.isEnabled() and bar._stop.isEnabled()
        bar.stopping()
        assert i18n.tr("overview_scan_stopping") in bar._feedback.text()
        assert not bar._stop.isEnabled()
        bar.hide()
        assert not bar._clock.isActive()
    finally:
        bar.close()
        bar.deleteLater()


def test_home_scrolls_many_cached_drives_and_preserves_literal_recent_paths(window, qapp):
    page = window.welcome
    _wait(qapp, lambda: page._drive_worker is None)
    page.drive_rows = tuple(DriveSnapshot(f"/owned/{index}", f"Drive {index}", 1000, 400) for index in range(24))
    page.set_recent(["/owned/R&D/" + "folder/" * 50])
    page.retranslate()
    window.resize(860, 600)
    window.show()
    _wait(qapp, lambda: page.scroll.verticalScrollBar().maximum() > 0)
    assert page._tip.height() >= page._tip.heightForWidth(page._tip.width())
    button = page._recent_box.itemAt(0).widget()
    assert isinstance(button, QPushButton) and "R&&D" in button.text()
    requested = []
    page.scan_requested.connect(requested.append)
    button.click()
    assert requested == page._recent


def test_explicit_path_scan_button_and_enter_respect_empty_input_and_review_guard(window, monkeypatch):
    requested = []
    monkeypatch.setattr(window, "start_scan", requested.append)
    window.path_edit.setText("   ")
    window.path_edit.returnPressed.emit()
    assert not window._scan_path.isEnabled() and not requested
    window.path_edit.setText("/owned/folder")
    window.path_edit.returnPressed.emit()
    assert requested == ["/owned/folder"]
    monkeypatch.setattr(type(window), "operation_busy", property(lambda _self: True))
    window._update_path_button()
    window.path_edit.returnPressed.emit()
    assert not window._scan_path.isEnabled() and requested == ["/owned/folder"]


def test_narrow_overview_wraps_readable_values_without_losing_totals(qapp, sample_tree):
    overview = ResultOverview()
    try:
        overview.show_totals(scan(sample_tree).root, "complete")
        overview.resize(550, 220)
        overview.show()
        qapp.processEvents()
        before = [value.text() for value in overview.values]
        assert overview.cards[2].y() > overview.cards[0].y()
        assert overview.cards[1].x() > overview.cards[0].x()
        overview.resize(950, 220)
        qapp.processEvents()
        assert overview.cards[2].y() == overview.cards[0].y()
        assert [value.text() for value in overview.values] == before
    finally:
        overview.close()
        overview.deleteLater()


@pytest.mark.parametrize("theme", ["system", "light", "dark"])
def test_theme_switch_retains_overview_values_and_analysis_selection(window, qapp, sample_tree, theme):
    results = window.results
    results.show_outcome(analyse(scan(sample_tree)))
    results.tabs.setCurrentIndex(LARGEST_TAB)
    before = [value.text() for value in results.overview.values]
    controller = theme_controller()
    try:
        controller.apply(theme)
        qapp.processEvents()
        assert [value.text() for value in results.overview.values] == before
        assert results.navigation.list.currentRow() == LARGEST_TAB
        assert results.navigation.combo.currentData() == LARGEST_TAB
    finally:
        controller.apply("system")
