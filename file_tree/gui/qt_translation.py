"""Qt's own texts (Yes / No / Close buttons, the folder picker) in the chosen language."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QTranslator

# Qt ships no English catalogue: English is its built-in language.
CATALOGUES = {"zh-TW": "qtbase_zh_TW", "zh-CN": "qtbase_zh_CN"}
_installed: list[QTranslator] = []


def apply_qt_translation(language: str) -> bool:
    """Swap Qt's catalogue for ``language``; False when there is none (English) or it cannot be loaded."""
    app = QCoreApplication.instance()
    if app is None:
        return False
    while _installed:
        app.removeTranslator(_installed.pop())
    catalogue = CATALOGUES.get(language)
    if catalogue is None:
        return False
    translator = QTranslator(app)
    if not translator.load(catalogue, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        return False
    app.installTranslator(translator)
    _installed.append(translator)
    return True
