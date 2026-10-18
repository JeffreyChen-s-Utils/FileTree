"""Scan feedback and adaptive navigation retain coverage, selection and source-operation guards."""

import dataclasses

from PySide6.QtCore import QCoreApplication, QDir, QEvent, Qt
from PySide6.QtGui import QColor, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QPushButton, QStyleOptionViewItem, QTableView
import pytest

from test_gui import _wait, window as window  # noqa: PLC0414 - shared pytest fixture
from je_file_tree.core.formatting import format_size
from je_file_tree.core.scanner import ScanProgress, scan
from je_file_tree.gui.bin_labels import bin_key
from je_file_tree.gui import i18n
from je_file_tree.gui.app import create_window
from je_file_tree.gui.delegates import PathTailDelegate, bar_alpha
from je_file_tree.gui.empty_hint import EmptyHint
from je_file_tree.gui.main_window import RESULTS_PAGE
from je_file_tree.gui.results_view import CHANGES_TAB, CHART_TAB, LARGEST_TAB, PROBLEMS_TAB, SEARCH_TAB
from je_file_tree.gui.result_overview import ResultOverview
from je_file_tree.gui.scan_bar import ScanBar
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.themes import theme_controller
from je_file_tree.gui.tree_model import SIZE
from je_file_tree.gui.welcome import DriveSnapshot


def test_result_legends_do_not_insert_invisible_font_fallback_controls(window, sample_tree):
    results = window.results
    results.show_outcome(analyse(scan(sample_tree)))
    assert all("\u2060" not in label.text() for label in results.findChildren(QLabel))


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
    assert navigation.list.isHidden()
    assert not navigation.combo.isHidden()
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
        assert bar._feedback.text() != before
        assert '4.0 s' in bar._feedback.text()
        assert bar._current.full_text() == path
        assert bar._current.toolTip() == path
        assert bar._current.textFormat() == Qt.TextFormat.PlainText
        bar._pause.click()
        assert bar._busy.maximum() == 1
        assert bar._stop.isEnabled()
        bar.analysing()
        assert bar._busy.maximum() == 0
        assert not bar._pause.isEnabled()
        assert bar._stop.isEnabled()
        bar.stopping()
        assert i18n.tr("overview_scan_stopping") in bar._feedback.text()
        assert not bar._stop.isEnabled()
        bar.hide()
        assert not bar._clock.isActive()
    finally:
        bar.close()
        bar.deleteLater()


def test_home_scrolls_many_cached_drives_and_preserves_literal_recent_paths(window, qapp, monkeypatch):
    monkeypatch.setattr("je_file_tree.gui.welcome.drives", lambda: [])
    page = window.welcome
    _wait(qapp, lambda: not page._drive_timer.isActive() and page._drive_worker is None)
    page.drive_rows = tuple(DriveSnapshot(f"/owned/{index}", f"Drive {index}", 1000, 400) for index in range(24))
    page.set_recent(["/owned/R&D/" + "folder/" * 50])
    page.retranslate()
    window.resize(860, 600)
    window.show()
    _wait(qapp, lambda: page.scroll.verticalScrollBar().maximum() > 0)
    assert page._tip.height() >= page._tip.heightForWidth(page._tip.width())
    button = page._recent_box.itemAt(0).widget()
    assert isinstance(button, QPushButton)
    assert 'R&&D' in button.text()
    requested = []
    page.scan_requested.connect(requested.append)
    button.click()
    assert requested == page._recent


def test_first_result_display_preserves_the_saved_tree_analysis_split(window, qapp, sample_tree):
    outcome = analyse(scan(sample_tree))
    window.resize(1840, 900)
    window.results.show_outcome(outcome)
    window.pages.setCurrentIndex(RESULTS_PAGE)
    window.show()
    _wait(qapp, lambda: window.results._splitter_initialized)
    window.results.splitter.setSizes([1000, 650])
    qapp.processEvents()
    before = window.results.splitter.sizes()
    window.results.splitter.setChildrenCollapsible(True)  # old saved layouts allowed collapsing either pane
    window.settings.setValue("geometry", window.saveGeometry())
    window.settings.setValue("splitter", window.results.splitter.saveState())
    restored = create_window(window.settings)
    try:
        restored.resize(window.size())  # geometry restoration may clamp to the platform's virtual screen
        restored.results.show_outcome(outcome)
        restored.pages.setCurrentIndex(RESULTS_PAGE)
        restored.show()
        _wait(qapp, lambda: restored.results._splitter_initialized)
        after = restored.results.splitter.sizes()
        assert after[0] / sum(after) == pytest.approx(before[0] / sum(before), abs=.01)
        assert not restored.results.splitter.childrenCollapsible()
        restored.results.hide()
        restored.results.show()
        qapp.processEvents()
        assert restored.results.splitter.sizes() == after
    finally:
        restored.close()
        _wait(qapp, lambda: restored._close_ready)
        restored.deleteLater()


def test_explicit_path_scan_button_and_enter_respect_empty_input_and_review_guard(window, monkeypatch):
    requested = []
    monkeypatch.setattr(window, "start_scan", requested.append)
    window.path_edit.setText("   ")
    window.path_edit.returnPressed.emit()
    assert not window._scan_path.isEnabled()
    assert not requested
    window.path_edit.setText("/owned/folder")
    window.path_edit.returnPressed.emit()
    assert requested == ["/owned/folder"]
    monkeypatch.setattr(type(window), "operation_busy", property(lambda _self: True))
    window._update_path_button()
    window.path_edit.returnPressed.emit()
    assert not window._scan_path.isEnabled()
    assert requested == ['/owned/folder']


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


def test_folder_columns_keep_the_nearest_folders_when_elided(window, sample_tree):
    results = window.results
    results.show_outcome(analyse(scan(sample_tree)))
    views = [(results.largest_table, 2), (results.search_table, 2), (results.type_locations_table, 0),
             (results.cleanup.view, 2), (results.duplicates.view, 2)]
    for view, column in views:
        delegate = view.itemDelegateForColumn(column)
        assert isinstance(delegate, PathTailDelegate), view
        option = QStyleOptionViewItem()
        delegate.initStyleOption(option, view.model().index(0, column))
        assert option.textElideMode == Qt.TextElideMode.ElideLeft
    assert results.largest_table.textElideMode() == Qt.TextElideMode.ElideMiddle  # names keep extensions


def test_share_bars_are_stronger_on_dark_surfaces():
    assert bar_alpha(QColor("#20242a")) > bar_alpha(QColor("#ffffff"))
    assert bar_alpha(QColor("#ffffff")) == 110


def test_chart_breadcrumbs_show_the_pane_background(window):
    crumbs = window.results.breadcrumbs
    assert not crumbs._container.autoFillBackground()
    assert not crumbs._scroll.viewport().autoFillBackground()


def test_drive_rows_show_native_roots_fill_and_nearly_full_warning(window, qapp, monkeypatch):
    monkeypatch.setattr("je_file_tree.gui.welcome.drives", lambda: [])
    page = window.welcome
    _wait(qapp, lambda: not page._drive_timer.isActive() and page._drive_worker is None)
    # Owned, nonexistent roots: the rows are rendered from snapshots and no drive is ever scanned.
    page.drive_rows = (DriveSnapshot("Q:/filetree-owned/", "System", 1000, 50),
                       DriveSnapshot("R:/filetree-owned/", "", 1000, 600))
    page.retranslate()
    full, roomy = page.drive_cards
    full_button, full_bar, roomy_bar = full.button, full.bar, roomy.bar
    assert full.property("role") == "card" and page._bin_labels[bin_key("Q:/filetree-owned/")][1] is full.bin_label
    assert full_button.isFlat() and full_button.font().bold()  # the card's title, still a keyboard-focusable button
    assert page._drives.indexOf(roomy) == 1 and page._drives.getItemPosition(1)[:2] == (0, 1)  # two cards per row
    shown = QDir.toNativeSeparators("Q:/filetree-owned/")
    assert full_button.text() == f"System  ({shown})"
    assert full_bar.toolTip() == i18n.tr("welcome_drive_used", percent="95.0 %")
    assert full_bar.palette().color(QPalette.ColorRole.Highlight) == QColor("#d13438")
    assert roomy_bar.palette().color(QPalette.ColorRole.Highlight) != QColor("#d13438")
    requested = []
    page.scan_requested.disconnect()  # the window would start a real scan; record the request only
    page.scan_requested.connect(requested.append)
    full_button.click()
    assert requested == ["Q:/filetree-owned/"]  # the scan keeps the native root Qt reported
    assert window._worker is None and window._pending_scan is None  # nothing was scanned
    page.set_unit("KB")
    free = page.drive_cards[0].free
    assert free.text() == i18n.tr("welcome_drive_free", free=format_size(50, "KB"), total=format_size(1000, "KB"))
    assert page.scan_all.minimumHeight() == page._choose.minimumHeight()


def test_empty_lists_explain_themselves_without_claiming_unfinished_coverage(window, qapp, sample_tree):
    results = window.results
    problems, largest = results._empty_hints
    results.begin_scan()
    assert problems.label.isHidden() and largest.label.isHidden()  # nothing to claim while scanning
    outcome = analyse(scan(sample_tree))
    results.show_outcome(outcome)
    assert not problems.label.isHidden() and problems.label.text() == i18n.tr("problems_none")
    assert largest.label.isHidden()  # the list has rows
    results._largest_filter.setText("no-such-name-anywhere")
    qapp.processEvents()
    assert largest.label.text() == i18n.tr("search_none") and not largest.label.isHidden()
    assert largest.label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    results._largest_filter.clear()
    qapp.processEvents()
    assert largest.label.isHidden()
    results.show_outcome(dataclasses.replace(outcome, partial=True))
    assert problems.label.isHidden()  # a stopped scan did not read everything
    outcome.result.errors.append((str(sample_tree / "unreadable"), "Access denied"))
    results.show_outcome(outcome)
    assert problems.label.isHidden()
    i18n.set_language("zh-TW")
    try:
        results.show_outcome(dataclasses.replace(outcome, result=dataclasses.replace(outcome.result, errors=[])))
        window.retranslate()
        assert problems.label.text() == i18n.tr("problems_none")
    finally:
        i18n.set_language("en")


def test_empty_hint_survives_its_view_being_destroyed(qapp):
    model = QStandardItemModel()
    view = QTableView()
    view.setModel(model)
    hint = EmptyHint(view, lambda: "empty")
    view.resize(240, 120)
    view.show()
    qapp.processEvents()
    assert not hint.label.isHidden()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)  # raised from eventFilter before
    model.appendRow(QStandardItem("after"))  # a model outliving the view no longer reaches the hint


def test_scan_state_chip_takes_a_tone_per_state(window, qapp, sample_tree):
    overview = window.results.overview
    assert overview.state.property("role") == "chip"
    assert window.results.capacity.summary.property("role") == "caption"
    for state, tone in (("complete", "success"), ("partial", "caution"), ("live", "accent"), ("empty", "")):
        overview.show_totals(None, state)
        assert overview.state.property("tone") == tone, state
