"""Verify folder entry points through hidden native Qt focus chains and private metadata.

Set QT_SCALE_FACTOR before launch. Contrast is a local simulated palette.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, QTimer, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from je_file_tree.core.folder_budgets import BudgetBatch, BudgetObservation  # noqa: E402
from je_file_tree.core.history import ScanHistory  # noqa: E402
from je_file_tree.core.node import Node  # noqa: E402
from je_file_tree.core.scanner import ScanOptions, ScanResult  # noqa: E402
from je_file_tree.core.snapshot import pack_snapshot  # noqa: E402
from je_file_tree.gui import history, main_window  # noqa: E402
from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.folder_budget_dialog import FolderBudgetDialog  # noqa: E402
from je_file_tree.gui.history import HistoryDialog  # noqa: E402
from je_file_tree.gui.i18n import LANGUAGES, set_language, tr  # noqa: E402
from je_file_tree.gui.main_window import RESULTS_PAGE  # noqa: E402
from je_file_tree.gui.qt_translation import apply_qt_translation  # noqa: E402
from je_file_tree.gui.scan_worker import analyse  # noqa: E402
from je_file_tree.gui.search_ranges import exact_bytes  # noqa: E402
from verify_budget_ux import hidden_open, palette, require, wait  # noqa: E402
from verify_keyboard import key, prepare_hidden, press, replace_text, select_all, tab_to, verify_scale  # noqa: E402

RULE_BYTES = 1537
FOLDERS = 80
SELECTED = 40
_HISTORY_EXEC = HistoryDialog.exec


def loaded(window, path: Path, store: ScanHistory) -> Node:
    """Install and retain a recorded tree whose named source does not exist."""
    root = Node(str(path / 'unread-source'), True, children=[], snapshot=pack_snapshot(path.stat()))
    for index in range(FOLDERS):
        name = f'Folder-{index:03}' if index != SELECTED else 'Selected-&-資料夾-' + 'long-path-' * 14
        root.children.append(Node(name, True, parent=root, size=4096, children=[]))
    root.size, root.dir_count = FOLDERS * 4096, FOLDERS
    store.save(root, options=ScanOptions())
    window.results.show_outcome(analyse(ScanResult(root, [], 0)))
    window.pages.setCurrentIndex(RESULTS_PAGE)
    window.path_edit.setText(root.path)
    window.results.select_node(root.children[SELECTED])
    return root.children[SELECTED]


def populate(workspace, folder: Node, path: Path) -> None:
    """Persist independent over, unknown and waiting rules without scanning sources."""
    for name, target in (('Selected rule', folder.path), ('Unknown rule', str(path / 'missing')),
                         ('Waiting rule', str(path / 'waiting'))):
        workspace.budgets.put(name, target, RULE_BYTES)
    ticket = workspace.budgets.ticket()
    workspace.budgets.publish(BudgetBatch(tuple(
        BudgetObservation(rule.identity, rule.version, ticket.sequence, 1_700_000_000, amount, reason)
        for rule, amount, reason in zip(ticket.rules, (4096, None), (None, 'missing'), strict=False))))


def visible(dialog: FolderBudgetDialog) -> list[str]:
    """Read names from the currently visible rows."""
    return [dialog.table.item(index, 0).text() for index in range(dialog.table.rowCount())
            if not dialog.table.isRowHidden(index)]


class ContextProbe:
    """Own private native views and collect observable keyboard and query evidence."""

    def __init__(self, app: QApplication, workspace, output: Path) -> None:
        self.app, self.workspace, self.output = app, workspace, output
        self.name = ''
        self.width, self.height = 1024, 768
        self.queries = 0
        self.history_opens = 0
        self.failures: list[RuntimeError] = []
        self.query = history.query_trend

    def query_spy(self, *args, **kwargs):
        """Count existing metadata queries while preserving the real worker result."""
        self.queries += 1
        return self.query(*args, **kwargs)

    def history_exec(self, dialog: HistoryDialog) -> int:
        """Inspect the real modal dialog from a local Qt timer, then close through Escape."""
        prepare_hidden(dialog)
        dialog.resize(min(990, self.width - 30), self.height - 30)
        self.history_opens += 1
        def inspect():
            try:
                wait(self.app, lambda: not dialog._running)
                verify_scale(dialog)
                target = self.workspace.current.folder_context().node
                require(dialog.full_path.text() == target.path, 'History opened another folder')
                require(dialog.trend is not None, 'History query did not complete')
                if dialog.focusWidget() is None:
                    dialog.folder_input.setFocus()
                select_all(dialog, dialog.full_path, target.path)
                require(dialog.grab().save(str(self.output / f'{self.name}-history.png')),
                        'History screenshot failed')
                key(dialog, Qt.Key.Key_Escape)
            except RuntimeError as error:
                self.failures.append(error)
            finally:
                dialog.reject()
        QTimer.singleShot(0, inspect)
        result = _HISTORY_EXEC(dialog)
        if self.failures:
            raise self.failures.pop()
        return result

    def budget_journey(self, folder: Node) -> None:
        """Locate an exact rule, retain a hidden draft and traverse temporary status filters."""
        workspace = self.workspace
        details = workspace.current.results.details
        press(workspace, details.budget_button)
        dialog = workspace._budget_dialog
        require(dialog is not None, 'Context budget button did not open the manager')
        verify_scale(dialog)
        dialog.resize(min(990, self.width - 40), min(620, self.height - 80))
        self.app.processEvents()
        require(dialog.selected_identity == workspace.budgets.rows[0].rule.identity,
                'Existing folder rule did not retain its identity')
        require(exact_bytes(dialog.limit.text(), dialog.unit.currentText()) == RULE_BYTES,
                'Existing limit was rounded')
        if dialog.focusWidget() is None:
            dialog.name.setFocus()
        select_all(dialog, dialog.path, folder.path)
        replace_text(dialog, dialog.name, 'Unsubmitted draft')
        draft = dialog._input()
        tab_to(dialog, dialog.status_filter)
        key(dialog, Qt.Key.Key_End)
        require(visible(dialog) == ['Unknown rule', 'Waiting rule'], 'Unknown filter omitted waiting rules')
        require('Selected rule' in dialog.selection_hint.text(), 'Hidden edited rule lacks an explanation')
        workspace.show_budgets(selected_path=folder.path)
        require(dialog._input() == draft and dialog.status_filter.currentData() == 'unknown',
                'An external path request overwrote the draft or filter')
        require(dialog.error.text() == tr('budget_keep_draft'), 'Dirty guard explanation missing')
        require(dialog.grab().save(str(self.output / f'{self.name}-draft.png')), 'Draft screenshot failed')
        key(dialog, Qt.Key.Key_Home)
        key(dialog, Qt.Key.Key_Down)
        require(visible(dialog) == ['Selected rule'], 'Over-limit filter has the wrong rows')
        key(dialog, Qt.Key.Key_Tab)
        require(dialog.focusWidget() is dialog.table, 'Filter Tab did not enter the table')
        key(dialog, Qt.Key.Key_Tab)
        require(dialog.focusWidget() is dialog.name and dialog._input() == draft,
                'Table Tab lost the draft or failed to reach the editor')
        key(dialog, Qt.Key.Key_Escape)
        require(workspace._budget_dialog is None, 'Escape did not close the budget manager')
        require(workspace.budgets.rows[0].rule.name == 'Selected rule', 'Closing saved an unsubmitted draft')

    def count_journey(self) -> None:
        """Open both clickable workspace counts through the actual Tab focus chain."""
        workspace = self.workspace
        for button, names in ((workspace.budget_unknown, ['Unknown rule', 'Waiting rule']),
                              (workspace.budget_over, ['Selected rule'])):
            press(workspace, button)
            dialog = workspace._budget_dialog
            require(visible(dialog) == names, 'Workspace count opened the wrong filter')
            if dialog.focusWidget() is None:
                dialog.status_filter.setFocus()
            key(dialog, Qt.Key.Key_Escape)

    def capture(self, language: str, theme: str, size: tuple[int, int]) -> dict[str, object]:
        """Run the complete folder/history/budget route in one native configuration."""
        self.width, self.height = size
        self.name = f'context-{language}-{theme}-{self.width}x{self.height}'
        workspace = self.workspace
        workspace.resize(*size)
        self.app.processEvents()
        details = workspace.current.results.details
        if not details.toggle.isChecked():
            press(workspace, details.toggle)
        wait(self.app, lambda: not details._timer.isActive() and not details._running)
        workspace.resize(*size)
        self.app.processEvents()
        current = workspace.current
        folder = current.folder_context().node
        before = (workspace.tabs.currentIndex(), current.results.selected_node(),
                  current.results.tree.verticalScrollBar().value(), current.results.tabs.currentIndex())
        select_all(workspace, details.context_path, folder.path)
        queries, opens = self.queries, self.history_opens
        press(workspace, details.history_button)
        require(self.queries == queries + 1 and self.history_opens == opens + 1,
                'One folder action did not produce exactly one history query')
        self.budget_journey(folder)
        self.count_journey()
        after = (workspace.tabs.currentIndex(), current.results.selected_node(),
                 current.results.tree.verticalScrollBar().value(), current.results.tabs.currentIndex())
        require(before == after, 'A dialog changed the scan tab, selection or view position')
        require(self.queries == queries + 1, 'Budget navigation repeated the history query')
        tab_to(workspace, details.history_button)
        ratio = verify_scale(workspace)
        require(workspace.width() <= self.width and workspace.height() <= self.height,
                f'Workspace exceeds the logical desktop: {workspace.width()}x{workspace.height()}')
        require(workspace.grab().save(str(self.output / f'{self.name}.png')), 'Context screenshot failed')
        return {'language': language, 'theme': theme, 'desktop': size, 'device_pixel_ratio': ratio,
                'keyboard_journey': 'passed', 'history_queries': self.queries - queries,
                'image': f'{self.name}.png', 'draft_image': f'{self.name}-draft.png',
                'history_image': f'{self.name}-history.png'}


def run(app: QApplication, args, scratch: Path) -> list[dict[str, object]]:
    """Build independent scan tabs and reuse the production routes for every configuration."""
    settings = QSettings(str(scratch / 'settings.ini'), QSettings.Format.IniFormat)
    settings.setValue('language', 'en')
    settings.setValue('check_updates', False)
    workspace = create_workspace(settings)
    prepare_hidden(workspace)
    workspace.show()
    store = ScanHistory(scratch / 'history')
    first = scratch / 'first'
    second = scratch / 'second'
    first.mkdir()
    second.mkdir()
    loaded(workspace.current, first, store)
    folder = loaded(workspace.add_tab(), second, store)
    populate(workspace, folder, scratch)
    workspace.current.results.details.toggle.setFocus()
    probe = ContextProbe(app, workspace, args.output)
    languages = LANGUAGES if args.language == 'all' else (args.language,)
    themes = ('light', 'dark', 'contrast') if args.theme == 'all' else (args.theme,)
    records = []
    try:
        with patch.object(HistoryDialog, 'exec', lambda dialog: ContextProbe.history_exec(probe, dialog)), \
                patch.object(history, 'query_trend', probe.query_spy):
            for language in languages:
                set_language(language)
                apply_qt_translation(language)
                workspace.retranslate()
                for theme in themes:
                    palette(theme)
                    for size in ((1024, 768), (1366, 768)):
                        records.append(probe.capture(language, theme, size))
    finally:
        if workspace._budget_dialog is not None:
            workspace._budget_dialog.reject()
        workspace.close()
        wait(app, lambda: workspace._close_ready)
    return records


def main() -> None:
    """Run native hidden controls with isolated settings/history and save repeatable evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('all', *LANGUAGES), default='all')
    parser.add_argument('--theme', choices=('all', 'light', 'dark', 'contrast'), default='all')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    require(app.platformName() != 'offscreen', 'Native verification requires the native Qt platform')
    with tempfile.TemporaryDirectory(prefix='filetree-context-ux-') as temporary:
        scratch = Path(temporary)
        with patch.object(FolderBudgetDialog, 'open', hidden_open), \
                patch.object(main_window, 'history_folder', lambda: scratch / 'history'), \
                patch.object(main_window, 'journal_folder', lambda: scratch / 'journal'):
            records = run(app, args, scratch)
    result = {'checks': 'passed', 'scale_factor': os.environ.get('QT_SCALE_FACTOR', 'default'),
              'contrast': 'simulated local palette; OS contrast and screen-reader speech not verified',
              'input': 'local Qt events to actual focus; no desktop keyboard/mouse injection',
              'keyboard_setup': 'Initial hidden workspace focus; new dialogs seeded only if focus is absent.',
              'captures': records}
    (args.output / 'context-ux.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.stdout.write(f'Context UX verified; {len(records)} configurations written to {args.output}\n')


if __name__ == '__main__':
    main()
