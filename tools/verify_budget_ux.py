"""Drive budget controls in hidden native windows and save reproducible UX evidence.

Run with QT_SCALE_FACTOR set before launch to inspect another scale. The contrast
choice is a local simulated palette, not a change to the operating system mode.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

LIMIT_BYTES = 1536
LIGHT_BACKGROUND_THRESHOLD = 0.5
HEADER_PADDING = 12
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.folder_budget_dialog import FolderBudgetDialog  # noqa: E402
from je_file_tree.gui.folder_budget_store import FolderBudgetStore  # noqa: E402
from je_file_tree.gui.i18n import LANGUAGES, set_language, tr  # noqa: E402
from je_file_tree.gui.search_ranges import exact_bytes  # noqa: E402
from je_file_tree.gui.themes import theme_controller  # noqa: E402


def require(condition: bool, message: str) -> None:
    """Fail with the observable behavior that was not established."""
    if not condition:
        raise RuntimeError(message)


def wait(app: QApplication, condition) -> None:
    """Process local widget events until an owned worker has completed."""
    deadline = time.monotonic() + 30
    while not condition():
        if time.monotonic() >= deadline:
            raise RuntimeError('Timed out waiting for budget scan or close')
        app.processEvents()
        time.sleep(0.01)


def hidden_open(dialog: FolderBudgetDialog) -> None:
    """Keep a production dialog off screen before opening it."""
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    _ORIGINAL_OPEN(dialog)


_ORIGINAL_OPEN = FolderBudgetDialog.open


def exercise(app: QApplication, workspace, source: Path) -> FolderBudgetDialog:
    """Use controls, keyboard input and a complete owned scan before rendering."""
    workspace.budget_action.trigger()
    dialog = workspace._budget_dialog
    require(dialog is not None, 'Budget action did not open its dialog')
    app.processEvents()
    require(dialog.empty_hint.isVisible(), 'Empty budget explanation is missing')
    original_chooser = QFileDialog.getExistingDirectory
    QFileDialog.getExistingDirectory = lambda *_args: str(source)
    try:
        dialog.choose_button.click()
    finally:
        QFileDialog.getExistingDirectory = original_chooser
    require(dialog.path.text() == str(source), 'Folder choice did not fill the target')
    require(workspace.current._worker is None, 'Folder choice started a scan')
    dialog.name.setFocus()
    QTest.keyClicks(dialog.name, 'Documents')
    for field in (dialog.path, dialog.choose_button, dialog.limit, dialog.unit):
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
        require(dialog.focusWidget() is field, 'Budget field tab order differs')
    dialog.limit.setText('1.5')
    dialog.unit.setCurrentText('KiB')
    QTest.keyClick(dialog.add_button, Qt.Key.Key_Space)
    require(workspace.budgets.rows[0].rule.limit == LIMIT_BYTES, 'Exact binary limit was not saved')
    dialog.table.selectRow(0)
    require(exact_bytes(dialog.limit.text(), dialog.unit.currentText()) == LIMIT_BYTES,
            'Selected limit cannot round trip')
    dialog.name.setText('Unsubmitted draft')
    draft = (dialog.name.text(), dialog.path.text(), dialog.limit.text(), dialog.unit.currentText())
    workspace.current.start_scan(str(source))
    wait(app, lambda: workspace.current._worker is None)
    require(workspace.budgets.rows[0].status == 'over', 'Full scan did not publish over-limit usage')
    require(draft == (dialog.name.text(), dialog.path.text(), dialog.limit.text(), dialog.unit.currentText()),
            'Scan publication replaced an unsubmitted edit')
    workspace.current.set_unit('KB')
    require(dialog.table.item(0, 3).text() == '4.0 KB', 'Active-tab size unit did not reach the table')
    require(dialog.name.text() == draft[0], 'Size unit change replaced a draft')
    dialog.new_button.click()
    dialog.name.setText('Invalid limit draft')
    dialog.limit.setText('-1')
    dialog.add_button.click()
    require(dialog.focusWidget() is dialog.limit and dialog.limit.text() == '-1',
            'Validation did not preserve and focus the bad limit')
    require(len(workspace.budgets.rows) == 1, 'Invalid input created a budget')
    QTest.keyClick(dialog.limit, Qt.Key.Key_Escape)
    app.processEvents()
    require(workspace._budget_dialog is None, 'Escape did not close the draft')
    fresh = FolderBudgetStore(QSettings(workspace.settings.fileName(), QSettings.Format.IniFormat))
    require(fresh.rows[0].rule.name == 'Documents' and fresh.rows[0].rule.limit == LIMIT_BYTES,
            'Closing a draft changed the persisted budget')
    require(fresh.rows[0].alerted, 'Over-limit reminder was not persisted')
    workspace.budget_action.trigger()
    return workspace._budget_dialog


def palette(choice: str) -> None:
    """Select a local theme, or a simulated high-contrast palette."""
    target = 'light' if choice == 'contrast' else choice
    controller = theme_controller()
    controller.apply('dark' if target == 'light' else 'light')
    controller.apply(target)
    if choice != 'contrast':
        background = QApplication.palette().color(QPalette.ColorRole.Window)
        require((background.lightnessF() > LIGHT_BACKGROUND_THRESHOLD) == (choice == 'light'),
                'The rendered palette does not match the requested theme')
        return
    app = QApplication.instance()
    app.setStyleSheet('')
    app.setStyle('Fusion')
    colors = QPalette()
    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button,
                 QPalette.ColorRole.AlternateBase, QPalette.ColorRole.ToolTipBase):
        colors.setColor(role, QColor('black'))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.ToolTipText, QPalette.ColorRole.PlaceholderText):
        colors.setColor(role, QColor('white'))
    colors.setColor(QPalette.ColorRole.Highlight, QColor('yellow'))
    colors.setColor(QPalette.ColorRole.HighlightedText, QColor('black'))
    app.setPalette(colors)


def observation_states(app: QApplication, workspace, dialog, source: Path) -> None:
    """Produce unknown and stale observations with a real scan, then add an unscanned rule."""
    nested = source / 'Changed limit'
    nested.mkdir()
    (nested / 'data.bin').write_bytes(b'x' * 100)
    for name, path, limit in (('Missing folder', source / 'missing', '0'), ('Changed limit', nested, '50')):
        dialog.new_button.click()
        dialog.name.setText(name)
        dialog.path.setText(str(path))
        dialog.unit.setCurrentText('B')
        dialog.limit.setText(limit)
        dialog.add_button.click()
    workspace.current.start_scan(str(source))
    wait(app, lambda: workspace.current._worker is None)
    dialog.table.selectRow(2)
    dialog.unit.setCurrentText('B')
    dialog.limit.setText('200')
    dialog.update_button.click()
    dialog.name.setText('Not scanned yet')
    dialog.path.setText(str(source / 'not-scanned-yet'))
    dialog.limit.setText('100')
    dialog.add_button.click()
    require([row.status for row in workspace.budgets.rows] == ['over', 'unknown', 'waiting', 'waiting'],
            'Budget state examples were not established')


def capture(app: QApplication, workspace, dialog, args) -> list[dict[str, object]]:
    """Check rendered geometry and save each requested language/theme/size combination."""
    records = []
    languages = tuple(LANGUAGES) if args.language == 'all' else (args.language,)
    themes = ('light', 'dark', 'contrast') if args.theme == 'all' else (args.theme,)
    sizes = ((1024, 768), (1366, 768)) if args.width is None else ((args.width, args.height),)
    for language in languages:
        set_language(language)
        workspace.retranslate()
        for theme in themes:
            palette(theme)
            for width, height in sizes:
                dialog.resize(min(990, width - 40), min(620, height - 80))
                app.processEvents()
                require(dialog.width() <= width and dialog.height() <= height,
                        'Dialog exceeds the logical desktop')
                require(dialog.table.horizontalScrollBar().maximum() == 0,
                        'Primary budget columns need horizontal scrolling')
                header = dialog.table.horizontalHeader()
                for column in range(dialog.table.columnCount()):
                    title = dialog.table.horizontalHeaderItem(column).text()
                    require(header.fontMetrics().horizontalAdvance(title) + HEADER_PADDING <=
                            header.sectionSize(column), f'Budget header is clipped: {title}')
                for button in (dialog.new_button, dialog.add_button, dialog.update_button, dialog.delete_button):
                    require(dialog.rect().contains(button.mapTo(dialog, button.rect().bottomRight())),
                            'A budget action is outside the dialog')
                require(tr('budget_over') in dialog.table.item(0, 6).text(), 'Translated status is missing')
                require(tr('budget_changed_limit') in dialog.table.item(2, 6).text(),
                        'Stale observation status is missing')
                require(dialog.table.item(3, 6).text() == tr('budget_not_scanned'),
                        'New rule and changed limit are indistinguishable')
                require('1,536 B' in dialog.table.item(0, 2).toolTip(), 'Exact limit is missing')
                name = f'budget-{language}-{theme}-{width}x{height}.png'
                require(dialog.grab().save(str(args.output / name)), 'Could not save budget screenshot')
                records.append({'image': name, 'language': language, 'theme': theme,
                                'desktop': [width, height], 'dialog': [dialog.width(), dialog.height()],
                                'device_pixel_ratio': dialog.devicePixelRatioF()})
    return records


def main() -> None:
    """Exercise real controls in private settings and write the requested evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('all', *LANGUAGES), default='all')
    parser.add_argument('--theme', choices=('all', 'light', 'dark', 'contrast'), default='all')
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int, default=768)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    FolderBudgetDialog.open = hidden_open
    with tempfile.TemporaryDirectory(prefix='filetree-budget-ux-') as directory:
        root = Path(directory)
        source = root / 'Documents'
        source.mkdir()
        (source / 'data.bin').write_bytes(b'x' * 4096)
        settings = QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat)
        settings.setValue('language', 'en')
        settings.setValue('check_updates', False)
        workspace = create_workspace(settings)
        workspace.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        workspace.show()
        dialog = exercise(app, workspace, source)
        observation_states(app, workspace, dialog, source)
        records = capture(app, workspace, dialog, args)
        dialog.reject()
        workspace.close()
        wait(app, lambda: workspace._close_ready)
    result = {'checks': 'passed', 'scale_factor': os.environ.get('QT_SCALE_FACTOR', 'default'),
              'contrast': 'simulated local palette; native OS contrast not changed or verified',
              'chooser': 'OS chooser return stubbed; production button and input exercised', 'captures': records}
    (args.output / 'budget-ux.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.stdout.write(f'Budget UX verified; {len(records)} captures written to {args.output}\n')


if __name__ == '__main__':
    main()
