"""Prefer installed Japanese/Korean UI fonts while preserving the user's base size and style."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

_FAMILIES = {
    "ja": {"win32": ("Yu Gothic UI", "Yu Gothic", "Meiryo"),
           "darwin": ("Hiragino Sans", "Hiragino Kaku Gothic ProN"),
           "other": ("Noto Sans CJK JP", "Noto Sans JP")},
    "ko": {"win32": ("Malgun Gothic",), "darwin": ("Apple SD Gothic Neo", "AppleGothic"),
           "other": ("Noto Sans CJK KR", "Noto Sans KR")},
}


def language_font(language: str, base: QFont) -> QFont:
    """Copy base and choose an installed locale family, preserving size/style and fallback otherwise.

    No font is downloaded or installed. Other languages restore the captured base font; changing
    Japanese/Korean never makes the previous locale's family the new default for another language.
    """
    font = QFont(base)
    candidates = _FAMILIES.get(language, {})
    available = set(QFontDatabase.families())
    for family in (*candidates.get(sys.platform, ()), *candidates.get("other", ())):
        if family in available:
            font.setFamily(family)
            break
    return font


_EMPHASIS = "_filetree_emphasis"  # widget property: the size factor of its bold application font


def emphasise(widget: QWidget, scale: float = 1.0) -> None:
    """Show ``widget`` in a bold copy of the application font, ``scale`` times its size, kept in step.

    A widget with a font of its own does not follow later application-font changes on every platform
    (macOS keeps its family), so ``apply_language_font`` re-applies this font to every marked widget.
    """
    widget.setProperty(_EMPHASIS, float(scale))
    widget.setFont(_emphasis_font(scale))


def _emphasis_font(scale: float) -> QFont:
    font = QFont(QApplication.font())
    font.setPointSizeF(font.pointSizeF() * scale)
    font.setBold(True)
    return font


def apply_language_font(language: str) -> QFont:
    """Make the language's font the application font, from the base font captured on first use.

    Application-wide, so every widget gets it, including ones created later (legend labels, dialogs):
    once a style sheet is active Qt no longer passes a window's font on to children created after it.
    """
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("a QApplication is required")
    base = getattr(app, "_filetree_base_font", None)
    if base is None:
        base = QFont(app.font())
        app._filetree_base_font = base
    font = language_font(language, base)
    if font != app.font():
        app.setFont(font)
        for widget in QApplication.allWidgets():
            scale = widget.property(_EMPHASIS)
            if scale is not None:
                widget.setFont(_emphasis_font(float(scale)))
    return font
