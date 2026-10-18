"""Light/dark palettes keep labels readable and reset cached/native rendering correctly."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QStyle, QWidget

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.scanner import scan
from je_file_tree.gui.age_colours import AGE_COLOURS, UNKNOWN_AGE_COLOUR
from je_file_tree.gui.app import create_window
from je_file_tree.gui.charts import BARS
from je_file_tree.gui.colours import contrast, readable_ink
from je_file_tree.gui.main_window import RESULTS_PAGE
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui import themes
from je_file_tree.gui.fluent_style import FluentStyle, tokens_for
from je_file_tree.gui.themes import NATIVE, theme_controller, theme_palette
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


def test_theme_menu_persists_translates_and_applies_fluent_themes(window, qapp, sample_tree) -> None:
    controller = theme_controller()
    window.results.show_outcome(analyse(scan(sample_tree)))
    chart = window.results.charts.treemap
    chart.grab()
    assert chart._pixmap is not None
    window.theme_menu.actions_by_theme['dark'].trigger()
    assert window.settings.value('theme') == 'dark' and isinstance(controller.style, FluentStyle)
    assert controller.resolved == 'dark' and 'QPushButton' in qapp.styleSheet()
    assert chart._pixmap is None and QApplication.palette().color(QPalette.ColorRole.Text).lightnessF() > .5
    chart.grab()
    window.theme_menu.actions_by_theme['light'].trigger()
    assert chart._pixmap is None and QApplication.palette().color(QPalette.ColorRole.Text).lightnessF() < .5
    chart.grab()
    style = controller.style
    window.theme_menu.actions_by_theme['light'].trigger()  # the same look: nothing is repolished
    assert controller.style is style and chart._pixmap is not None
    window.theme_menu.actions_by_theme['system'].trigger()
    expected = 'dark' if qapp.styleHints().colorScheme() == Qt.ColorScheme.Dark else 'light'
    assert controller.resolved == expected and isinstance(controller.style, FluentStyle)
    window.change_language('zh-TW')
    assert window.theme_menu.title() == '主題' and window.theme_menu.actions_by_theme['light'].text() == '淺色'


def test_system_theme_keeps_the_native_style_under_high_contrast(window, qapp, monkeypatch) -> None:
    controller = theme_controller()
    monkeypatch.setattr(themes, '_high_contrast', lambda _hints: True)
    try:
        controller.apply('system')
        assert controller.resolved == NATIVE and qapp.styleSheet() == ''
        assert qapp.style().objectName() == controller.native_style
        controller.apply('dark')  # an explicit choice is still honoured
        assert controller.resolved == 'dark' and isinstance(controller.style, FluentStyle)
    finally:
        monkeypatch.undo()
        controller.apply('system')


def test_platform_scheme_changes_reapply_only_the_system_theme(window, qapp, monkeypatch) -> None:
    controller = theme_controller()
    applied = []
    try:
        controller.apply('light')
        monkeypatch.setattr(controller, 'apply', applied.append)
        controller._platform_changed(Qt.ColorScheme.Dark)
        assert applied == []
        controller.choice = 'system'
        controller._platform_changed(Qt.ColorScheme.Dark)
        assert applied == ['system']
    finally:
        monkeypatch.undo()
        controller.apply('system')


@pytest.mark.parametrize('scheme', ['light', 'dark'])
@pytest.mark.parametrize('accent', [None, '#0067c0', '#f38064', '#ffb900', '#ffffff', '#000000', '#00cc6a', '#8764b8'])
def test_tokens_keep_wcag_contrast_for_any_platform_accent(scheme, accent) -> None:
    tokens = tokens_for(scheme, accent)
    colour = {name: QColor(getattr(tokens, name)) for name in tokens.__slots__ if name != 'scheme'}
    assert contrast(colour['accent'], colour['card']) >= 3  # controls and selection markers
    assert contrast(colour['link'], colour['card']) >= 4.5
    assert contrast(colour['on_accent'], colour['accent']) >= 4.5
    for surface in ('window', 'card', 'control', 'selection'):
        assert contrast(colour['text'], colour[surface]) >= 4.5, surface
    for surface in ('window', 'card', 'subtle'):
        assert contrast(colour['text_secondary'], colour[surface]) >= 4.5, surface
        for status in ('success', 'caution', 'link'):  # state chips sit on the subtle surface
            assert contrast(colour[status], colour[surface]) >= 4.5, (status, surface)


def test_widgets_carry_no_style_sheet_of_their_own(window, qapp, sample_tree) -> None:
    window.results.show_outcome(analyse(scan(sample_tree)))
    styled = [type(widget).__name__ for widget in window.findChildren(QWidget) if widget.styleSheet()]
    assert styled == []


def test_parent_fonts_still_reach_children_under_the_style_sheet(window, qapp) -> None:
    theme_controller().apply('dark')
    try:
        parent = QWidget()
        plain, caption = QLabel('plain', parent), QLabel('caption', parent)
        caption.setProperty('role', 'caption')
        larger = QFont(parent.font())
        larger.setPointSizeF(24)
        parent.setFont(larger)  # as a language change does with its font
        assert plain.font().pointSizeF() == caption.font().pointSizeF() == 24
        parent.deleteLater()
    finally:
        theme_controller().apply('system')


def test_fluent_style_draws_its_own_close_and_clear_glyphs(qapp) -> None:
    style = FluentStyle(tokens_for('dark'))
    for pixmap in (QStyle.StandardPixmap.SP_TabCloseButton, QStyle.StandardPixmap.SP_LineEditClearButton):
        image = style.standardIcon(pixmap).pixmap(16, 16).toImage()
        inks = {image.pixelColor(x, y).name() for x in range(16) for y in range(16)
                if image.pixelColor(x, y).alpha() > 200}
        assert inks and all(QColor(ink).saturationF() < .1 for ink in inks)  # neutral grey, never Fusion's red


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
    assert theme_palette('system').resolveMask() == 0 and theme_palette(NATIVE).resolveMask() == 0
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
