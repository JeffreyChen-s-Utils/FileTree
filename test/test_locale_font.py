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


def test_emphasised_widgets_follow_every_language_font_change(qapp, monkeypatch):
    label = QLabel()
    locale_font.emphasise(label, 2)
    base_size = QApplication.font().pointSizeF()
    assert label.font().bold() and label.font().pointSizeF() == 2 * base_size
    chosen = QFont(QApplication.font())
    chosen.setFamily("Courier New")  # stands in for a language's family, whatever the platform has
    monkeypatch.setattr(locale_font, "language_font", lambda _language, _base: chosen)
    try:
        locale_font.apply_language_font("xx")
        assert label.font().family() == "Courier New"  # re-applied, even where own fonts stop following
        assert label.font().bold() and label.font().pointSizeF() == 2 * base_size
    finally:
        monkeypatch.undo()
        locale_font.apply_language_font("en")
