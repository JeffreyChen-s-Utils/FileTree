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
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QTableView  # noqa: E402

from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.i18n import LANGUAGES, set_language  # noqa: E402
from je_file_tree.gui.search_ranges import SearchRangeDialog  # noqa: E402
from verify_budget_ux import palette, require, wait  # noqa: E402

MINIMUM_RESULT_HEIGHT = 80
MINIMUM_BYTES, MAXIMUM_BYTES = 1536, 8192
MAX_FOCUS_STEPS = 40


def editing_keyboard(app: QApplication, panel) -> None:
    """Expand editing and reach the custom range action through the real tab chain."""
    QTest.keyClick(panel.conditions_view.edit, Qt.Key.Key_Space)
    app.processEvents()
    require(panel.controls_scroll.isVisible(), 'Keyboard did not expand condition editing')
    panel.box.setFocus()
    for _ in range(MAX_FOCUS_STEPS):
        if panel.focusWidget() is panel.filters.custom:
            break
        QTest.keyClick(panel.focusWidget(), Qt.Key.Key_Tab)
    require(panel.focusWidget() is panel.filters.custom, 'Tab cannot reach custom ranges')
    viewport = panel.controls_scroll.viewport()
    require(viewport.rect().intersects(panel.filters.custom.geometry().translated(
        panel.filters.custom.parentWidget().mapTo(viewport, panel.filters.custom.parentWidget().rect().topLeft()))),
        'Focused range action did not scroll into view')
    panel.conditions_view.edit.click()
    app.processEvents()


def draft_controls(dialog: SearchRangeDialog) -> None:
    """Correct an invalid field, choose a date by keyboard, then accept exact bounds."""
    dialog.minimum.setText('-1')
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    require(dialog.values is None and dialog.focusWidget() is dialog.minimum, 'Invalid size lost focus')
    dialog.minimum.setText('1.5')
    dialog.min_unit.setCurrentText('KiB')
    dialog.maximum.setText('8192')
    dialog.start.choose_button.click()
    calendar = dialog.start.dialog
    require(calendar.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen), 'Calendar became visible')
    QTest.keyClick(calendar, Qt.Key.Key_Escape)
    require(dialog.start.text() == '', 'Calendar cancellation added a bound')
    dialog.start.choose_button.click()
    calendar = dialog.start.dialog
    calendar.calendar.setSelectedDate(QDate(2020, 1, 1))
    QTest.keyClick(calendar.calendar.findChild(QTableView), Qt.Key.Key_Right)
    QTest.keyClick(calendar.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.Key.Key_Space)
    require(dialog.start.text() == '2020-01-02', 'Calendar keyboard selection was not accepted')
    QTest.keyClick(dialog.start.clear_button, Qt.Key.Key_Space)
    require(dialog.start.text() == '', 'Date clear failed')
    dialog.start.setText('2020-01-01')
    dialog.through.setText('2090-12-31')
    QTest.keyClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.Key.Key_Space)


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
    original_exec = SearchRangeDialog.exec
    def hidden_exec(dialog):
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        QTimer.singleShot(0, lambda: draft_controls(dialog))
        return original_exec(dialog)
    SearchRangeDialog.exec = hidden_exec
    try:
        panel.filters.custom.click()
    finally:
        SearchRangeDialog.exec = original_exec
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
                editing_keyboard(app, panel)
                for button in panel.conditions_view.buttons.values():
                    if not button.isHidden():
                        button.setFocus()
                        app.processEvents()
                        require(panel.focusWidget() is button, 'Condition removal is not keyboard reachable')
                        require(button.width() >= button.sizeHint().width(), 'Condition action is clipped')
                panel.conditions_view.scroll.verticalScrollBar().setValue(0)
                date = panel.conditions_view.labels['changed']
                viewport = panel.conditions_view.scroll.viewport()
                require(viewport.rect().contains(date.mapTo(viewport, date.rect().bottomRight())),
                        'Applied dates are not visible without scrolling')
                name = f'search-{language}-{theme}-{width}x{height}'
                require(workspace.grab().save(str(args.output / f'{name}.png')), 'Screenshot failed')
                dialog = SearchRangeDialog(panel.filters.state(), workspace)
                dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
                dialog.show()
                app.processEvents()
                require(dialog.width() <= width and dialog.height() <= height, 'Range dialog exceeds desktop')
                require(dialog.grab().save(str(args.output / f'{name}-range.png')), 'Range screenshot failed')
                records.append({'image': f'{name}.png', 'range_image': f'{name}-range.png',
                                'language': language, 'theme': theme, 'desktop': [width, height],
                                'device_pixel_ratio': workspace.devicePixelRatioF()})
                dialog.reject()
                dialog.deleteLater()
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
        source = private / 'Reports & records'
        source.mkdir()
        (source / 'report.txt').write_bytes(b'x' * 4096)
        settings = QSettings(str(private / 'settings.ini'), QSettings.Format.IniFormat)
        settings.setValue('language', 'en')
        settings.setValue('check_updates', False)
        workspace = create_workspace(settings)
        workspace.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        workspace.show()
        exercise(app, workspace, source)
        records = capture(app, workspace, args)
        workspace.close()
        wait(app, lambda: workspace._close_ready)
    result = {'checks': 'passed', 'scale_factor': os.environ.get('QT_SCALE_FACTOR', 'default'),
              'contrast': 'simulated local palette; native OS contrast not changed or verified',
              'captures': records}
    (args.output / 'search-ux.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.stdout.write(f'Search UX verified; {len(records)} configurations written to {args.output}\n')


if __name__ == '__main__':
    main()
