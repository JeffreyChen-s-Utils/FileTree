"""Custom ranges retain exact boundaries and reject invalid drafts and saved values."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QTableView

from je_file_tree.core.node import Node
from je_file_tree.core.search import Query, SearchResult, search
from je_file_tree.gui import search_ranges
from je_file_tree.gui.i18n import current_language, set_language, tr
from je_file_tree.gui.search_filters import SIZE_STEPS, SearchFilters
from je_file_tree.gui.search_panel import SearchPanel
from je_file_tree.gui.search_ranges import MAX_BYTES, SearchRangeDialog, calendar_bounds, exact_bytes
from je_file_tree.gui.tables import LargestFilesModel


@pytest.fixture
def make_panel(qapp):
    panels = []
    def create():
        panel = SearchPanel(QTableView(), LargestFilesModel())
        panels.append(panel)
        return panel
    yield create
    for panel in panels:
        panel.stop(wait=True)
        panel.deleteLater()
        QCoreApplication.sendPostedEvents(panel, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize(('text', 'unit', 'expected'), [
    ('', 'B', None), ('0', 'B', 0), ('1.5', 'KiB', 1536), ('4.125', 'GiB', 4429185024),
    (str(MAX_BYTES), 'B', MAX_BYTES), ('0.0009765625', 'KiB', 1),
])
def test_exact_size(text, unit, expected):
    assert exact_bytes(text, unit) == expected


@pytest.mark.parametrize('text', ['-1', 'NaN', 'Infinity', '0.1', str(MAX_BYTES + 1),
                                       '1e999999999', '1e-999999999', 'bad', '1' * 129])
def test_invalid_exact_size(text):
    with pytest.raises(ValueError):
        exact_bytes(text, 'B')


def test_dates_and_core_edges():
    since, before = calendar_bounds('2026-10-20', '2026-10-20')
    assert since == datetime(2026, 10, 20).timestamp()
    assert before == datetime(2026, 10, 21).timestamp()
    root = Node('root', True, children=[Node(str(n), False, size=1 << 34, modified=n)
                for n in (since - 1, since, before - 0.001, before, 0, float('inf'), float('nan'))])
    result = search(root, Query(min_size=1 << 34, max_size=1 << 34,
                               modified_since=since, modified_before=before))
    assert result is not None and result.count == 2
    assert search(root, Query(min_size=1 << 34)).count == 7
    assert search(root, Query(unchanged_for=0), now=before).count == 4
    assert search(root, Query(changed_within=before), now=before).count == 4
    assert search(Node('root', True, children=[Node('empty', False)]), Query(max_size=0)).count == 1


@pytest.mark.parametrize(('start', 'through'), [('2026-02-30', ''), ('2026-10-22', '2026-10-20'),
                                               ('', '9999-12-31'), (True, ''), ('20261020', '')])
def test_invalid_dates(start, through):
    with pytest.raises(ValueError):
        calendar_bounds(start, through)


@pytest.mark.parametrize('offset', [-4, -6])
def test_calendar_end_uses_next_midnight_across_offset_change(monkeypatch, offset):
    class LocalCalendar:
        @staticmethod
        def combine(day, clock):
            hours = -5 if day.day == 8 else offset
            return datetime.combine(day, clock, timezone(timedelta(hours=hours)))
    monkeypatch.setattr(search_ranges, 'datetime', LocalCalendar)
    since, before = calendar_bounds('2026-03-08', '2026-03-08')
    assert before - since == (24 - (offset + 5)) * 3600


def test_saved_roundtrip_retranslation_and_bounded_custom_choices(qapp):
    filters = SearchFilters()
    state = {'min_size': 0, 'max_size': 4429185024, 'changed': 'custom', 'category': None,
             'kind': 'files', 'date_start': '2026-10-20', 'date_through': '2026-10-20'}
    filters.apply(state)
    again = SearchFilters()
    again.apply(json.loads(json.dumps(filters.state())))
    language = current_language()
    try:
        for code in ('en', 'zh-TW', 'zh-CN', 'ja', 'ko'):
            set_language(code)
            again.retranslate()
            assert again.state() == state
            assert again.conditions()['changed_within'] is None
    finally:
        set_language(language)
    for minimum in (123, 456, 789):
        again.apply({'min_size': minimum})
        assert again.min_size.currentData() == minimum
        assert again.min_size.count() == len(SIZE_STEPS) + 2
    again.apply({})
    assert again.state() == {'min_size': None, 'max_size': None, 'changed': 'any',
                             'category': None, 'kind': 'any'}


def test_dialog_drafts_cancel_invalid_and_accept(qapp, monkeypatch):
    filters = SearchFilters()
    filters.apply({'min_size': 123, 'changed': 'week'})
    original = filters.state()
    def cancel(dialog):
        dialog.minimum.setText('999')
        dialog.reject()
        return dialog.result()
    monkeypatch.setattr(SearchRangeDialog, 'exec', cancel)
    filters.custom.click()
    assert filters.state() == original
    dialog = SearchRangeDialog(original)
    dialog.minimum.setText('2')
    dialog.maximum.setText('1')
    dialog.accept()
    assert dialog.values is None and dialog.error.text()
    assert filters.state() == original
    dialog.minimum.setText('1.5')
    dialog.min_unit.setCurrentText('KiB')
    dialog.maximum.clear()
    dialog.start.setText('2026-10-20')
    dialog.through.setText('2026-10-20')
    dialog.accept()
    assert dialog.values['min_size'] == 1536
    assert dialog.result() == SearchRangeDialog.DialogCode.Accepted


@pytest.mark.parametrize('state', [{'min_size': True}, {'min_size': float('nan')}, {'max_size': []},
                                  {'min_size': MAX_BYTES + 1}, {'min_size': 1 << 100},
                                  {'max_size': -1}, {'min_size': '12'},
                                  {'min_size': 20, 'max_size': 10}, {'changed': 'custom'},
                                  {'changed': 'custom', 'date_start': 'wrong'},
                                  {'changed': 'custom', 'date_start': []}])
def test_invalid_saved_search_clears_results_and_refuses_save(qapp, state, make_panel):
    panel = make_panel()
    root = Node('root', True, children=[Node('hit', False, size=10)])
    panel.set_root(root)
    panel.filters.apply({'min_size': 0})
    deadline = time.monotonic() + 5
    while panel.busy and time.monotonic() < deadline:
        qapp.processEvents()
    assert panel.model.rowCount() == 1
    panel.rerun()
    old_worker = panel._current
    assert panel.model.rowCount() == 0
    panel.set_saved({'broken': state})
    panel.saved.setCurrentIndex(panel.saved.findData('broken'))
    panel._load_saved()
    assert not panel.busy and panel.model.rowCount() == 0
    assert panel.summary.text() == tr('search_range_invalid')
    assert not panel._save_button.isEnabled()
    panel._found(old_worker, SearchResult(root.children, 1, 10))
    assert panel.model.rowCount() == 0
    panel.save('must not save')
    assert panel.saved.findData('must not save') == -1
    panel.filters.apply({'max_size': 0})
    assert panel._save_button.isEnabled()


def test_selecting_empty_custom_mode_is_invalid(qapp):
    filters = SearchFilters()
    filters.apply({'changed': 'week'})
    filters.changed_when.setCurrentIndex(filters.changed_when.findData('custom'))
    with pytest.raises(ValueError):
        filters.conditions()


def test_custom_saved_search_restarts_with_exact_bounds(make_panel):
    first = make_panel()
    first.filters.apply({'min_size': 0, 'max_size': 4429185024, 'changed': 'custom',
                         'date_start': '2026-10-20', 'date_through': '2026-10-20'})
    first.box.setText('*.bin')
    saved = []
    first.saved_changed.connect(saved.append)
    first.save('Exact')
    restarted = make_panel()
    restarted.set_saved(json.loads(json.dumps(saved[0])))
    restarted.saved.setCurrentIndex(restarted.saved.findData('Exact'))
    restarted._load_saved()
    assert restarted.query() == first.query()
    assert restarted.filters.state() == first.filters.state()


def test_one_sided_dates_and_size_overflow():
    assert calendar_bounds('2026-10-20', '') == (datetime(2026, 10, 20).timestamp(), None)
    assert calendar_bounds('', '2026-10-20') == (None, datetime(2026, 10, 21).timestamp())
    with pytest.raises(ValueError):
        exact_bytes(str(MAX_BYTES), 'TiB')


def test_window_settings_reopen_keeps_custom_search(qapp, tmp_path):
    from PySide6.QtCore import QSettings
    from je_file_tree.gui.app import create_window
    from je_file_tree.gui.qt_translation import apply_qt_translation

    path = str(tmp_path / 'ranges.ini')
    settings = QSettings(path, QSettings.Format.IniFormat)
    settings.setValue('language', 'en')
    first = create_window(settings)
    query = first.results.search
    query.filters.apply({'min_size': 0, 'max_size': 4429185024, 'changed': 'custom',
                         'date_start': '2026-10-20', 'date_through': '2026-10-20'})
    query.box.setText('*.bin')
    expected = query.query()
    query.save('Stored ranges')
    settings.sync()
    first.close()
    deadline = time.monotonic() + 5
    while not first._close_ready and time.monotonic() < deadline:
        qapp.processEvents()
    assert first._close_ready
    first.deleteLater()
    restarted = create_window(QSettings(path, QSettings.Format.IniFormat))
    try:
        restored = restarted.results.search
        restored.saved.setCurrentIndex(restored.saved.findData('Stored ranges'))
        restored._load_saved()
        assert restored.query() == expected
        set_language('zh-TW')
        restored.retranslate()
        assert restored.query() == expected
    finally:
        restarted.close()
        deadline = time.monotonic() + 5
        while not restarted._close_ready and time.monotonic() < deadline:
            qapp.processEvents()
        assert restarted._close_ready
        restarted.deleteLater()
        set_language('en')
        apply_qt_translation('en')


def test_accepting_blank_dates_clears_relative_preset(qapp, monkeypatch):
    filters = SearchFilters()
    filters.apply({'changed': 'week'})
    def accept(dialog):
        dialog.minimum.setText('1.5')
        dialog.min_unit.setCurrentText('KiB')
        dialog.accept()
        return dialog.result()
    monkeypatch.setattr(SearchRangeDialog, 'exec', accept)
    filters.custom.click()
    assert filters.state()['changed'] == 'any'
    assert filters.conditions()['changed_within'] is None
    assert filters.conditions()['min_size'] == 1536
