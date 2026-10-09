"""Prefer installed Japanese/Korean UI fonts while preserving the user's base size and style."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QFontDatabase

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
