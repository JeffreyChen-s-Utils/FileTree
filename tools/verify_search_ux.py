"""Exercise search in hidden native windows; contrast is a simulated local palette."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QDate, QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QTableView  # noqa: E402

from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.i18n import LANGUAGES, set_language, tr  # noqa: E402
from je_file_tree.gui.qt_translation import apply_qt_translation  # noqa: E402
from je_file_tree.gui.search_ranges import SearchRangeDialog  # noqa: E402
from verify_budget_ux import palette, require, wait  # noqa: E402
from verify_keyboard import key, prepare_hidden, press, replace_text, select_all, tab_to, verify_scale  # noqa: E402

MINIMUM_RESULT_HEIGHT = 80
MINIMUM_BYTES, MAXIMUM_BYTES = 1536, 8192
MINIMUM_DESKTOP = (1024, 768)


def dialog_geometry(dialog) -> None:
    """Check native dialog bounds and actual scale against the smallest supported desktop."""
    verify_scale(dialog)
    require(dialog.width() <= MINIMUM_DESKTOP[0] and dialog.height() <= MINIMUM_DESKTOP[1],
            'A calendar or range dialog exceeds the logical desktop')


def keyboard_calendar(dialog: SearchRangeDialog, output: Path | None) -> None:
    """Cancel once, then choose the adjacent calendar date through its focus chain."""
    replace_text(dialog, dialog.start.edit, '2020-01-01')
    press(dialog, dialog.start.choose_button)
    calendar = dialog.start.dialog
    require(calendar.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen), 'Calendar became visible')
    if calendar.focusWidget() is None:
        calendar.calendar.findChild(QTableView).setFocus()
    press(calendar, calendar.buttons.button(QDialogButtonBox.StandardButton.Cancel))
    require(dialog.start.text() == '2020-01-01', 'Calendar cancellation changed the draft')
    press(dialog, dialog.start.choose_button)
    calendar = dialog.start.dialog
    if calendar.focusWidget() is None:
        calendar.calendar.findChild(QTableView).setFocus()
    tab_to(calendar, calendar.calendar.findChild(QTableView))
    key(calendar, Qt.Key.Key_Right)
    require(calendar.calendar.selectedDate() == QDate(2020, 1, 2), 'Calendar arrow key missed the next day')
    dialog_geometry(calendar)
    grid = calendar.calendar.findChild(QTableView)
    last = grid.model().index(grid.model().rowCount() - 1, grid.model().columnCount() - 1)
    require(grid.viewport().rect().contains(grid.visualRect(last)),
            f'Calendar last week is clipped: {grid.visualRect(last)} outside {grid.viewport().rect()}')
    if output is not None:
        require(calendar.grab().save(str(output.with_name(output.name + '-calendar.png'))),
                'Calendar screenshot failed')
    press(calendar, calendar.buttons.button(QDialogButtonBox.StandardButton.Ok))
    require(dialog.start.text() == '2020-01-02', 'Calendar acceptance did not change the draft')
    require(dialog.focusWidget() is dialog.start.edit, 'Calendar did not return to its input')
    press(dialog, dialog.start.clear_button)
    require(dialog.start.text() == '', 'Keyboard date clear did not remove the bound')


def keyboard_ranges(dialog: SearchRangeDialog, output: Path | None = None) -> None:
    """Enter exact bounds and calendar dates using Tab, text and focused Space events."""
    replace_text(dialog, dialog.minimum, '1.5')
    tab_to(dialog, dialog.min_unit)
    key(dialog, Qt.Key.Key_Home)
    key(dialog, Qt.Key.Key_Down)
    replace_text(dialog, dialog.maximum, '8192')
    tab_to(dialog, dialog.max_unit)
    key(dialog, Qt.Key.Key_Home)
    keyboard_calendar(dialog, output)
    replace_text(dialog, dialog.start.edit, '2020-01-01')
    replace_text(dialog, dialog.through.edit, '2090-12-31')
    dialog_geometry(dialog)
    if output is not None:
        require(dialog.grab().save(str(output.with_name(output.name + '-range.png'))), 'Range screenshot failed')
    press(dialog, dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))


def range_input(dialog: SearchRangeDialog) -> tuple[str, ...]:
    """Capture every literal draft field for cancellation and validation comparisons."""
    return (dialog.minimum.text(), dialog.min_unit.currentText(), dialog.maximum.text(),
            dialog.max_unit.currentText(), dialog.start.text(), dialog.through.text())


def invalid_ranges(dialog: SearchRangeDialog, output: Path) -> None:
    """Retain all draft fields on size and date errors, then cancel without applying."""
    replace_text(dialog, dialog.minimum, '-1')
    draft = range_input(dialog)
    press(dialog, dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
    require(range_input(dialog) == draft and dialog.focusWidget() is dialog.minimum and dialog.values is None,
            'Invalid size did not retain every field and focus its input')
    require(dialog.field_errors[dialog.minimum].isVisible(), 'Size error is not visible')
    dialog_geometry(dialog)
    require(dialog.grab().save(str(output.with_name(output.name + '-size-error.png'))), 'Size error capture failed')
    replace_text(dialog, dialog.minimum, '1536')
    replace_text(dialog, dialog.start.edit, 'invalid-date')
    draft = range_input(dialog)
    press(dialog, dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
    require(range_input(dialog) == draft and dialog.focusWidget() is dialog.start.edit and dialog.values is None,
            'Invalid date did not retain every field and focus its input')
    require(dialog.field_errors[dialog.start].isVisible(), 'Date error is not visible')
    dialog_geometry(dialog)
    require(dialog.grab().save(str(output.with_name(output.name + '-date-error.png'))), 'Date error capture failed')
    key(dialog, Qt.Key.Key_Escape)


def open_ranges(workspace, visit) -> None:
    """Keep the native modal hidden and propagate callback failures after closing its event loop."""
    errors = []
    original_exec = SearchRangeDialog.exec
    def hidden_exec(dialog):
        prepare_hidden(dialog)
        def run():
            try:
                if dialog.focusWidget() is None:
                    dialog.minimum.setFocus()
                visit(dialog)
            except Exception as error:  # noqa: BLE001 - re-raised after closing the modal event loop
                errors.append(error)
                dialog.reject()
        QTimer.singleShot(0, run)
        return original_exec(dialog)
    SearchRangeDialog.exec = hidden_exec
    try:
        press(workspace, workspace.current.results.search.filters.custom)
    finally:
        SearchRangeDialog.exec = original_exec
    if errors:
        raise errors[0]


def keyboard_search(app: QApplication, workspace, output: Path) -> None:
    """Complete search editing, date cancellation and condition removal without jumping focus."""
    results = workspace.current.results
    panel = results.search
    action = workspace.current._actions['find']
    require(action.shortcut() == QKeySequence(QKeySequence.StandardKey.Find), 'Search shortcut setting changed')
    action.trigger()
    app.processEvents()
    require(workspace.focusWidget() is panel.box, 'Search action did not focus the search input')
    require(workspace.grab().save(str(output.with_name(output.name + '-editing.png'))), 'Editor capture failed')
    literal = 'missing<&>' + 'long-condition-' * 12
    replace_text(workspace, panel.box, literal)
    key(workspace, Qt.Key.Key_Return)
    wait(app, lambda: panel._current is None)
    require(panel.model.rowCount() == 0, 'No-result search did not finish')
    select_all(workspace, panel.box, literal)
    replace_text(workspace, panel.box, '*.txt')
    key(workspace, Qt.Key.Key_Return)
    wait(app, lambda: panel._current is None)
    open_ranges(workspace, lambda dialog: keyboard_ranges(dialog, output))
    wait(app, lambda: panel._current is None)
    require(panel.filters.state()['min_size'] == MINIMUM_BYTES and panel.model.rowCount() == 1,
            'Keyboard range acceptance changed exact bytes or matching results')
    applied = panel.filters.state()
    open_ranges(workspace, lambda dialog: invalid_ranges(dialog, output))
    require(panel.filters.state() == applied, 'Cancelling invalid range edits changed the search')
    def cancel_reopened(dialog):
        require(dialog.minimum.text() == str(MINIMUM_BYTES) and dialog.start.text() == '2020-01-01',
                'Reopened range did not show the previously applied values')
        press(dialog, dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel))
    open_ranges(workspace, cancel_reopened)
    saved, root, selected = dict(panel._searches), panel._root, results.selected_node()
    scope = results._scope_button.isChecked()
    press(workspace, panel.conditions_view.edit)
    require(not panel.controls_scroll.isVisible(), 'Keyboard did not collapse the condition editor')
    tab_to(workspace, panel.conditions_view.scope, backwards=True)
    select_all(workspace, panel.conditions_view.scope, tr('search_scope_root', path=panel._root.path))
    press(workspace, panel.conditions_view.buttons['min_size'])
    require(panel.filters.state()['max_size'] == MAXIMUM_BYTES, 'Removing minimum changed maximum')
    press(workspace, panel.conditions_view.reset)
    require(panel._searches == saved and panel._root is root and results.selected_node() is selected
            and results._scope_button.isChecked() == scope, 'Keyboard Clear changed saved searches or scope')
    press(workspace, panel.conditions_view.edit)
    require(workspace.focusWidget() is panel.box, 'Keyboard did not reopen cleared search controls')
    replace_text(workspace, panel.box, '*.txt')
    open_ranges(workspace, keyboard_ranges)
    wait(app, lambda: panel._current is None)
    press(workspace, panel.conditions_view.edit)


def exercise(app: QApplication, workspace, source: Path) -> None:
    """Drive the production search route without touching user settings or files."""
    workspace.current.start_scan(str(source))
    wait(app, lambda: workspace.current._worker is None)
    results = workspace.current.results
    results.show_search()
    panel = results.search
    panel.box.setFocus()
    QTest.keyClicks(panel.box, '*.txt')
    QTest.keyClick(panel.box, Qt.Key.Key_Return)
    wait(app, lambda: panel._current is None)
    require(panel.model.rowCount() == 1, 'Name search did not find the private fixture')
    open_ranges(workspace, keyboard_ranges)
    require(panel.filters.state()['min_size'] == MINIMUM_BYTES, 'Range acceptance rounded exact bytes')
    panel.save('Private fixture')
    saved, root, selected = dict(panel._searches), panel._root, results.selected_node()
    scope = results._scope_button.isChecked()
    panel.conditions_view.buttons['min_size'].click()
    require(panel.filters.state()['max_size'] == MAXIMUM_BYTES, 'Minimum removal changed maximum')
    panel.conditions_view.reset.click()
    require(panel._searches == saved and panel._root is root, 'Clear changed saved searches or root')
    require(results.selected_node() is selected and results._scope_button.isChecked() == scope,
            'Clear changed tree selection or list scope')
    panel.box.setText('missing<&>')
    panel.rerun()
    wait(app, lambda: panel._current is None)
    require(panel._result.count == 0, 'No-result search did not finish')
    panel.box.setText('*.txt')
    panel.filters.apply({'min_size': 1536, 'max_size': 8192, 'changed': 'custom',
                         'date_start': '2020-01-01', 'date_through': '2090-12-31', 'kind': 'files'})
    wait(app, lambda: panel._current is None)
    require(panel.model.rowCount() == 1, 'Combined search lost the matching file')
    panel.conditions_view.edit.click()
    require(not panel.controls_scroll.isVisible(), 'Condition editor did not collapse')


def capture(app: QApplication, workspace, args) -> list[dict[str, object]]:
    """Record the complete workspace and range dialog in every requested configuration."""
    records = []
    languages = tuple(LANGUAGES) if args.language == 'all' else (args.language,)
    themes = ('light', 'dark', 'contrast') if args.theme == 'all' else (args.theme,)
    sizes = ((1024, 768), (1366, 768)) if args.width is None else ((args.width, args.height),)
    panel = workspace.current.results.search
    for language in languages:
        set_language(language)
        apply_qt_translation(language)
        workspace.retranslate()
        for theme in themes:
            palette(theme)
            for width, height in sizes:
                workspace.resize(width, height)
                app.processEvents()
                workspace.resize(width, height)
                app.processEvents()
                require(workspace.width() <= width and workspace.height() <= height,
                        f'Workspace exceeds desktop: {language} {workspace.size()} / {width}x{height}')
                require(panel.table.height() >= MINIMUM_RESULT_HEIGHT, 'Conditions squeeze out results')
                name = f'search-{language}-{theme}-{width}x{height}'
                ratio = verify_scale(workspace)
                keyboard_search(app, workspace, args.output / name)
                panel.conditions_view.scroll.verticalScrollBar().setValue(0)
                date = panel.conditions_view.labels['changed']
                viewport = panel.conditions_view.scroll.viewport()
                require(viewport.rect().contains(date.mapTo(viewport, date.rect().bottomRight())),
                        'Applied dates are not visible without scrolling')
                name = f'search-{language}-{theme}-{width}x{height}'
                require(workspace.grab().save(str(args.output / f'{name}.png')), 'Screenshot failed')
                records.append({'image': f'{name}.png', 'range_image': f'{name}-range.png',
                                'editing_image': f'{name}-editing.png',
                                'calendar_image': f'{name}-calendar.png', 'keyboard_journey': 'passed',
                                'size_error_image': f'{name}-size-error.png',
                                'date_error_image': f'{name}-date-error.png',
                                'language': language, 'theme': theme, 'desktop': [width, height],
                                'device_pixel_ratio': ratio})
    return records


def main() -> None:
    """Run private native interaction checks and render a language/theme/size matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('all', *LANGUAGES), default='all')
    parser.add_argument('--theme', choices=('all', 'light', 'dark', 'contrast'), default='all')
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int, default=768)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='filetree-search-ux-') as directory:
        private = Path(directory)
        source = private / ('Reports-資料夾-&-' + 'long-path-' * 10)
        source.mkdir()
        (source / 'report.txt').write_bytes(b'x' * 4096)
        settings = QSettings(str(private / 'settings.ini'), QSettings.Format.IniFormat)
        settings.setValue('language', 'en')
        settings.setValue('check_updates', False)
        workspace = create_workspace(settings)
        prepare_hidden(workspace)
        workspace.show()
        exercise(app, workspace, source)
        records = capture(app, workspace, args)
        workspace.close()
        wait(app, lambda: workspace._close_ready)
    result = {'checks': 'passed', 'scale_factor': os.environ.get('QT_SCALE_FACTOR', 'default'),
              'contrast': 'simulated local palette; native OS contrast not changed or verified',
              'keyboard_setup': 'Search QAction triggered; shortcut configured but active-window Ctrl+F not verified. '
                                'Initial focus seeded only when a newly opened hidden dialog has no focus.',
              'captures': records}
    (args.output / 'search-ux.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.stdout.write(f'Search UX verified; {len(records)} configurations written to {args.output}\n')


if __name__ == '__main__':
    main()
