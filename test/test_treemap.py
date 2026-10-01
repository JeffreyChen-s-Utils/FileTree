"""The squarified treemap layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.treemap import Rect, layout, squarify


def _inside(inner: Rect, outer: Rect, slack: float = 1e-6) -> bool:
    return (inner.x >= outer.x - slack and inner.y >= outer.y - slack
            and inner.x + inner.width <= outer.x + outer.width + slack
            and inner.y + inner.height <= outer.y + outer.height + slack)


def test_squarify_areas_are_proportional_and_fill_the_rectangle() -> None:
    area = Rect(0, 0, 600, 400)
    values = [6, 6, 4, 3, 2, 2, 1]
    rects = squarify(values, area)
    assert len(rects) == len(values)
    scale = area.area / sum(values)
    for value, rect in zip(values, rects, strict=True):
        assert rect.area == pytest.approx(value * scale)
        assert _inside(rect, area)
    assert sum(rect.area for rect in rects) == pytest.approx(area.area)


def test_squarify_keeps_rectangles_close_to_square() -> None:
    rects = squarify([1] * 16, Rect(0, 0, 400, 400))
    ratios = [max(rect.width / rect.height, rect.height / rect.width) for rect in rects]
    assert max(ratios) < 1.5


def test_squarify_handles_empty_input_and_zero_area() -> None:
    assert squarify([], Rect(0, 0, 10, 10)) == []
    assert all(rect.area == 0 for rect in squarify([1, 2], Rect(5, 5, 0, 10)))


def test_rect_helpers() -> None:
    rect = Rect(10, 20, 30, 40)
    assert rect.contains(10, 20) and not rect.contains(40, 20)
    assert rect.inset(5) == Rect(15, 25, 20, 30)
    assert Rect(0, 0, 4, 4).inset(10) == Rect(10, 10, 0, 0)


def test_layout_nests_children_inside_their_folder(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    area = Rect(0, 0, 800, 600)
    tiles = layout(root, area, min_side=1, padding=2)
    by_node = {id(tile.node): tile for tile in tiles}
    assert {tile.node.name for tile in tiles if tile.depth == 1} == {"big.bin", "photos", "code", "notes.txt"}
    for tile in tiles:
        assert _inside(tile.rect, area)
        parent = by_node.get(id(tile.node.parent))
        if parent is not None:
            assert tile.depth == parent.depth + 1
            assert _inside(tile.rect, parent.rect)
    top_area = sum(tile.rect.area for tile in tiles if tile.depth == 1)
    assert top_area == pytest.approx(area.area)


def _folder(name: str, sizes: list[int], parent: Node | None = None) -> Node:
    folder = Node(name, True, children=[], parent=parent)
    folder.children.extend(Node(f"f{index}", False, size=size, parent=folder) for index, size in enumerate(sizes))
    folder.size = sum(sizes)
    return folder


def test_small_entries_share_one_group_tile_and_the_limits_hold() -> None:
    root = _folder("root", [1000] + [1] * 999 + [0] * 5)
    tiles = layout(root, Rect(0, 0, 100, 100), min_side=5)
    found = [(tile.node.name, tile.grouped, tile.grouped_size) for tile in tiles]
    assert found == [("f0", 0, 0), ("root", 999, 999)], (
        "the 999 specks are one group tile of their folder; empty files count for nothing")
    assert tiles[1].rect.area == pytest.approx(10000 * 999 / 1999)
    assert all(min(tile.rect.width, tile.rect.height) >= 5 for tile in tiles), "no tile narrower than min_side"
    assert len(layout(root, Rect(0, 0, 2000, 2000), min_side=1, max_tiles=10)) == 10


def test_a_lone_small_entry_or_a_thin_group_is_left_out() -> None:
    lone = _folder("root", [1000, 1])
    assert [tile.node.name for tile in layout(lone, Rect(0, 0, 100, 100), min_side=5)] == ["f0"], (
        "one small entry is no group: its space stays empty")
    thin = _folder("root", [100000, 1, 1])
    assert [tile.node.name for tile in layout(thin, Rect(0, 0, 100, 100), min_side=5)] == ["f0"]


def test_a_folder_opens_only_when_an_entry_in_it_gets_a_tile_of_its_own() -> None:
    root = Node("root", True, children=[])
    crowded = _folder("crowded", [1] * 400, parent=root)
    mixed = _folder("mixed", [300] + [1] * 100, parent=root)
    root.children.extend([crowded, mixed])
    root.size = crowded.size + mixed.size
    tiles = layout(root, Rect(0, 0, 100, 100), min_side=8, padding=0)
    by_depth = {(tile.depth, tile.node.name, tile.grouped) for tile in tiles}
    assert (1, "crowded", 0) in by_depth
    assert not any(tile.node is crowded and tile.depth == 2 for tile in tiles), (
        "400 specks: the folder stays one tile instead of holding a single group tile")
    assert {(2, "f0", 0), (2, "mixed", 100)} <= by_depth


def test_layout_stops_at_max_depth(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert {tile.depth for tile in layout(root, Rect(0, 0, 800, 600), max_depth=1)} == {1}


def test_an_empty_folder_gives_no_tiles() -> None:
    assert layout(Node("empty", True, children=[]), Rect(0, 0, 100, 100)) == []


def test_a_header_strip_keeps_each_opened_folder_s_name_clear(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    tiles = layout(root, Rect(0, 0, 400, 300), padding=2.0, header=16.0)
    by_name = {tile.node.name: tile for tile in tiles}
    photos = by_name["photos"]
    assert photos.header == 16.0
    for name in ("a.jpg", "b.png"):
        assert by_name[name].rect.y >= photos.rect.y + 2.0 + 16.0 - 1e-9, "children start below the strip"
    assert by_name["big.bin"].header == 0.0, "files have no strip"
    assert all(tile.header == 0.0 for tile in layout(root, Rect(0, 0, 400, 300), max_depth=1, header=16.0)), (
        "a folder that is not opened has no strip")
    assert all(tile.header == 0.0 for tile in layout(root, Rect(0, 0, 400, 300)))
