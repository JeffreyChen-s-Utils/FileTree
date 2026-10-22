"""Run-time line icons follow the palette in the sidebar and tool bar (U-20261018-85)."""

from PySide6.QtGui import QColor, QIcon, QPalette
import pytest

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.scanner import scan
from je_file_tree.gui.fluent_icons import NAMES, icon
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.themes import theme_controller


def _drawn_in(qicon: QIcon, colour: str, mode: QIcon.Mode = QIcon.Mode.Normal, size: int = 32) -> bool:
    """Whether the icon has ink and every mostly opaque pixel is ``colour`` (within edge rounding)."""
    image = qicon.pixmap(size, size, mode).toImage()
    target = QColor(colour)
    inks = [image.pixelColor(x, y) for x in range(size) for y in range(size) if image.pixelColor(x, y).alpha() >= 160]
    return bool(inks) and all(max(abs(ink.red() - target.red()), abs(ink.green() - target.green()),
                                  abs(ink.blue() - target.blue())) <= 2 for ink in inks)


@pytest.mark.parametrize("name", NAMES)
def test_every_icon_draws_only_in_its_colours(qapp, name):
    drawn = icon(name, QColor("#123456"), QColor("#a0a0a0"))
    assert _drawn_in(drawn, "#123456")
    assert _drawn_in(drawn, "#a0a0a0", QIcon.Mode.Disabled)


def test_sidebar_and_chooser_icons_follow_the_theme(window, qapp, sample_tree):
    results = window.results
    results.show_outcome(analyse(scan(sample_tree)))
    navigation = results.navigation
    rows = range(navigation.list.count())
    assert all(not navigation.list.item(row).icon().isNull() for row in rows)
    assert all(not navigation.combo.itemIcon(row).isNull() for row in range(navigation.combo.count()))
    controller = theme_controller()
    try:
        for theme in ("dark", "light"):
            controller.apply(theme)
            qapp.processEvents()
            ink = navigation.palette().color(QPalette.ColorRole.WindowText).name()
            assert _drawn_in(navigation.list.item(0).icon(), ink)
            assert _drawn_in(navigation.combo.itemIcon(0), ink)
            window_ink = window.palette().color(QPalette.ColorRole.WindowText).name()
            assert _drawn_in(window._actions["open"].icon(), window_ink)
    finally:
        controller.apply("system")


def test_tool_bar_actions_show_icons_beside_their_text(window):
    for key in ("open", "rescan", "stop", "help"):
        assert not window._actions[key].icon().isNull(), key
