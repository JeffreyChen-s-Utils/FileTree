"""Folder entry points preserve scan context, exact budget identity and unsubmitted edits."""

import os

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest

from je_file_tree.core.folder_budgets import BudgetBatch, BudgetObservation
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanResult
from je_file_tree.gui import history, main_window
from je_file_tree.gui.app import create_workspace
from je_file_tree.gui.folder_budget_dialog import FolderBudgetDialog
from je_file_tree.gui.folder_budget_store import FolderBudgetStore
from je_file_tree.gui.i18n import set_language, tr
from je_file_tree.gui.main_window import RESULTS_PAGE
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.search_ranges import exact_bytes
from test_gui import _wait


@pytest.fixture
def workspace(tmp_path, qapp, monkeypatch):
    original_open = FolderBudgetDialog.open
    def hidden_open(dialog):
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        original_open(dialog)
    monkeypatch.setattr(FolderBudgetDialog, 'open', hidden_open)
    settings = QSettings(str(tmp_path / 'context.ini'), QSettings.Format.IniFormat)
    settings.setValue('language', 'en')
    workspace = create_workspace(settings)
    workspace.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    workspace.show()
    yield workspace
    if workspace._budget_dialog is not None:
        workspace._budget_dialog.reject()
    workspace.close()
    _wait(qapp, lambda: workspace._close_ready)
    set_language('en')


def loaded(window, path):
    """Install recorded nodes without inspecting the named source."""
    root = Node(str(path), True, children=[])
    folder = Node('folder-' * 30 + '&資料夾', True, parent=root, children=[])
    leaf = Node('data.bin', False, parent=folder, size=2048)
    root.children.append(folder)
    folder.children.append(leaf)
    window.results.show_outcome(analyse(ScanResult(root, [], 0)))
    window.pages.setCurrentIndex(RESULTS_PAGE)
    window.results.select_node(folder)
    return root, folder, leaf


def observations(store, tmp_path):
    """Prepare over, within, unknown and waiting observations in the real bounded store."""
    for name in ('over', 'within', 'unknown', 'waiting'):
        store.put(name, str(tmp_path / name), 1537)
    ticket = store.ticket()
    store.publish(BudgetBatch(tuple(BudgetObservation(rule.identity, rule.version, ticket.sequence,
                                                     1_700_000_000, amount, reason)
                                   for rule, amount, reason in zip(ticket.rules, (4096, 1, None),
                                                                  (None, None, 'missing'), strict=False))))


def visible_names(dialog):
    """Read the visible table rows as a user would see them."""
    return [dialog.table.item(index, 0).text() for index in range(dialog.table.rowCount())
            if not dialog.table.isRowHidden(index)]


def test_filter_counts_keyboard_and_hidden_draft_survive_refresh(workspace, tmp_path, qapp):
    observations(workspace.budgets, tmp_path)
    workspace.budget_unknown.setFocus()
    QTest.keyClick(workspace.focusWidget(), Qt.Key.Key_Space)
    dialog = workspace._budget_dialog
    assert visible_names(dialog) == ['unknown', 'waiting']
    assert workspace.budget_unknown.text() == tr('budget_count_unknown', count=2)
    assert workspace.budget_over.text() == tr('budget_count_over', count=1)
    dialog.status_filter.setFocus()
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Home)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
    assert dialog.focusWidget() is dialog.table
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Down)
    assert dialog.selected_identity == workspace.budgets.rows[0].rule.identity
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
    assert dialog.focusWidget() is dialog.name
    QTest.keyClicks(dialog.focusWidget(), ' draft')
    draft = dialog._input()
    workspace.show_budgets(status_filter='unknown')
    assert workspace._budget_dialog is dialog
    assert 'over' in dialog.selection_hint.text()
    assert tr('budget_over') in dialog.selection_hint.text()
    dialog.set_unit('TB')
    set_language('zh-TW')
    dialog.retranslate()
    workspace.budgets.changed.emit()
    assert dialog._input() == draft
    assert visible_names(dialog) == ['unknown', 'waiting']
    assert dialog.update_button.isEnabled()
    dialog.select_path(str(tmp_path / 'within'))
    assert dialog._input() == draft
    assert dialog.error.text() == tr('budget_keep_draft')
    assert dialog.status_filter.currentData() == 'unknown'
    workspace.budgets.error = 'Budget path must be absolute'
    workspace.budgets.changed.emit()
    assert workspace.budget_label.text()
    assert workspace.budget_unknown.isEnabled()
    qapp.processEvents()


def test_normalized_existing_path_loads_exact_identity_and_invalid_path_keeps_editor(tmp_path, qapp):
    store = FolderBudgetStore(QSettings(str(tmp_path / 'rules.ini'), QSettings.Format.IniFormat))
    rule = store.put('existing', str(tmp_path / 'saved'), (1 << 63) - 1)
    equivalent = str(tmp_path / 'saved' / '..' / 'saved') + os.sep
    dialog = FolderBudgetDialog(store, selected_path=equivalent, unit='TB', status_filter='over')
    assert dialog.selected_identity == rule.identity
    assert dialog.status_filter.currentData() == 'all'
    assert exact_bytes(dialog.limit.text(), dialog.unit.currentText()) == rule.limit
    before = dialog._input()
    dialog.select_path('relative')
    assert dialog._input() == before
    assert dialog.error.text()
    dialog.select_path(str(tmp_path / 'new'))
    assert dialog.selected_identity is None
    assert not dialog.limit.text()
    assert len(store.rows) == 1
    dialog.reject()


def test_no_matching_filter_is_distinct_from_no_rules_and_refresh_reapplies(tmp_path, qapp):
    store = FolderBudgetStore(QSettings(str(tmp_path / 'empty.ini'), QSettings.Format.IniFormat))
    dialog = FolderBudgetDialog(store, status_filter='over')
    assert dialog.empty_hint.text() == tr('budget_empty')
    rule = store.put('waiting', str(tmp_path / 'saved'), 1)
    assert dialog.empty_hint.text() == tr('budget_filter_empty')
    assert not visible_names(dialog)
    ticket = store.ticket()
    store.publish(BudgetBatch((BudgetObservation(rule.identity, rule.version, ticket.sequence,
                                                1_700_000_000, 2, None),)))
    assert visible_names(dialog) == ['waiting']
    dialog.reject()


def test_context_rechecks_selection_and_guards_without_details_work(workspace, tmp_path, monkeypatch):
    window = workspace.current
    assert window.folder_context().reason == 'folder_context_empty'
    root, folder, leaf = loaded(window, tmp_path / 'unread-source')
    target = folder.path
    details = window.results.details
    assert details.context_path.text() == folder.path
    assert details.history_button.isEnabled() and details.budget_button.isEnabled()
    window.results.select_node(leaf)
    assert window.folder_context().node is folder
    calls = []
    window._budget_show = calls.append
    monkeypatch.setattr(details, 'set_node', lambda *_args, **_kwargs: pytest.fail('Repeated details analysis'))
    window._update_actions()
    details.budget_requested.emit()
    assert calls == [target]
    window._worker = object()
    try:
        details.budget_requested.emit()
        window._update_folder_context()
        assert details.context_reason.text() == tr('folder_context_busy')
        assert not details.history_button.isEnabled()
    finally:
        window._worker = None
    window._closing = True
    details.budget_requested.emit()
    assert window.folder_context().reason == 'folder_context_closing'
    window._closing = False
    leaf.is_link = True
    details.budget_requested.emit()
    assert window.folder_context().reason == 'folder_context_link'
    leaf.is_link = False
    leaf.parent = None
    assert window.folder_context().reason == 'folder_context_stale'
    leaf.parent = folder
    root.name = ''
    assert window.folder_context().reason == 'folder_context_virtual'
    details.budget_requested.emit()
    assert calls == [target]
    window.show_folder_budgets()
    assert calls == [target, '']


def test_history_uses_one_query_and_retains_current_tab_selection_scroll(workspace, tmp_path, qapp, monkeypatch):
    loaded(workspace.current, tmp_path / 'first')
    second = workspace.add_tab()
    root, folder, _leaf = loaded(second, tmp_path / 'second')
    details = second.results.details
    queries, dialogs = [], []
    original_query = history.query_trend
    def query(*args, **kwargs):
        queries.append(args)
        return original_query(*args, **kwargs)
    monkeypatch.setattr(history, 'query_trend', query)
    def inspect(dialog):
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.show()
        dialogs.append(dialog)
        _wait(qapp, lambda: not dialog._running)
        assert dialog.root == root.path
        assert dialog.folder.text() == os.path.relpath(folder.path, root.path)
        dialog.reject()
        return 0
    monkeypatch.setattr(main_window.HistoryDialog, 'exec', inspect)
    before = second.results.tree.verticalScrollBar().value()
    details.history_requested.emit()
    assert len(dialogs) == len(queries) == 1
    assert workspace.current is second
    assert second.results.selected_node() is folder
    assert second.results.tree.verticalScrollBar().value() == before
    second._path_dialogs.add(object())
    try:
        workspace.tabs.setCurrentIndex(0)
        assert workspace.current.folder_context().reason == 'folder_context_busy'
        workspace.current.show_history()
        assert len(queries) == 1
    finally:
        second._path_dialogs.clear()


def test_details_tab_chain_reaches_workspace_counts(workspace, tmp_path, qapp):
    loaded(workspace.current, tmp_path / 'source')
    details = workspace.current.results.details
    details.toggle.setChecked(True)
    details.budget_button.setFocus()
    qapp.processEvents()
    visited = set()
    while workspace.focusWidget() is not workspace.budget_unknown:
        current = workspace.focusWidget()
        assert current not in visited, 'Tab stopped before reaching the workspace budget counts'
        visited.add(current)
        QTest.keyClick(current, Qt.Key.Key_Tab)
    assert workspace.budget_over in visited
    assert workspace.current.results._levels_combo in visited


def test_focused_details_action_remains_visible_after_translation_and_resize(workspace, tmp_path, qapp):
    loaded(workspace.current, tmp_path / 'source')
    details = workspace.current.results.details
    details.toggle.setChecked(True)
    details.history_button.setFocus()
    set_language('ja')
    workspace.retranslate()
    workspace.resize(1024, 768)
    qapp.processEvents()
    button = workspace.focusWidget()
    assert button is details.history_button
    viewport = details.body.viewport()
    bounds = button.rect().translated(button.mapTo(viewport, button.rect().topLeft()))
    assert viewport.rect().intersects(bounds)


def test_unfocused_details_keeps_its_scroll_on_context_and_language_refresh(workspace, tmp_path, qapp):
    loaded(workspace.current, tmp_path / 'source')
    details = workspace.current.results.details
    details.toggle.setChecked(True)
    details.history_button.setFocus()
    _wait(qapp, lambda: not details._timer.isActive() and not details._running)
    workspace.current.path_edit.setFocus()
    scroll = details.body.verticalScrollBar()
    assert scroll.maximum() > 20
    scroll.setValue(20)
    workspace.current._update_actions()
    set_language('zh-TW')
    workspace.retranslate()
    qapp.processEvents()
    assert workspace.focusWidget() is workspace.current.path_edit
    assert scroll.value() == 20
