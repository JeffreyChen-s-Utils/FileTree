"""History navigation keeps captured scope, point identity and cancellation observable."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from test_gui import _wait
from je_file_tree.core.history import ScanHistory
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanOptions
from je_file_tree.core.snapshot import pack_snapshot
from je_file_tree.core.trends import HistoryTrend, TrendPoint, TrendQuery, UnknownReason
from je_file_tree.gui import history
from je_file_tree.gui.history import HistoryDialog
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.loaded_folder import LoadedFolderWorker, PAGE_SIZE


@pytest.fixture
def trend_dialog(qapp, tmp_path):
    parent = QWidget()
    parent.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    root = Node(str(tmp_path / 'unread-source'), True, size=2048, children=[], snapshot=pack_snapshot(tmp_path.stat()))
    child = Node('photos', True, size=1024, parent=root, children=[])
    root.children.append(child)
    store = ScanHistory(tmp_path / 'history')
    store.save(root, options=ScanOptions())
    dialog = HistoryDialog(store, root.path, 'KB', parent, loaded_root=root)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    dialog.show()
    _wait(qapp, lambda: not dialog._running)
    yield dialog
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    dialog.deleteLater()
    parent.deleteLater()


def result_for(dialog, points=None, **kwargs):
    """Use private retained metadata, with explicit identities for each observation."""
    entry = dialog.store.read(dialog.root).entries[0]
    if points is None:
        points = (TrendPoint(entry, 2048, None, None),
                  TrendPoint(replace(entry, path=entry.path.with_name('second')), None, None,
                             UnknownReason.MISSING, UnknownReason.INCOMPATIBLE),
                  TrendPoint(replace(entry, path=entry.path.with_name('third')), 2048, None,
                             None, UnknownReason.MISSING),
                  TrendPoint(replace(entry, path=entry.path.with_name('fourth')), 1024, -1024, None))
    return HistoryTrend(TrendQuery(dialog.root), points, (), kwargs.pop('net', None), len(points), 0,
                        kwargs.pop('truncated', False), **kwargs)


def test_same_timestamp_unknown_points_are_keyboard_reachable_and_table_synchronized(trend_dialog, qapp):
    dialog = trend_dialog
    result = result_for(dialog)
    dialog._show_trend(result)
    dialog.chart.setFocus()
    qapp.processEvents()
    assert dialog.focusWidget() is dialog.chart
    signals = []
    dialog.chart.point_selected.connect(signals.append)
    dialog.chart.set_selected_point(0)
    assert signals == []
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    assert signals == [1] and dialog.trend_view.currentRow() == 1
    assert tr('trend_size_reason', reason=tr('trend_reason_missing')) in dialog.point_details.toPlainText()
    assert tr('trend_change_reason', reason=tr('trend_reason_incompatible')) in dialog.point_details.toPlainText()
    unknown = dialog.chart._positions(result.points)[1]
    assert unknown.y() > dialog.chart._positions(result.points)[0].y()
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    assert dialog.chart.selected_point == 2 and dialog.trend_view.currentRow() == 2
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    assert dialog.chart.selected_point == 3 and dialog.trend_view.currentRow() == 3
    assert '−1.0 KB' in dialog.point_details.toPlainText() and '−1,024 B' in dialog.point_details.toPlainText()
    assert dialog.trend_view.item(3, 2).toolTip() == '−1,024 B'
    assert '−1,024 B' in dialog.trend_view.item(3, 2).data(Qt.ItemDataRole.AccessibleTextRole)
    dialog.trend_view.setFocus()
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Up)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Up)
    assert dialog.chart.selected_point == 1
    assert not dialog.compare_button.isEnabled()
    dialog.tabs.setCurrentWidget(dialog.view)
    dialog.view.setCurrentIndex(dialog.model.index(0, 0))
    assert dialog.compare_button.isEnabled()


@pytest.mark.parametrize('key, days', [('30', 29), ('90', 89)])
def test_preset_and_custom_dates_use_same_inclusive_query(trend_dialog, qapp, key, days):
    dialog = trend_dialog
    today = date.today()
    dialog.period.setCurrentIndex(dialog.period.findData(key))
    assert dialog.start_input.text() == (today - timedelta(days=days)).isoformat()
    assert dialog.end_input.text() == today.isoformat()
    dialog.apply_trend()
    query = dialog.worker.query
    assert query.start == dialog._midnight(today - timedelta(days=days))
    assert query.end == dialog._midnight(today + timedelta(days=1))
    _wait(qapp, lambda: not dialog._running)
    dialog.period.setCurrentIndex(dialog.period.findData('custom'))
    dialog.apply_trend()
    assert dialog.worker.query == query
    _wait(qapp, lambda: not dialog._running)
    dialog.start_input.clear()
    dialog.apply_trend()
    assert dialog.worker.query.start is None and dialog.worker.query.end == query.end
    _wait(qapp, lambda: not dialog._running)
    dialog.period.setCurrentIndex(dialog.period.findData('all'))
    assert not dialog.start_input.text() and not dialog.end_input.text()


def test_dst_midnights_are_independently_converted(trend_dialog, qapp, monkeypatch):
    def midnight(day):
        offset = -4 if day >= date(2026, 3, 9) else -5
        return datetime.combine(day, datetime.min.time(), timezone(timedelta(hours=offset)))
    monkeypatch.setattr(HistoryDialog, '_midnight', staticmethod(midnight))
    dialog = trend_dialog
    dialog.start_input.setText('2026-03-08')
    dialog.end_input.setText('2026-03-08')
    dialog.apply_trend()
    query = dialog.worker.query
    assert query.end.timestamp() - query.start.timestamp() == 23 * 3600
    _wait(qapp, lambda: not dialog._running)


@pytest.mark.parametrize('field,text', [('start_input', '2026-02-30'), ('end_input', 'oops'),
                                      ('folder_input', '../outside')])
def test_invalid_input_is_retained_focused_and_clears_selection(trend_dialog, qapp, field, text):
    dialog = trend_dialog
    dialog._show_trend(result_for(dialog))
    target = getattr(dialog, field)
    target.setText(text)
    dialog.apply_trend()
    qapp.processEvents()
    assert target.text() == text
    assert dialog.focusWidget() is getattr(target, 'edit', target)
    assert dialog.trend is None and dialog.chart.selected_point is None and not dialog.chart.points
    assert dialog.trend_view.rowCount() == 0 and not dialog.compare_button.isEnabled()


def test_reversed_period_focuses_end_and_preserves_bounds(trend_dialog, qapp):
    dialog = trend_dialog
    dialog.start_input.setText('2026-10-28')
    dialog.end_input.setText('2026-10-27')
    dialog.apply_trend()
    assert dialog.focusWidget() is dialog.end_input.edit
    assert tr('trend_date_order') in dialog.status.text()
    assert dialog.start_input.text() == '2026-10-28' and dialog.end_input.text() == '2026-10-27'


@pytest.mark.parametrize('points,reason,truncated', [(0, UnknownReason.INSUFFICIENT, False),
    (1, UnknownReason.INSUFFICIENT, False), (3, UnknownReason.TRUNCATED, True),
    (3, UnknownReason.INCOMPATIBLE, False)])
def test_empty_single_capped_and_incompatible_have_distinct_explanations(trend_dialog, points, reason, truncated):
    dialog = trend_dialog
    result = result_for(dialog)
    dialog._show_trend(replace(result, points=result.points[:points], net_reason=reason, truncated=truncated))
    assert (tr('history_empty') if not points else tr('trend_reason_' + reason.value)) in dialog.net_label.text()
    if points == 1:
        assert '2,048 B' in dialog.point_details.toPlainText()
        assert tr('trend_first_point') in dialog.point_details.toPlainText()
        assert tr('trend_size_reason', reason=tr('trend_unknown')) not in dialog.point_details.toPlainText()
    if truncated:
        assert tr('trend_capped') in dialog.status.text()


def test_zero_net_is_known_and_exact(trend_dialog):
    dialog = trend_dialog
    dialog._show_trend(result_for(dialog, net=0))
    assert '0.0 KB' in dialog.net_label.text()
    assert dialog.net_label.toolTip() == '0 B'


def test_loaded_folder_navigation_pages_without_walking_descendants_or_source(trend_dialog, qapp, monkeypatch):
    root = trend_dialog.loaded_root
    class NoDescendants:
        def __iter__(self):
            raise AssertionError('Descendants must not be enumerated')
    root.children = [Node(f'folder-{index:04}', True, parent=root, children=NoDescendants())
                     for index in reversed(range(PAGE_SIZE + 3))]
    root.children.append(Node('file', False, parent=root))
    root.children.append(Node('link', True, is_link=True, parent=root))
    monkeypatch.setattr(Node, 'iter_nodes', lambda _self: pytest.fail('Whole tree traversal'))
    trend_dialog.choose_folder()
    chooser = trend_dialog.folder_dialog
    _wait(qapp, lambda: bool(chooser.rows))
    assert chooser.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    assert len(chooser.rows) == PAGE_SIZE and chooser.rows[0].name == 'folder-0000'
    assert chooser.next.isEnabled()
    chooser.next.click()
    _wait(qapp, lambda: bool(chooser.rows))
    assert len(chooser.rows) == 3 and chooser.rows[0].name == 'folder-0200'
    chooser.reject()
    _wait(qapp, lambda: trend_dialog.folder_dialog is None)
    assert trend_dialog.folder_input.text() == '' and trend_dialog.trend.query.folder == ''


def test_accepted_folder_uses_ancestor_chain_and_root_return(trend_dialog, qapp):
    dialog = trend_dialog
    dialog.choose_folder()
    chooser = dialog.folder_dialog
    _wait(qapp, lambda: bool(chooser.rows))
    chooser.list.setFocus()
    QTest.keyClick(chooser.focusWidget(), Qt.Key.Key_Return)
    _wait(qapp, lambda: not chooser.worker.isRunning())
    assert not chooser._closed and chooser.isVisible()
    assert chooser.current.name == 'photos'
    chooser.choose()
    _wait(qapp, lambda: dialog.folder_dialog is None and not dialog._running)
    assert dialog.folder_input.text() == 'photos' and dialog.trend.query.folder == 'photos'
    assert dialog.full_path.text() == dialog.loaded_root.children[0].path
    dialog.return_to_root()
    _wait(qapp, lambda: not dialog._running)
    assert dialog.folder_input.text() == '' and dialog.trend.query.folder == ''


def test_initial_child_query_matches_full_path_and_retains_full_root_comparison(trend_dialog, qapp):
    parent = trend_dialog
    dialog = HistoryDialog(parent.store, parent.root, 'KB', parent, folder='photos', loaded_root=parent.loaded_root)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    dialog.show()
    compared = []
    dialog.compare_requested.connect(compared.append)
    try:
        _wait(qapp, lambda: not dialog._running)
        assert dialog.trend.query.folder == 'photos'
        assert dialog.full_path.text() == parent.loaded_root.children[0].path
        assert dialog.chart.points is dialog.trend.points
        assert dialog.chart.points[0].size == 1024
        assert dialog.model.rows()[0].size == 2048
        dialog.tabs.setCurrentWidget(dialog.view)
        dialog.view.setCurrentIndex(dialog.model.index(0, 0))
        dialog.compare_selected()
        _wait(qapp, lambda: bool(compared))
        assert compared[0].size == 2048 and compared[0].root == parent.root
    finally:
        dialog.reject()
        _wait(qapp, lambda: not dialog._finish_waiting)
        dialog.deleteLater()


def test_quick_folder_queries_ignore_late_reply_and_close_joins_navigation(trend_dialog, qapp, monkeypatch):
    dialog = trend_dialog
    entered, release = threading.Event(), threading.Event()
    old = result_for(dialog)
    def query(_store, request, *, cancel):
        if request.folder == 'photos':
            entered.set()
            assert release.wait(10)
        return replace(old, query=request)
    monkeypatch.setattr(history, 'query_trend', query)
    dialog.folder_input.setText('photos')
    dialog.apply_trend()
    _wait(qapp, entered.is_set)
    dialog.return_to_root()
    release.set()
    _wait(qapp, lambda: not dialog._running)
    assert dialog.trend.query.folder == ''
    entered.clear()
    def held(worker):
        entered.set()
        assert worker.cancel.wait(10)
    monkeypatch.setattr(LoadedFolderWorker, 'run', held)
    dialog.choose_folder()
    _wait(qapp, entered.is_set)
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    assert all(not worker.isRunning() for worker in dialog.findChildren(LoadedFolderWorker))


def test_history_read_does_not_wait_for_navigation_worker(trend_dialog, qapp, monkeypatch):
    entered = threading.Event()
    def held(worker):
        entered.set()
        assert worker.cancel.wait(10)
    monkeypatch.setattr(LoadedFolderWorker, 'run', held)
    dialog = trend_dialog
    dialog.choose_folder()
    _wait(qapp, entered.is_set)
    dialog.apply_trend()
    _wait(qapp, lambda: not dialog._running)
    assert dialog.trend is not None and dialog.folder_dialog.worker.isRunning()
    dialog.folder_dialog.reject()
    _wait(qapp, lambda: dialog.folder_dialog is None)
