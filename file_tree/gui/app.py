"""Start the application: ``python -m file_tree [folder]`` or the ``file-tree`` command."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtCore import QLocale, QSettings
from PySide6.QtWidgets import QApplication

from file_tree import __version__
from file_tree.gui.i18n import LANGUAGES, match_language, set_language
from file_tree.gui import elevation
from file_tree.gui.main_window import ASK_ADMIN_KEY, MainWindow, read_flag
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


def wants_admin_prompt(settings: QSettings) -> bool:
    """Whether to ask for administrator rights before the window opens (Windows, not yet elevated, not turned off)."""
    return elevation.can_elevate() and read_flag(settings, ASK_ADMIN_KEY, True)


def main(argv: Sequence[str]) -> int:
    """Run the window until it is closed; ``argv`` may hold one folder to scan right away."""
    app = QApplication.instance() or QApplication([sys.argv[0], *argv])
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationName(APPLICATION)
    app.setApplicationVersion(__version__)
    folder = next((argument for argument in argv if not argument.startswith("-")), None)
    settings = QSettings()
    # Like TreeSize: ask first, so every folder can be read. Declining keeps this copy.
    if wants_admin_prompt(settings) and elevation.relaunch_elevated(list(argv)):
        return 0
    window = create_window(settings, folder)
    window.show()
    return app.exec()


def run() -> None:
    """Entry point of the ``file-tree`` command."""
    sys.exit(main(sys.argv[1:]))
