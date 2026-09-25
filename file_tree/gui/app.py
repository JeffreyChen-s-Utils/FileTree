"""Start the application: ``python -m file_tree [folder]`` or the ``file-tree`` command."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtCore import QLocale, QSettings
from PySide6.QtWidgets import QApplication

from file_tree import __version__
from file_tree.gui.i18n import LANGUAGES, match_language, set_language
from file_tree.gui.main_window import MainWindow
from file_tree.gui.qt_translation import apply_qt_translation

ORGANIZATION = "JE-Chen"
APPLICATION = "FileTree"


def create_window(settings: QSettings, folder: str | None = None) -> MainWindow:
    """Build the window in the remembered (or the system's) language, scanning ``folder`` if given."""
    language = str(settings.value("language", ""))
    if language not in LANGUAGES:
        language = match_language(QLocale.system().name())
    set_language(language)
    apply_qt_translation(language)
    window = MainWindow(settings)
    if folder:
        window.start_scan(folder)
    return window


def main(argv: Sequence[str]) -> int:
    """Run the window until it is closed; ``argv`` may hold one folder to scan right away."""
    app = QApplication.instance() or QApplication([sys.argv[0], *argv])
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationName(APPLICATION)
    app.setApplicationVersion(__version__)
    folder = next((argument for argument in argv if not argument.startswith("-")), None)
    window = create_window(QSettings(), folder)
    window.show()
    return app.exec()


def run() -> None:
    """Entry point of the ``file-tree`` command."""
    sys.exit(main(sys.argv[1:]))
