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


def test_layout_leaves_out_what_is_too_small_and_respects_the_limits() -> None:
    root = Node("root", True, children=[])
    for index in range(1000):
        root.children.append(Node(f"f{index}", False, size=1000 if index == 0 else 1, parent=root))
    root.size = sum(child.size for child in root.children)
    tiles = layout(root, Rect(0, 0, 100, 100), min_side=5)
    assert [tile.node.name for tile in tiles] == ["f0"]
    assert len(layout(root, Rect(0, 0, 2000, 2000), min_side=1, max_tiles=10)) == 10


def test_layout_stops_at_max_depth(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert {tile.depth for tile in layout(root, Rect(0, 0, 800, 600), max_depth=1)} == {1}


def test_an_empty_folder_gives_no_tiles() -> None:
    assert layout(Node("empty", True, children=[]), Rect(0, 0, 100, 100)) == []
