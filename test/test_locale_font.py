"""Locale family selection keeps size/style, restores the original and never installs fonts."""

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QFont

from je_file_tree.gui import locale_font


@pytest.mark.parametrize("language, platform, family", [
    ("ja", "win32", "Yu Gothic UI"), ("ko", "win32", "Malgun Gothic"),
    ("ja", "darwin", "Hiragino Sans"), ("ko", "darwin", "Apple SD Gothic Neo"),
    ("ja", "linux", "Noto Sans CJK JP"), ("ko", "linux", "Noto Sans CJK KR"),
])
def test_installed_locale_family_preserves_size_style_and_the_base(qapp, monkeypatch, language, platform, family):
    base = QFont("owned base family", 11)
    base.setItalic(True)
    monkeypatch.setattr(locale_font, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(locale_font.QFontDatabase, "families", lambda: [family])
    chosen = locale_font.language_font(language, base)
    assert chosen.family() == family and chosen.pointSize() == 11 and chosen.italic()
    assert base.family() == "owned base family"
    assert locale_font.language_font("en", base).family() == base.family()


def test_missing_locale_fonts_keep_the_captured_system_font(qapp, monkeypatch):
    monkeypatch.setattr(locale_font.QFontDatabase, "families", lambda: [])
    base = QFont("owned system family", 10)
    assert locale_font.language_font("ko", base) == base
