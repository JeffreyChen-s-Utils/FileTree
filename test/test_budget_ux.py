"""Budget observations remain readable while exact edits survive presentation changes."""

from decimal import localcontext

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest

from je_file_tree.core.folder_budgets import BudgetBatch, BudgetObservation
from je_file_tree.core.formatting import format_size
from je_file_tree.gui.app import create_workspace
from je_file_tree.gui.folder_budget_dialog import FolderBudgetDialog
from je_file_tree.gui.folder_budget_store import FolderBudgetStore
from je_file_tree.gui.i18n import set_language, tr
from je_file_tree.gui.search_ranges import MAX_BYTES, editable_size, exact_bytes
from test_gui import _wait


@pytest.mark.parametrize('value', [0, 1, 1536, MAX_BYTES])
@pytest.mark.parametrize('unit', ['auto', 'B', 'KB', 'MB', 'GB', 'TB', 'PB'])
def test_limit_input_round_trips_without_decimal_context_or_display_rounding(value, unit):
    with localcontext() as context:
        context.prec = 2
        text, binary_unit = editable_size(value, unit)
        assert exact_bytes(text, binary_unit) == value
    assert 'e' not in text.lower()


def _dialog(tmp_path, qapp, *, unit='auto'):
    set_language('en')
    settings = QSettings(str(tmp_path / 'budget-ui.ini'), QSettings.Format.IniFormat)
    store = FolderBudgetStore(settings)
    dialog = FolderBudgetDialog(store, unit=unit)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    dialog.show()
    qapp.processEvents()
    return dialog, store


def _publish(store, amount, *, when=1_700_000_000.0, reason=None):
    ticket = store.ticket()
    rule = ticket.rules[0]
    observation = BudgetObservation(rule.identity, rule.version, ticket.sequence, when, amount, reason)
    store.publish(BudgetBatch((observation,)))


def test_arrow_selection_then_tab_reaches_editor_without_changing_rule(tmp_path, qapp):
    dialog, store = _dialog(tmp_path, qapp)
    store.put('first', str(tmp_path / 'first'), 1536)
    second = store.put('second', str(tmp_path / 'second'), 1537)
    dialog.table.setFocus()
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Down)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Down)
    assert dialog.selected_identity == second.identity
    before = dialog._input()
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
    assert dialog.focusWidget() is dialog.name
    assert dialog._input() == before
    QTest.keyClicks(dialog.focusWidget(), 'draft')
    draft = dialog._input()
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
    assert dialog.focusWidget() is dialog.path
    assert dialog._input() == draft
    assert dialog.selected_identity == second.identity
    assert store.rows[1].rule.name == 'second'
    dialog.reject()


def test_observation_units_exact_values_and_old_limit_are_distinct(tmp_path, qapp):
    dialog, store = _dialog(tmp_path, qapp, unit='KB')
    rule = store.put('data', str(tmp_path / 'data'), 1536)
    assert dialog.table.item(0, 2).text() == '1.5 KB'
    assert '1,536 B' in dialog.table.item(0, 2).toolTip()
    assert dialog.table.item(0, 6).text() == tr('budget_not_scanned')
    _publish(store, 2048)
    observed = dialog.table.item(0, 4).text()
    assert dialog.table.item(0, 3).text() == '2.0 KB'
    assert dialog.table.item(0, 5).text() == '0.5 KB'
    store.put('data', rule.path, 3072, rule.identity)
    assert dialog.table.item(0, 4).text() == observed
    assert dialog.table.item(0, 3).text() == '2.0 KB'
    assert dialog.table.item(0, 5).text() == tr('budget_unknown')
    assert tr('budget_changed_limit') in dialog.table.item(0, 6).text()
    _publish(store, None, reason='incomplete')
    assert dialog.table.item(0, 3).text() == tr('budget_unknown')
    assert tr('budget_reason_incomplete') in dialog.table.item(0, 6).text()
    dialog.reject()


def test_refresh_language_and_units_preserve_selected_draft(tmp_path, qapp):
    dialog, store = _dialog(tmp_path, qapp, unit='TB')
    rule = store.put('data', str(tmp_path / 'data'), 1)
    dialog.table.selectRow(0)
    assert exact_bytes(dialog.limit.text(), dialog.unit.currentText()) == 1
    dialog.name.setText('unsaved name')
    dialog.limit.setText('1.25')
    expected = (dialog.name.text(), dialog.path.text(), dialog.limit.text(), dialog.unit.currentText())
    _publish(store, 4096)
    dialog.set_unit('MB')
    set_language('zh-TW')
    dialog.retranslate()
    assert dialog.selected_identity == rule.identity
    assert dialog.table.selectedItems()
    assert (dialog.name.text(), dialog.path.text(), dialog.limit.text(), dialog.unit.currentText()) == expected
    assert dialog.table.item(0, 3).text() == format_size(4096, 'MB')
    dialog.select_path(str(tmp_path / 'other'))
    assert dialog.path.text() == rule.path
    assert dialog.error.text() == tr('budget_keep_draft')
    dialog.reject()
    assert store.rows[0].rule.name == 'data'
    set_language('en')


@pytest.mark.parametrize('value', [0, 1536, MAX_BYTES])
def test_edit_existing_limit_and_reopen_keeps_exact_bytes(tmp_path, qapp, value):
    dialog, store = _dialog(tmp_path, qapp, unit='TB')
    rule = store.put('data', str(tmp_path / 'data'), value)
    dialog.table.selectRow(0)
    dialog.name.setText('renamed')
    dialog.update_button.click()
    reopened = FolderBudgetStore(QSettings(store.settings.fileName(), QSettings.Format.IniFormat))
    assert reopened.rows[0].rule.limit == value
    assert reopened.rows[0].rule.version == rule.version
    assert reopened.rows[0].rule.name == 'renamed'
    assert reopened.rows[0].observation is None
    assert not reopened.rows[0].alerted
    dialog.reject()


def test_empty_state_chooser_and_field_errors_keep_input(tmp_path, qapp, monkeypatch):
    dialog, store = _dialog(tmp_path, qapp)
    assert dialog.empty_hint.isVisible()
    from je_file_tree.gui import folder_budget_dialog
    monkeypatch.setattr(folder_budget_dialog.QFileDialog, 'getExistingDirectory',
                        lambda *_args: str(tmp_path / 'chosen'))
    dialog.choose_button.click()
    assert dialog.path.text() == str(tmp_path / 'chosen')
    assert not store.rows
    dialog.add_button.click()
    assert dialog.focusWidget() is dialog.name
    dialog.name.setText('new')
    dialog.path.setText('relative')
    dialog.limit.setText('0')
    dialog.add_button.click()
    assert dialog.focusWidget() is dialog.path
    dialog.path.setText(str(tmp_path / 'chosen'))
    dialog.limit.setText('0.1')
    dialog.add_button.click()
    assert dialog.focusWidget() is dialog.limit
    assert dialog.limit.text() == '0.1' and not store.rows
    dialog.limit.setText('0')
    dialog.add_button.click()
    assert store.rows[0].rule.limit == 0
    assert store.rows[0].observation is None
    assert not dialog.empty_hint.isVisible()
    dialog.reject()


def test_keyboard_visits_fields_and_cancel_keeps_persisted_rule(tmp_path, qapp):
    dialog, store = _dialog(tmp_path, qapp)
    store.put('saved', str(tmp_path / 'saved'), 1024)
    dialog.table.selectRow(0)
    dialog.name.setFocus()
    dialog.name.selectAll()
    QTest.keyClicks(dialog.name, 'draft')
    for expected in (dialog.path, dialog.choose_button, dialog.limit, dialog.unit):
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
        assert dialog.focusWidget() is expected
    QTest.keyClick(dialog.unit, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
    assert store.rows[0].rule.name == 'saved'


def test_workspace_budget_tracks_active_tab_unit_without_changing_draft(tmp_path, qapp, monkeypatch):
    original_open = FolderBudgetDialog.open
    def hidden_open(dialog):
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        original_open(dialog)
    monkeypatch.setattr(FolderBudgetDialog, 'open', hidden_open)
    settings = QSettings(str(tmp_path / 'workspace.ini'), QSettings.Format.IniFormat)
    settings.setValue('language', 'en')
    workspace = create_workspace(settings)
    workspace.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    workspace.show()
    workspace.budgets.put('saved', str(tmp_path / 'saved'), 1536)
    first = workspace.current
    first.set_unit('KB')
    workspace.show_budgets()
    dialog = workspace._budget_dialog
    assert dialog.table.item(0, 2).text() == '1.5 KB'
    dialog.name.setText('draft')
    first.set_unit('GB')
    assert dialog.table.item(0, 2).text() == '0.0 GB'
    workspace.add_tab()
    workspace.current.set_unit('MB')
    assert dialog.table.item(0, 2).text() == '0.0 MB'
    workspace.tabs.setCurrentIndex(0)
    assert dialog.table.item(0, 2).text() == '0.0 GB'
    assert dialog.name.text() == 'draft'
    dialog.reject()
    workspace.close()
    _wait(qapp, lambda: workspace._close_ready)


def test_large_persisted_observation_reopens_without_float_overflow(tmp_path, qapp):
    settings = QSettings(str(tmp_path / 'large.ini'), QSettings.Format.IniFormat)
    store = FolderBudgetStore(settings)
    store.put('large', str(tmp_path / 'large'), 1)
    _publish(store, 10 ** 1000)
    reopened = FolderBudgetStore(QSettings(settings.fileName(), QSettings.Format.IniFormat))
    assert not reopened.error
    dialog = FolderBudgetDialog(reopened)
    assert dialog.table.item(0, 3).text().endswith(' PB')
    assert format_size(10 ** 1000, 'B') in dialog.table.item(0, 3).toolTip()
    dialog.set_unit('KB')
    assert dialog.table.item(0, 3).text().endswith(' KB')
    assert tr('budget_over') in dialog.table.item(0, 6).text()
    dialog.reject()
