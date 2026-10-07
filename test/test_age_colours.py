"""Chart palettes share a frozen modification-age reference and explicit unknown dates."""

import math

import pytest

from je_file_tree.core.analysis import AGES
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.sunburst import Segment
from je_file_tree.gui.age_colours import AGE_COLOURS, UNKNOWN_AGE_COLOUR, age_colour, age_text_colour
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.results_view import ResultsView
from je_file_tree.gui.treemap_widget import BY_AGE, BY_FOLDER, BY_TYPE

_NOW = 1_800_000_000


@pytest.mark.parametrize("age,days", list(zip(AGES, (10, 60, 250, 500, 900), strict=True)))
def test_modified_age_shades_are_identical_for_tiles_and_rings(qapp, age, days) -> None:
    node = Node("file.txt", False, size=5, modified=_NOW - days * 86400)
    view = ResultsView()
    view.charts.set_age_reference(_NOW)
    view.charts.set_colour_mode(BY_AGE)
    tile = view.charts.treemap._colour(node, 1)
    ring = view.charts.sunburst._colour(Segment(node, 1, 0, 1))
    assert tile.name() == ring.name() == AGE_COLOURS[age]
    view.deleteLater()


@pytest.mark.parametrize("modified", [0, -1, math.nan, math.inf, _NOW + 1])
def test_unusable_dates_are_not_presented_as_old_files(modified) -> None:
    assert age_colour(Node("file", False, modified=modified), _NOW).name() == UNKNOWN_AGE_COLOUR


def test_labels_switch_ink_for_light_and_dark_age_shades() -> None:
    recent = age_colour(Node("new", False, modified=_NOW), _NOW)
    old = age_colour(Node("old", False, modified=_NOW - 1000 * 86400), _NOW)
    assert age_text_colour(recent).name() != age_text_colour(old).name()


def test_shared_colour_preference_and_age_legend_follow_chart_switches(qapp, tmp_path) -> None:
    view = ResultsView()
    view.apply_chart_settings({"chart_mode": "sunburst", "treemap_colours": BY_AGE})
    assert view.charts.treemap.colour_mode == view.charts.sunburst.colour_mode == BY_AGE
    assert not view._legend.isHidden() and not view._colours_combo.isHidden()
    assert view._levels_combo.isHidden()
    for age in AGES:
        assert tr("age_" + age).replace(" ", "\u00a0") in view._legend.text().replace("\u2060", "")
    assert view._legend.toolTip() == tr("age_colour_tip")
    view.set_chart_mode("bars")
    assert view._legend.toolTip() == ""
    view.set_chart_mode("treemap")
    assert view._legend.toolTip() == tr("age_colour_tip")
    view.charts.set_colour_mode(BY_FOLDER)
    view._update_chart_controls()
    assert view._legend.isHidden()
    view.charts.set_colour_mode(BY_TYPE)
    view._update_chart_controls()
    assert not view._legend.isHidden()
    view.charts.set_view_root(scan(tmp_path).root)
    view.charts.treemap.grab()
    view.charts.sunburst.grab()
    view.deleteLater()
