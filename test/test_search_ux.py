"""Search condition actions and calendar drafts preserve the active query contract."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QDate, QEvent, QLocale, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QDialogButtonBox, QTableView

from je_file_tree.core.node import Node
from je_file_tree.core.search import SearchResult
from je_file_tree.gui.i18n import current_language, set_language, tr
from je_file_tree.gui.search_conditions import descriptions
from je_file_tree.gui.search_panel import SearchPanel
from je_file_tree.gui.optional_date import CalendarDialog
from je_file_tree.gui.search_ranges import MAX_BYTES, SearchRangeDialog
from je_file_tree.gui.tables import LargestFilesModel


@pytest.fixture
def panel(qapp):
    table, model = QTableView(), LargestFilesModel()
    table.setModel(model)
    widget = SearchPanel(table, model)
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    widget.resize(520, 700)
    widget.show()
    widget.set_root(Node('C:/A<&', True, children=[Node('report.txt', False, size=4096)]))
    yield widget
    widget.stop(wait=True)
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)


def test_individual_removal_and_clear_preserve_saved_and_root(panel, qapp):
    state = {'min_size': 123, 'max_size': 456, 'changed': 'custom',
             'date_start': '2026-10-20', 'date_through': '2026-10-20',
             'kind': 'files', 'category': 'documents'}
    panel.box.setText('literal<&')
    panel.filters.apply(state)
    panel.save('keep')
    saved, root = dict(panel._searches), panel._root
    changes = QSignalSpy(panel.filters.changed)
    for key in ('min_size', 'max_size', 'changed', 'category', 'kind'):
        previous = changes.count()
        panel.conditions_view.buttons[key].click()
        assert changes.count() == previous + 1
        assert key not in descriptions(panel.box.text(), panel.filters.state(), 'B')
        if key == 'min_size':
            assert panel.filters.state()['max_size'] == 456
    panel.filters.apply(state)
    stale = panel._current
    panel.conditions_view.reset.click()
    assert panel.box.text() == '' and not descriptions('', panel.filters.state(), 'B')
    assert panel._searches == saved and panel._root is root
    panel._found(stale, SearchResult([root], 1, 99))
    assert panel.model.rowCount() == 0 and panel._result is None
    assert 'C:/A<&' in panel.conditions_view.scope.text()


@pytest.mark.parametrize('bad', [True, [], MAX_BYTES + 1, -1])
def test_invalid_saved_size_reports_before_summary(panel, bad):
    panel.set_saved({'bad': {'min_size': bad}})
    panel.saved.setCurrentIndex(1)
    panel._load_saved()
    assert panel._validation_error and panel._current is None
    assert tr('search_range_invalid') in panel.conditions_view.labels['min_size'].text()
    panel.save('must not save')
    assert 'must not save' not in panel._searches


def test_invalid_saved_date_and_virtual_scope(panel):
    panel.set_root(Node('', True))
    panel.filters.apply({'changed': 'custom', 'date_start': []})
    assert panel._validation_error
    assert panel.conditions_view.scope.text() == tr('search_scope_multi')
    assert tr('search_range_invalid') in panel.conditions_view.labels['changed'].text()


def test_translation_and_unit_keep_authoritative_state(panel):
    language = current_language()
    state = {'min_size': 1536, 'max_size': 9999, 'changed': 'custom',
             'date_start': '2026-10-20', 'date_through': '', 'kind': 'files', 'category': None}
    panel.filters.apply(state)
    panel.box.setText('<report&>')
    try:
        for code in ('en', 'zh-TW', 'zh-CN', 'ja', 'ko'):
            set_language(code)
            for unit in ('B', 'KB', 'auto'):
                panel.model.unit = unit
                panel.retranslate()
                assert panel.filters.state() == state
                assert '1,536 B' in panel.conditions_view.labels['min_size'].text()
                label = panel.conditions_view.labels['text']
                assert '<report&>' in label.text() and label.textFormat() == Qt.TextFormat.PlainText
    finally:
        set_language(language)


def test_calendar_keyboard_cancel_accept_clear_and_parent_draft(qapp):
    dialog = SearchRangeDialog({'date_start': '', 'date_through': ''})
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    dialog.show()
    date = dialog.start
    QTest.keyClick(date.choose_button, Qt.Key.Key_Space)
    qapp.processEvents()
    calendar = date.dialog
    assert calendar.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    assert date.text() == ''
    QTest.keyClick(calendar, Qt.Key.Key_Escape)
    assert date.text() == '' and date.dialog is None
    date.setText('invalid draft')
    date.choose_button.click()
    calendar = date.dialog
    calendar.calendar.setSelectedDate(QDate(2026, 10, 20))
    QTest.keyClick(calendar.calendar.findChild(QTableView), Qt.Key.Key_Right)
    QTest.keyClick(calendar.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.Key.Key_Space)
    assert date.text() == '2026-10-21' and dialog.values is None
    QTest.keyClick(date.clear_button, Qt.Key.Key_Space)
    assert date.text() == ''
    dialog.reject()
    assert dialog.values is None


def test_invalid_date_focus_and_open_boundary(qapp):
    dialog = SearchRangeDialog({})
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    dialog.show()
    dialog.start.setText('2026-02-30')
    dialog.accept()
    assert dialog.values is None and dialog.field_errors[dialog.start].isVisible()
    assert dialog.focusWidget() is dialog.start.edit
    dialog.start.clear()
    dialog.through.setText('2026-10-20')
    dialog.accept()
    assert dialog.values['date_start'] == '' and dialog.values['date_through'] == '2026-10-20'


def test_typing_invalidates_old_worker_before_debounce(panel):
    panel.box.setText('report')
    panel.rerun()
    worker = panel._current
    panel.box.setText('next<&>')
    panel._found(worker, SearchResult([panel._root], 1, 1))
    assert panel._current is None and panel.model.rowCount() == 0
    assert panel._timer.isActive()
    assert 'next&lt;&amp;&gt;' in panel.conditions_view.labels['text'].toolTip()
    for widget in (panel.conditions_view.labels['text'], panel.conditions_view.scope):
        document = QTextDocument()
        document.setHtml(widget.toolTip())
        assert document.toPlainText() == widget.text()


def test_calendar_uses_application_language_not_system(qapp):
    original, language = QLocale(), current_language()
    parent = QTableView()
    try:
        QLocale.setDefault(QLocale('de_DE'))
        for code in ('en', 'zh-TW', 'zh-CN', 'ja', 'ko'):
            set_language(code)
            dialog = CalendarDialog('', parent)
            expected = QLocale(code.replace('-', '_'))
            assert dialog.calendar.locale().name() == expected.name()
            assert dialog.calendar.locale().monthName(10) == expected.monthName(10)
            assert dialog.calendar.locale().dayName(1) == expected.dayName(1)
            dialog.deleteLater()
    finally:
        QLocale.setDefault(original)
        set_language(language)
