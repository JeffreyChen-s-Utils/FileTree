"""Locale family selection keeps size/style, restores the original and never installs fonts."""

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.scanner import scan
from je_file_tree.gui import locale_font
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.themes import theme_controller


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


def test_language_font_reaches_widgets_created_later_under_the_theme(window, qapp, sample_tree):
    base = QApplication.instance()._filetree_base_font
    theme_controller().apply("dark")  # an application style sheet is active
    try:
        window.change_language("ko")
        expected = locale_font.language_font("ko", base).family()
        window.results.show_outcome(analyse(scan(sample_tree)))  # legend labels are created now
        labels = window.results._legend.labels()
        assert labels and all(label.font().family() == expected for label in labels)
        assert window.results.overview.values[0].font().family() == expected
        window.change_language("en")
        assert window.results.overview.values[0].font().family() == base.family()
    finally:
        window.change_language("en")
        theme_controller().apply("system")


def _family_bits() -> int:
    """The resolve-mask bits a family sets, taken from Qt itself (their values differ between versions)."""
    one, many = QFont(), QFont()
    one.setFamily("Courier New")
    many.setFamilies(["Courier New"])
    return one.resolveMask() | many.resolveMask()


def test_emphasis_font_sets_only_size_and_weight_so_the_family_follows(qapp):
    label = QLabel()
    label.setFont(QFont("Courier New", 13))  # an explicitly set family, as macOS reports its fonts
    assert label.font().resolveMask() & _family_bits()  # copying this font would have kept the family
    font = locale_font.emphasis_font(label, 2)
    assert font.pointSizeF() == 26 and font.bold()
    assert font.resolveMask() & _family_bits() == 0
