"""Exercise history trends in hidden native Qt windows using private captured fixtures.

Set QT_SCALE_FACTOR before launch. Contrast uses a local palette simulation and
does not claim native operating-system contrast or screen-reader verification.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QWidget  # noqa: E402

from je_file_tree.core.history import ScanHistory  # noqa: E402
from je_file_tree.core.node import Node  # noqa: E402
from je_file_tree.core.scanner import ScanOptions  # noqa: E402
from je_file_tree.core.snapshot import pack_snapshot  # noqa: E402
from je_file_tree.core.trends import UnknownReason  # noqa: E402
from je_file_tree.gui.history import HistoryDialog  # noqa: E402
from je_file_tree.gui.i18n import LANGUAGES, set_language, tr  # noqa: E402
from je_file_tree.gui.qt_translation import apply_qt_translation  # noqa: E402
from verify_budget_ux import palette, require, wait  # noqa: E402

OBSERVATIONS = 3
DPR_TOLERANCE = 0.01


def tab_to(dialog, target) -> None:
    """Reach controls through Tab events on the actual focused widget."""
    for _ in range(60):
        if dialog.focusWidget() is target:
            return
        require(dialog.focusWidget() is not None, 'Keyboard focus was lost')
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
    raise RuntimeError(f'Tab cannot reach {type(target).__name__}')


def press(dialog, target) -> None:
    """Activate a button only after it owns focus."""
    tab_to(dialog, target)
    require(dialog.focusWidget() is target, 'Button did not receive focus')
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Space)


def type_text(dialog, target, text: str) -> None:
    """Replace literal text using the focused editor."""
    tab_to(dialog, target)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Backspace)
    QTest.keyClicks(dialog.focusWidget(), text)


def fixture(path: Path) -> tuple[ScanHistory, Node]:
    """Write private history for an in-memory tree whose source directory does not exist."""
    root = Node(str(path / 'unread-source'), True, children=[], snapshot=pack_snapshot(path.stat()))
    photos = Node('Photos', True, children=[], parent=root)
    root.children.extend((photos, Node('Long-folder-' * 12, True, parent=root)))
    store = ScanHistory(path / 'history')
    for index in range(OBSERVATIONS):
        photos.size = (index + 1) * 1024 * 1024
        root.size = photos.size
        store.save(root, options=ScanOptions())
    return store, root


def exercise(app: QApplication, dialog: HistoryDialog) -> None:
    """Drive invalid input, calendar cancel, presets, loaded navigation and point selection."""
    dialog.folder_input.setFocus()
    type_text(dialog, dialog.start_input.edit, 'invalid-date')
    press(dialog, dialog.apply_button)
    require(dialog.focusWidget() is dialog.start_input.edit, 'Invalid start date did not regain focus')
    require(dialog.start_input.text() == 'invalid-date', 'Invalid date was silently changed')
    press(dialog, dialog.start_input.choose_button)
    calendar = dialog.start_input.dialog
    require(calendar is not None and calendar.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen),
            'Calendar was not hidden before opening')
    require(calendar.focusWidget() is not None, 'Calendar has no keyboard focus')
    QTest.keyClick(calendar.focusWidget(), Qt.Key.Key_Escape)
    app.processEvents()
    require(dialog.start_input.text() == 'invalid-date', 'Calendar cancellation changed the draft')
    tab_to(dialog, dialog.period)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Home)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Down)
    require(dialog.start_input.text() == (date.today() - timedelta(days=29)).isoformat(), '30-day preset is wrong')
    press(dialog, dialog.apply_button)
    wait(app, lambda: not dialog._running)
    require(len(dialog.trend.points) == OBSERVATIONS, 'Preset query lost observations')
    choose_folder(app, dialog)
    press(dialog, dialog.root_button)
    wait(app, lambda: not dialog._running)
    require(dialog.trend.query.folder == '', 'Root button did not restore the original root')
    tab_to(dialog, dialog.period)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Home)
    require(not dialog.start_input.text() and not dialog.end_input.text(), 'All history did not clear both dates')
    press(dialog, dialog.apply_button)
    wait(app, lambda: not dialog._running)
    select_points(dialog)


def choose_folder(app: QApplication, dialog: HistoryDialog) -> None:
    """Enter and accept a loaded child, then cancel a second navigation without changing scope."""
    press(dialog, dialog.choose_folder_button)
    chooser = dialog.folder_dialog
    wait(app, lambda: bool(chooser.rows))
    require(chooser.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen), 'Folder chooser was exposed')
    tab_to(chooser, chooser.list)
    QTest.keyClick(chooser.focusWidget(), Qt.Key.Key_End)
    QTest.keyClick(chooser.focusWidget(), Qt.Key.Key_Return)
    wait(app, lambda: chooser.current.name == 'Photos' and not chooser.worker.isRunning())
    require(chooser.isVisible() and not chooser._closed,
            f'Enter closed chooser: visible={chooser.isVisible()} closed={chooser._closed} result={chooser.result()}')
    press(chooser, chooser.buttons.button(QDialogButtonBox.StandardButton.Ok))
    wait(app, lambda: dialog.folder_dialog is None and not dialog._running)
    require(dialog.trend.query.folder == 'Photos', 'Accepted folder did not drive the query')
    require(dialog.full_path.text().endswith('Photos'), 'Copyable full path differs from the query')
    query = dialog.trend.query
    press(dialog, dialog.choose_folder_button)
    chooser = dialog.folder_dialog
    require(chooser.focusWidget() is not None, 'Chooser lost initial focus')
    QTest.keyClick(chooser.focusWidget(), Qt.Key.Key_Escape)
    wait(app, lambda: dialog.folder_dialog is None)
    require(dialog.trend.query == query, 'Cancel changed the current query')
    press(dialog, dialog.choose_folder_button)
    chooser = dialog.folder_dialog
    wait(app, lambda: bool(chooser.rows))
    tab_to(chooser, chooser.list)
    QTest.keyClick(chooser.focusWidget(), Qt.Key.Key_Home)
    QTest.keyClick(chooser.focusWidget(), Qt.Key.Key_Return)
    wait(app, lambda: chooser.current.name.startswith('Long-folder-') and not chooser.worker.isRunning())
    full_path = chooser.current.path
    require(chooser.path.text() == full_path, 'Chooser lost the complete long path')
    press(chooser, chooser.buttons.button(QDialogButtonBox.StandardButton.Ok))
    wait(app, lambda: dialog.folder_dialog is None and not dialog._running)
    require(dialog.full_path.text() == full_path, 'Trend lost the complete accepted long path')


def select_points(dialog: HistoryDialog) -> None:
    """Exercise same-timestamp and unknown observations with real focused keyboard events."""
    result = dialog.trend
    stamp = result.points[0].entry.saved
    points = tuple(replace(point, entry=replace(point.entry, saved=stamp)) for point in result.points)
    points = (points[0], replace(points[1], size=None, change=None, reason=UnknownReason.MISSING,
                                change_reason=UnknownReason.INCOMPATIBLE),
              replace(points[2], change=None, change_reason=UnknownReason.MISSING))
    dialog._show_trend(replace(result, points=points))
    tab_to(dialog, dialog.chart)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Home)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    require(dialog.chart.selected_point == 1 and dialog.trend_view.currentRow() == 1,
            'Unknown observation cannot be reached independently')
    require(tr('trend_reason_missing') in dialog.point_details.toPlainText(), 'Size unknown reason is absent')
    require(tr('trend_reason_incompatible') in dialog.point_details.toPlainText(), 'Change unknown reason is absent')
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    require(dialog.chart.selected_point == OBSERVATIONS - 1, 'Same timestamp prevented sequential selection')
    tab_to(dialog, dialog.trend_view)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Up)
    require(dialog.chart.selected_point == 1, 'Table selection did not update the chart')
    require(not dialog.compare_button.isEnabled(), 'Point selection enabled full-root comparison')


def compare_root(app: QApplication, dialog: HistoryDialog) -> None:
    """Load the original full-root snapshot from its separate keyboard-driven comparison tab."""
    compared = []
    dialog.compare_requested.connect(compared.append)
    tab_to(dialog, dialog.tabs.tabBar())
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Right)
    require(dialog.tabs.currentWidget() is dialog.view, 'Comparison tab was not reached')
    tab_to(dialog, dialog.view)
    QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
    require(dialog.view.currentIndex().row() == 0, 'Comparison did not select the first retained scan')
    press(dialog, dialog.compare_button)
    wait(app, lambda: bool(compared))
    require(dialog._closed and compared[0].root == dialog.root, 'Comparison changed the original root or did not close')


def capture(app: QApplication, dialog: HistoryDialog, language: str, args) -> list[dict[str, object]]:
    """Capture two logical desktops in each palette and assert actual Qt scaling."""
    records = []
    themes = ('light', 'dark', 'contrast') if args.theme == 'all' else (args.theme,)
    sizes = ((1024, 768), (1366, 768)) if args.width is None else ((args.width, args.height),)
    expected_scale = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    for theme in themes:
        palette(theme)
        for width, height in sizes:
            dialog.resize(min(1100, width - 40), height - 80)
            app.processEvents()
            require(abs(dialog.devicePixelRatioF() - expected_scale) < DPR_TOLERANCE,
                    'Actual DPR differs from requested scale')
            require(dialog.width() <= width and dialog.height() <= height, 'History dialog exceeds logical desktop')
            for widget in (dialog.folder_input, dialog.choose_folder_button, dialog.root_button, dialog.full_path,
                           dialog.period, dialog.start_input, dialog.end_input, dialog.apply_button, dialog.chart,
                           dialog.point_details, dialog.net_label, dialog.tabs, dialog.status, dialog.stop_button):
                require(dialog.rect().contains(widget.mapTo(dialog, widget.rect().bottomRight())),
                        f'{type(widget).__name__} extends outside history dialog')
            require(dialog.trend_view.horizontalScrollBar().maximum() == 0,
                    'Trend columns require horizontal scrolling')
            for column in range(dialog.trend_view.columnCount()):
                header = dialog.trend_view.horizontalHeader()
                text = dialog.trend_view.horizontalHeaderItem(column).text()
                require(header.fontMetrics().horizontalAdvance(text) + 12 <= header.sectionSize(column),
                        f'Trend header clipped: {text}')
            name = f'trend-{language}-{theme}-{width}x{height}.png'
            require(dialog.grab().save(str(args.output / name)), 'Screenshot could not be saved')
            records.append({'image': name, 'language': language, 'theme': theme, 'desktop': [width, height],
                            'dialog': [dialog.width(), dialog.height()],
                            'device_pixel_ratio': dialog.devicePixelRatioF()})
    return records


def main() -> None:
    """Run the five-language matrix without settings writes or desktop keyboard/mouse input."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('all', *LANGUAGES), default='all')
    parser.add_argument('--theme', choices=('all', 'light', 'dark', 'contrast'), default='all')
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int, default=768)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    require(app.platformName() != 'offscreen', 'Native verification requires the native Qt platform')
    expected_scale = float(os.environ.get('QT_SCALE_FACTOR', '1'))
    screen = next((screen for screen in app.screens()
                   if abs(screen.devicePixelRatio() - expected_scale) < DPR_TOLERANCE), None)
    require(screen is not None, 'No native screen provides the requested actual DPR')
    languages = tuple(LANGUAGES) if args.language == 'all' else (args.language,)
    records = []
    with tempfile.TemporaryDirectory(prefix='filetree-trend-ux-') as directory:
        path = Path(directory)
        store, root = fixture(path)
        for language in languages:
            set_language(language)
            apply_qt_translation(language)
            parent = QWidget()
            parent.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            dialog = HistoryDialog(store, root.path, 'MB', parent, loaded_root=root)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            dialog.setScreen(screen)
            dialog.move(screen.availableGeometry().topLeft())
            dialog.show()
            wait(app, lambda dialog=dialog: not dialog._running)
            exercise(app, dialog)
            records.extend(capture(app, dialog, language, args))
            compare_root(app, dialog)
            wait(app, lambda dialog=dialog: not dialog._finish_waiting)
            dialog.deleteLater()
            parent.deleteLater()
            app.processEvents()
    result = {'checks': 'passed', 'keyboard_journeys': list(languages),
              'scale_factor': os.environ.get('QT_SCALE_FACTOR', 'default'),
              'contrast': 'simulated local palette; native OS contrast and screen readers not verified',
              'captures': records}
    (args.output / 'trend-ux.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.stdout.write(f'Trend UX verified; {len(records)} captures written to {args.output}\n')


if __name__ == '__main__':
    main()
