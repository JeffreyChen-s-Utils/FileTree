"""Verify cleanup review with hidden native Qt windows and private source fixtures.

Set QT_SCALE_FACTOR before launch. Contrast is a local palette simulation; this
probe does not verify OS contrast, screen-reader speech or native Trash moves.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox  # noqa: E402

from je_file_tree.core.node import Node  # noqa: E402
from je_file_tree.core.protected import PROGRAMS, Protection  # noqa: E402
from je_file_tree.core.scanner import scan  # noqa: E402
from je_file_tree.gui.cleanup_review import CleanupReview  # noqa: E402
from je_file_tree.gui.cleanup_text import explanation  # noqa: E402
from je_file_tree.gui.i18n import LANGUAGES, set_language, tr  # noqa: E402
from je_file_tree.gui.qt_translation import apply_qt_translation  # noqa: E402
from verify_budget_ux import palette, require, wait  # noqa: E402
from verify_keyboard import key, prepare_hidden, press, select_all, tab_to, verify_scale  # noqa: E402

COLUMNS = 4
MINIMUM_TABLE_HEIGHT = 120


def fixture(directory: Path) -> tuple[Node, list[Node], dict[Node, str], list[Protection]]:
    """Scan only fresh owned files and retain one explicitly unknown metadata observation."""
    source = directory / ('Review-資料-&-' + 'long-folder-' * 5)
    source.mkdir()
    for name in ('cache', 'build-' + 'long-name-' * 9, 'ordinary-protected'):
        (source / name).write_bytes(b'owned cleanup review fixture')
    root = scan(source).root
    by_name = {node.name: node for node in root.children}
    nodes = [by_name['cache'], next(node for node in root.children if node.name.startswith('build-')),
             by_name['ordinary-protected']]
    nodes[2].snapshot = None
    return root, nodes, {nodes[0]: 'browser_cache', nodes[1]: 'build_output'}, [Protection(nodes[2].path, PROGRAMS)]


def open_review(app: QApplication, data: tuple, width: int, height: int) -> CleanupReview:
    """Open the production dialog off screen and await its real estimate worker."""
    root, nodes, reasons, places = data
    dialog = CleanupReview(nodes, reasons, places, 'B', root)
    prepare_hidden(dialog)
    dialog.resize(min(980, width - 40), height - 100)
    dialog.show()
    app.processEvents()
    if dialog.focusWidget() is None:
        dialog.scope.setFocus()
    wait(app, lambda: dialog._current is None)
    return dialog


def inspect_layout(dialog: CleanupReview, width: int, height: int) -> None:
    """Require all primary columns, full headings, details and actions within the logical desktop."""
    require(dialog.width() <= width and dialog.height() <= height, 'Review exceeds logical desktop')
    require(dialog.model.columnCount() == COLUMNS, 'Review does not have four primary columns')
    require(dialog.view.horizontalScrollBar().maximum() == 0, 'Primary columns require horizontal scrolling')
    require(dialog.view.height() >= MINIMUM_TABLE_HEIGHT, 'Details squeezed the entry table')
    for column in range(COLUMNS):
        header = dialog.view.horizontalHeader()
        text = dialog.model.headerData(column, Qt.Orientation.Horizontal)
        require(header.fontMetrics().horizontalAdvance(text) + 12 <= header.sectionSize(column),
                f'Clipped primary header: {text}')
    for widget in (dialog.scope, dialog.view, dialog.details, dialog.summary, dialog.open_folder, dialog.buttons):
        require(dialog.rect().contains(widget.mapTo(dialog, widget.rect().bottomRight())),
                f'{type(widget).__name__} extends outside the dialog')
    require(dialog.summary.height() >= dialog.summary.heightForWidth(dialog.summary.width()),
            'Recovery limitations are clipped')


def keyboard_review(app: QApplication, dialog: CleanupReview) -> dict[str, int]:
    """Read the full path and consequences, check manual entries, and disable an empty selection."""
    low, manual, ordinary = dialog.model.nodes
    require(dialog.selected_nodes() == [low, ordinary], 'Initial rule selection changed')
    require(tr('size_unknown') in dialog.summary.text(), 'Missing metadata did not retain unknown recovery')
    require(tr('protected_programs') in dialog.model.risk_text(2), 'Protected reason is missing')
    require(tr('cleanup_risk_manual') not in dialog.model.details_text(2),
            'Explicit manual selection falsely claims it starts unchecked')
    select_all(dialog, dialog.scope, dialog._root.path)
    tab_to(dialog, dialog.view)
    key(dialog, Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
    key(dialog, Qt.Key.Key_Space)
    key(dialog, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
    key(dialog, Qt.Key.Key_Home)
    key(dialog, Qt.Key.Key_Space)
    wait(app, lambda: dialog._current is None)
    require(dialog.selected_nodes() == [], 'Unchecked entries remain in the final selection')
    require(not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled(),
            'Empty selection permits confirmation')
    key(dialog, Qt.Key.Key_Up)
    key(dialog, Qt.Key.Key_Space)
    wait(app, lambda: dialog._current is None)
    require(dialog.selected_nodes() == [manual], 'Space did not select exactly the manual entry')
    require('0–' in dialog.summary.text(), 'Known recovery estimate lost the zero lower bound')
    tab_to(dialog, dialog.details)
    expected = dialog.model.details_text(1)
    require(expected.count(explanation('build_output')) == 1, 'Reason and consequences are duplicated')
    key(dialog, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    require(dialog.details.createMimeDataFromSelection().text() == expected, 'Copy data omits full details')
    key(dialog, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
    scroll = dialog.details.verticalScrollBar()
    require(dialog.details.textCursor().atEnd() and
            dialog.details.viewport().rect().contains(dialog.details.cursorRect()),
            'End cannot reveal the complete consequence')
    observed = {'value': scroll.value(), 'maximum': scroll.maximum()}
    key(dialog, Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier)
    tab_to(dialog, dialog.open_folder)
    tab_to(dialog, dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
    return observed


def capture(app: QApplication, data: tuple, args) -> list[dict[str, object]]:
    """Exercise each language, palette and logical desktop independently, including accept and cancel."""
    records = []
    languages = LANGUAGES if args.language == 'all' else (args.language,)
    themes = ('light', 'dark', 'contrast') if args.theme == 'all' else (args.theme,)
    sizes = ((1024, 768), (1366, 768)) if args.width is None else ((args.width, args.height),)
    for language in languages:
        set_language(language)
        translated = apply_qt_translation(language)
        require(language == 'en' or translated, 'Qt standard button translation is unavailable')
        for theme in themes:
            palette(theme)
            for width, height in sizes:
                dialog = open_review(app, data, width, height)
                try:
                    ratio = verify_scale(dialog)
                    inspect_layout(dialog, width, height)
                    scroll = keyboard_review(app, dialog)
                    name = f'cleanup-{language}-{theme}-{width}x{height}.png'
                    require(dialog.grab().save(str(args.output / name)), 'Screenshot failed')
                    checked = dialog.selected_nodes()
                    press(dialog, dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
                    wait(app, lambda current=dialog: not current.isVisible() and not current._running)
                    require(dialog.result() == QDialog.DialogCode.Accepted and dialog.selected_nodes() == checked,
                            'Acceptance changed the reviewed target identities')
                finally:
                    dialog.shutdown()
                    dialog.deleteLater()
                cancel_review(app, data, width, height)
                records.append({'image': name, 'language': language, 'theme': theme, 'desktop': [width, height],
                                'device_pixel_ratio': ratio, 'keyboard_journey': 'passed',
                                'accepted_paths': [node.path for node in checked], 'cancel': 'rejected',
                                'details_end_scroll': scroll})
    return records


def cancel_review(app: QApplication, data: tuple, width: int, height: int) -> None:
    """Cancel through the focused standard button without emitting acceptance."""
    dialog = open_review(app, data, width, height)
    accepted = []
    dialog.accepted.connect(lambda: accepted.append(True))
    try:
        press(dialog, dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel))
        wait(app, lambda: not dialog.isVisible() and not dialog._running)
        require(dialog.result() == QDialog.DialogCode.Rejected and not accepted, 'Cancel accepted a source action')
    finally:
        dialog.shutdown()
        dialog.deleteLater()


def main() -> None:
    """Run a private native review matrix without desktop input, settings writes or source moves."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('all', *LANGUAGES), default='all')
    parser.add_argument('--theme', choices=('all', 'light', 'dark', 'contrast'), default='all')
    parser.add_argument('--width', type=int)
    parser.add_argument('--height', type=int, default=768)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='filetree-cleanup-ux-') as directory:
        data = fixture(Path(directory))
        before = {node.path: Path(node.path).read_bytes() for node in data[1]}
        records = capture(app, data, args)
        require(all(Path(path).read_bytes() == value for path, value in before.items()), 'Owned source bytes changed')
    result = {'checks': 'passed', 'scale_factor': os.environ.get('QT_SCALE_FACTOR', 'default'),
              'contrast': 'simulated local palette; native OS contrast not verified',
              'keyboard_setup': 'Actual focus receives local Qt keys; initial focus seeded only if absent.',
              'source_operations': 'none; review accept returns nodes only; private source bytes unchanged',
              'captures': records}
    (args.output / 'cleanup-ux.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.stdout.write(f'Cleanup UX verified; {len(records)} configurations written to {args.output}\n')


if __name__ == '__main__':
    main()
