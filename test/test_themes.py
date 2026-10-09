"""Light/dark palettes keep labels readable and reset cached/native rendering correctly."""

import pytest
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.scanner import scan
from je_file_tree.gui.age_colours import AGE_COLOURS, UNKNOWN_AGE_COLOUR
from je_file_tree.gui.app import create_window
from je_file_tree.gui.charts import BARS
from je_file_tree.gui.colours import contrast, readable_ink
from je_file_tree.gui.main_window import RESULTS_PAGE
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.themes import theme_controller, theme_palette
from je_file_tree.gui.treemap_widget import CATEGORY_COLOURS


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_primary_and_selected_palette_text_meets_minimum_contrast(theme) -> None:
    palette = theme_palette(theme)
    for ink, fill in ((QPalette.ColorRole.Text, QPalette.ColorRole.Base),
                      (QPalette.ColorRole.WindowText, QPalette.ColorRole.Window),
                      (QPalette.ColorRole.ButtonText, QPalette.ColorRole.Button),
                      (QPalette.ColorRole.HighlightedText, QPalette.ColorRole.Highlight)):
        assert contrast(palette.color(ink), palette.color(fill)) >= 4.5


@pytest.mark.parametrize('colour', [*CATEGORY_COLOURS.values(), *AGE_COLOURS.values(), UNKNOWN_AGE_COLOUR])
def test_chart_label_ink_is_readable_for_every_existing_category_and_age(colour) -> None:
    fill = QColor(colour)
    assert contrast(readable_ink(fill), fill) >= 4.5


def test_theme_menu_persists_translates_and_resets_native_style(window, qapp, sample_tree) -> None:
    controller = theme_controller()
    native_style, native_palette = controller.native_style, QApplication.palette()
    window.results.show_outcome(analyse(scan(sample_tree)))
    chart = window.results.charts.treemap
    chart.grab()
    assert chart._pixmap is not None
    window.theme_menu.actions_by_theme['light'].trigger()
    assert window.settings.value('theme') == 'light' and qapp.style().objectName() == 'fusion'
    assert chart._pixmap is None
    assert QApplication.palette().color(QPalette.ColorRole.Text).lightnessF() < .5
    chart.grab()
    window.theme_menu.actions_by_theme['dark'].trigger()
    assert chart._pixmap is None and QApplication.palette().color(QPalette.ColorRole.Text).lightnessF() > .5
    window.theme_menu.actions_by_theme['system'].trigger()
    assert qapp.style().objectName() == native_style
    assert QApplication.palette().color(QPalette.ColorRole.Text) == native_palette.color(QPalette.ColorRole.Text)
    window.change_language('zh-TW')
    assert window.theme_menu.title() == '主題' and window.theme_menu.actions_by_theme['light'].text() == '淺色'


def test_saved_theme_restores_before_the_window_and_unknown_values_fall_back(window, qapp) -> None:
    window.settings.setValue('theme', 'dark')
    other = create_window(window.settings)
    assert other.theme_menu.actions_by_theme['dark'].isChecked()
    assert QApplication.palette().color(QPalette.ColorRole.Text).lightnessF() > .5
    other.close()
    other.deleteLater()
    window.settings.setValue('theme', 'invalid')
    other = create_window(window.settings)
    assert other.theme_menu.actions_by_theme['system'].isChecked()
    assert theme_palette('system').resolveMask() == 0
    other.close()
    other.deleteLater()


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_bar_names_and_values_render_using_palette_ink(window, qapp, sample_tree, theme) -> None:
    window.results.show_outcome(analyse(scan(sample_tree)))
    window.pages.setCurrentIndex(RESULTS_PAGE)
    window.results.charts.set_mode(BARS)
    window.theme_menu.actions_by_theme[theme].trigger()
    chart = window.results.charts.bars
    # Exact-ink assertions require solid glyphs across DirectWrite and FreeType;
    # antialiasing can blend every pixel of a small glyph with its background.
    font = chart.font()
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    chart.setFont(font)
    window.show()
    qapp.processEvents()
    image = chart.grab().toImage()
    text = chart.palette().color(QPalette.ColorRole.Text).rgb()
    height = chart._row_height()
    name_pixels = {image.pixel(x, y) for x in range(25, 160) for y in range(3, height - 2)}
    value_pixels = {image.pixel(x, y) for x in range(image.width() - 140, image.width() - 8)
                    for y in range(3, height - 2)}
    assert text in name_pixels and text in value_pixels
    window.theme_menu.actions_by_theme['system'].trigger()
