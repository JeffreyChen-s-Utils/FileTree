"""Verify workspace templates with keyboard input in hidden native windows.

Set QT_SCALE_FACTOR before launch for another scale. Contrast is a local palette
simulation; the operating system contrast mode is not changed or verified.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATH_COLUMN = 2
CAPTURE_TABS = 3
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.i18n import LANGUAGES, tr  # noqa: E402
from je_file_tree.gui.workspace_templates import read_templates  # noqa: E402
from je_file_tree.gui.workspace_templates_dialog import WorkspaceTemplatesDialog  # noqa: E402
from verify_budget_ux import palette, require, wait  # noqa: E402

_ORIGINAL_OPEN = WorkspaceTemplatesDialog.open


def hidden_open(dialog: WorkspaceTemplatesDialog) -> None:
    """Prevent native exposure before opening the real production dialog."""
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    _ORIGINAL_OPEN(dialog)


def tab_to(dialog: WorkspaceTemplatesDialog, target) -> None:
    """Reach a control through actual Tab events, never by assigning its focus."""
    for _ in range(40):
        if dialog.focusWidget() is target:
            return
        require(dialog.focusWidget() is not None, 'Keyboard focus was lost')
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
    raise RuntimeError(f'Tab cannot reach {type(target).__name__}')


def press(dialog: WorkspaceTemplatesDialog, target) -> None:
    """Tab to the requested button and activate the widget that owns keyboard focus."""
    tab_to(dialog, target)
    require(dialog.focusWidget() is target, 'Button did not receive keyboard focus')
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Space)


def edit_path(dialog: WorkspaceTemplatesDialog, text: str) -> None:
    """Reach and edit the first preview path using its table keyboard editor."""
    tab_to(dialog, dialog.table)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    require(dialog.table.currentColumn() == PATH_COLUMN, 'Arrow keys did not reach the path column')
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_F2)
    require(dialog.focusWidget() is not dialog.table, 'Path editor did not receive focus')
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(dialog.focusWidget(), text)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Return)
    QApplication.processEvents()
    require(dialog.table.item(0, 2).text() == text,
            f'Path edit was not retained: {dialog.table.item(0, 2).text()!r}')
    require(dialog.report is None and not dialog.load.isEnabled(), 'Edit kept a stale path check')


def open_dialog(app: QApplication, workspace) -> WorkspaceTemplatesDialog:
    """Open through the workspace action with a single keyboard starting focus."""
    workspace.templates_action.trigger()
    dialog = workspace._templates_dialog
    require(dialog is not None, 'Template action did not open a dialog')
    dialog.resize(984, 688)
    app.processEvents()
    dialog.name.setFocus()
    return dialog


def exercise(app: QApplication, workspace, source: Path) -> None:
    """Verify save, edit, error, recheck, cancel and replacement in the selected language."""
    page = workspace.current
    page.prepare_scan_scope(str(source))
    dialog = open_dialog(app, workspace)
    opening = dialog.current
    QTest.keyClicks(dialog.focusWidget(), 'Keyboard template')
    press(dialog, dialog.saved_buttons['add'])
    require(read_templates(workspace.settings)[0].state == opening, 'Add saved the wrong source')
    edit_path(dialog, 'relative-path')
    press(dialog, dialog.check)
    require(dialog.focusWidget() is dialog.table and dialog.table.item(0, 2).text() == 'relative-path',
            'Invalid path did not retain input and focus')
    require(dialog.status.text() == tr('templates_invalid'), 'Invalid path error is missing')
    edit_path(dialog, str(source / 'missing'))
    press(dialog, dialog.check)
    wait(app, lambda: dialog.report is not None)
    require(bool(dialog.report[0][0]), 'Unavailable path disappeared')
    require(tr('templates_active') in dialog.table.item(0, 0).text(), 'Active preview lacks a text label')
    press(dialog, dialog.saved_buttons['update'])
    require(read_templates(workspace.settings)[0].state == opening, 'Update persisted preview edits')
    require(dialog.report is None, 'Update reused the previous preview check')
    tab_to(dialog, dialog.name)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Backspace)
    press(dialog, dialog.saved_buttons['update'])
    require(dialog.focusWidget() is dialog.name and not dialog.name.text(), 'Name error lost draft or focus')
    page.start_scan(str(source))
    require(dialog._impact.tabs[0].scanning, 'Starting scan did not update live impact')
    wait(app, lambda: page._worker is None)
    require(not dialog._impact.tabs[0].scanning and dialog._impact.tabs[0].has_result,
            'Completed scan did not update the open dialog')
    outcome = page.results.outcome
    press(dialog, dialog.cancel)
    require(workspace.current is page and page.results.outcome is outcome, 'Cancel replaced existing results')
    require(workspace._templates_dialog is None, 'Cancel did not close the manager')
    replace_with_keyboard(app, workspace, source)


def replace_with_keyboard(app: QApplication, workspace, source: Path) -> None:
    """Load a retained unavailable scope without dispatching a scan."""
    dialog = open_dialog(app, workspace)
    missing = str(source / 'retained-unavailable')
    edit_path(dialog, missing)
    press(dialog, dialog.check)
    wait(app, lambda: dialog.report is not None)
    require(dialog.load.isEnabled(), 'Checked unavailable roots cannot be explicitly loaded')
    press(dialog, dialog.load)
    wait(app, lambda: workspace._replacement is None)
    require(workspace.current.capture_scan_scope() == missing, 'Replacement discarded the unavailable root')
    require(workspace.current._worker is None and workspace.current.results.outcome is None,
            'Replacement started scanning or retained an old result')
    require(not workspace.current._scan_path.isEnabled(), 'Unavailable root allows Start')


def prepare_capture(app: QApplication, workspace, source: Path) -> WorkspaceTemplatesDialog:
    """Create old results, a queued owner, a blank tab and an unavailable long scope."""
    first = workspace.current
    first.start_scan(str(source))
    wait(app, lambda: first._worker is None)
    long_path = str(source / ('long-folder-name-' * 10) / 'retained-unavailable')
    first.prepare_scan_scope((str(source), long_path))
    second = workspace.add_tab()
    second._dispatch_scan = lambda _worker: None
    second.start_scan(str(source))
    workspace.add_tab()
    workspace.tabs.setCurrentIndex(0)
    dialog = open_dialog(app, workspace)
    press(dialog, dialog.check)
    wait(app, lambda: dialog.report is not None)
    require(len(dialog._impact.tabs) == CAPTURE_TABS and sum(tab.scanning for tab in dialog._impact.tabs) == 1,
            'Capture did not include queued ownership')
    require(sum(tab.has_result for tab in dialog._impact.tabs) == 1, 'Capture did not include old results')
    require(long_path in dialog.impact_details.toPlainText(), 'Long scope is truncated in copyable details')
    return dialog


def capture(app: QApplication, dialog, language: str, args) -> list[dict[str, object]]:
    """Record translated controls, complete paths and bounded native geometry."""
    records = []
    themes = ('light', 'dark', 'contrast') if args.theme == 'all' else (args.theme,)
    sizes = ((1024, 768), (1366, 768)) if args.width is None else ((args.width, args.height),)
    for theme in themes:
        palette(theme)
        for width, height in sizes:
            dialog.resize(min(1100, width - 40), height - 80)
            app.processEvents()
            require(dialog.width() <= width and dialog.height() <= height, 'Dialog exceeds logical desktop')
            for widget in (dialog.name, *dialog.saved_buttons.values(), dialog.table, dialog.check,
                           dialog.impact_summary, dialog.load, dialog.cancel):
                require(dialog.rect().contains(widget.mapTo(dialog, widget.rect().bottomRight())),
                        'Template control extends outside the dialog')
            require(dialog.table.horizontalScrollBar().maximum() == 0, 'Preview columns need horizontal scrolling')
            header = dialog.table.horizontalHeader()
            for column in range(dialog.table.columnCount()):
                text = dialog.table.horizontalHeaderItem(column).text()
                require(header.fontMetrics().horizontalAdvance(text) + 12 <= header.sectionSize(column),
                        f'Preview header is clipped: {text}')
            require(tr('templates_active') in dialog.table.item(0, 0).text(), 'Active text is untranslated')
            require(tr('templates_scanning') in dialog.impact_details.toPlainText(), 'Queued scan text is missing')
            name = f'template-{language}-{theme}-{width}x{height}.png'
            require(dialog.grab().save(str(args.output / name)), 'Screenshot could not be saved')
            records.append({'image': name, 'language': language, 'theme': theme,
                            'desktop': [width, height], 'dialog': [dialog.width(), dialog.height()],
                            'device_pixel_ratio': dialog.devicePixelRatioF()})
    return records


def main() -> None:
    """Run each language's keyboard journey with private settings and no visible native windows."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('all', *LANGUAGES), default='all')
    parser.add_argument('--theme', choices=('all', 'light', 'dark', 'contrast'), default='all')
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int, default=768)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    WorkspaceTemplatesDialog.open = hidden_open
    languages = tuple(LANGUAGES) if args.language == 'all' else (args.language,)
    records = []
    with tempfile.TemporaryDirectory(prefix='filetree-template-ux-') as directory:
        root = Path(directory)
        source = root / 'Documents'
        source.mkdir()
        (source / 'data.bin').write_bytes(b'x' * 4096)
        for language in languages:
            settings = QSettings(str(root / f'{language}.ini'), QSettings.Format.IniFormat)
            settings.setValue('language', language)
            settings.setValue('check_updates', False)
            workspace = create_workspace(settings)
            workspace.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            workspace.show()
            exercise(app, workspace, source)
            dialog = prepare_capture(app, workspace, source)
            records.extend(capture(app, dialog, language, args))
            press(dialog, dialog.cancel)
            workspace.close()
            wait(app, lambda workspace=workspace: workspace._close_ready)
            workspace.deleteLater()
    result = {'checks': 'passed', 'scale_factor': os.environ.get('QT_SCALE_FACTOR', 'default'),
              'keyboard_journeys': list(languages),
              'contrast': 'simulated local palette; native OS contrast not changed or verified',
              'captures': records}
    (args.output / 'template-ux.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.stdout.write(f'Template UX verified; {len(records)} captures written to {args.output}\n')


if __name__ == '__main__':
    main()
