"""Start the application: ``python -m je_file_tree [folder]`` or the ``je-file-tree`` command."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtCore import QLocale, QSettings
from PySide6.QtWidgets import QApplication

from je_file_tree import __version__
from je_file_tree.gui.i18n import LANGUAGES, match_language, set_language
from je_file_tree.gui.icon import app_icon, claim_taskbar_button
from je_file_tree.gui import elevation
from je_file_tree.gui.main_window import ASK_ADMIN_KEY, MainWindow, read_flag
from je_file_tree.gui.qt_translation import apply_qt_translation
from je_file_tree.gui.scan_worker import pace_workers
from je_file_tree.gui.themes import theme_controller

ORGANIZATION = "JE-Chen"
APPLICATION = "FileTree"


def create_window(settings: QSettings, folder: str | None = None) -> MainWindow:
    """Build the window in the remembered (or the system's) language, scanning ``folder`` if given."""
    language = str(settings.value("language", ""))
    if language not in LANGUAGES:
        language = match_language(QLocale.system().name())
    set_language(language)
    theme_controller().apply(str(settings.value('theme', 'system')))
    apply_qt_translation(language)
    window = MainWindow(settings)
    window.setWindowIcon(app_icon())
    if folder:
        window.start_scan(folder)
    return window


def wants_admin_prompt(settings: QSettings) -> bool:
    """Whether to ask for administrator rights before the window opens (Windows, not yet elevated, not turned off)."""
    return elevation.can_elevate() and read_flag(settings, ASK_ADMIN_KEY, True)


def main(argv: Sequence[str]) -> int:
    """Run the window until it is closed; ``argv`` may hold one folder to scan right away."""
    claim_taskbar_button()  # before any window exists, or Windows files it under Python's button
    app = QApplication.instance() or QApplication([sys.argv[0], *argv])
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationName(APPLICATION)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    folder = next((argument for argument in argv if not argument.startswith("-")), None)
    settings = QSettings()
    # Like TreeSize: ask first, so every folder can be read. Declining keeps this copy.
    if wants_admin_prompt(settings) and elevation.relaunch_elevated(list(argv)):
        return 0
    pace_workers()  # background work waits while the window is busy
    window = create_window(settings, folder)
    window.show()
    window._updates.start()
    return app.exec()


def run() -> None:
    """Entry point of the ``je-file-tree`` command."""
    sys.exit(main(sys.argv[1:]))
