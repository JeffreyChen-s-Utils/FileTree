"""Squarified treemap layout (Bruls, Huizing and van Wijk, 2000).

Each entry becomes a rectangle whose area is proportional to its size, laid
out so the rectangles stay as close to squares as possible, which makes sizes
easy to compare by eye. The layout is pure arithmetic; drawing is up to the GUI.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from file_tree.core.node import Node


@dataclass(frozen=True, slots=True)
class Rect:
    """An axis-aligned rectangle."""

    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        """Width times height."""
        return self.width * self.height

    def contains(self, x: float, y: float) -> bool:
        """Whether the point lies inside (left and top edges included)."""
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def inset(self, amount: float) -> Rect:
        """This rectangle shrunk by ``amount`` on every side (never below zero size)."""
        width = max(0.0, self.width - 2 * amount)
        height = max(0.0, self.height - 2 * amount)
        return Rect(self.x + amount, self.y + amount, width, height)


@dataclass(frozen=True, slots=True)
class Tile:
    """One laid-out entry: its node, its rectangle, and how deep below the laid-out root it is."""

    node: Node
    rect: Rect
    depth: int


def squarify(values: Sequence[float], rect: Rect) -> list[Rect]:
    """Rectangles tiling ``rect``, one per value, with areas proportional to the values.

    ``values`` must be sorted largest first and every value must be positive.
    The rectangles come back in the same order as the values.
    """
    total = sum(values)
    if not values or total <= 0 or rect.area <= 0:
        return [Rect(rect.x, rect.y, 0.0, 0.0) for _ in values]
    scale = rect.area / total
    areas = [value * scale for value in values]
    rects: list[Rect] = []
    x, y, width, height = rect.x, rect.y, rect.width, rect.height
    start = 0
    while start < len(areas):
        end = _row_end(areas, start, min(width, height))
        row = areas[start:end]
        row_area = sum(row)
        if width >= height:
            column = row_area / height if height else 0.0
            offset = y
            for area in row:
                item = area / column if column else 0.0
                rects.append(Rect(x, offset, column, item))
                offset += item
            x += column
            width -= column
        else:
            band = row_area / width if width else 0.0
            offset = x
            for area in row:
                item = area / band if band else 0.0
                rects.append(Rect(offset, y, item, band))
                offset += item
            y += band
            height -= band
        start = end
    return rects


def _row_end(areas: list[float], start: int, side: float) -> int:
    """Where the row beginning at ``start`` should end: add items while the worst aspect ratio improves."""
    total = areas[start]
    worst = _worst_ratio(total, areas[start], areas[start], side)
    end = start + 1
    while end < len(areas):
        candidate_total = total + areas[end]
        candidate = _worst_ratio(candidate_total, areas[start], areas[end], side)
        if candidate > worst:
            break
        total, worst = candidate_total, candidate
        end += 1
    return end


def _worst_ratio(total: float, largest: float, smallest: float, side: float) -> float:
    """The worst aspect ratio in a row of areas summing to ``total`` laid along ``side``."""
    if total <= 0 or smallest <= 0 or side <= 0:
        return float("inf")
    side_squared = side * side
    total_squared = total * total
    return max(side_squared * largest / total_squared, total_squared / (side_squared * smallest))


def layout(root: Node, rect: Rect, *, max_depth: int | None = None, min_side: float = 3.0,
           padding: float = 2.0, max_tiles: int = 20000) -> list[Tile]:
    """Tiles for everything beneath ``root`` inside ``rect``, parents before their children.

    Entries whose rectangle would be narrower than ``min_side`` are left out
    (their space stays empty), folders are nested ``padding`` inside their own
    tile, and layout stops at ``max_depth`` levels or ``max_tiles`` tiles, so the
    cost stays bounded however large the tree is.
    """
    tiles: list[Tile] = []
    queue: deque[tuple[Node, Rect, int]] = deque([(root, rect, 1)])
    while queue and len(tiles) < max_tiles:
        folder, area, depth = queue.popleft()
        for child, child_rect in _place_children(folder, area, min_side):
            tile = Tile(child, child_rect, depth)
            tiles.append(tile)
            if len(tiles) >= max_tiles:
                break
            inner = child_rect.inset(padding)
            if (child.is_dir and child.children and (max_depth is None or depth < max_depth)
                    and min(inner.width, inner.height) >= min_side):
                queue.append((child, inner, depth + 1))
    return tiles


def _place_children(folder: Node, area: Rect, min_side: float) -> list[tuple[Node, Rect]]:
    """Squarify ``folder``'s non-empty children into ``area``, dropping those too small to see.

    The ones too small to see are laid out together as one unnamed block, so
    the others keep their true proportions.
    """
    if folder.size <= 0 or area.area <= 0:
        return []
    min_area = min_side * min_side
    scale = area.area / folder.size
    shown = [child for child in folder.children if child.size * scale >= min_area]
    entries: list[tuple[int, Node | None]] = [(child.size, child) for child in shown]
    rest = folder.size - sum(child.size for child in shown)
    if rest > 0:
        entries.append((rest, None))
    entries.sort(key=_entry_size, reverse=True)  # stays right after a deletion shrank a folder
    rects = squarify([size for size, _ in entries], area)
    return [(child, rect) for (_, child), rect in zip(entries, rects, strict=True)
            if child is not None and min(rect.width, rect.height) >= min_side]


def _entry_size(entry: tuple[int, Node | None]) -> int:
    return entry[0]
