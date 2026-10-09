"""Squarified treemap layout (Bruls, Huizing and van Wijk, 2000).

Each entry becomes a rectangle whose area is proportional to its size, laid
out so the rectangles stay as close to squares as possible, which makes sizes
easy to compare by eye. The layout is pure arithmetic; drawing is up to the GUI.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NamedTuple

from je_file_tree.core.node import Node


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
    """One laid-out entry: its node, its rectangle, and how deep below the laid-out root it is.

    ``header`` is the height of the strip at the top of a folder's tile kept free for its name
    (0 when the folder got none); its children are laid out below it.

    A *group* tile (``grouped`` > 0) stands for that many entries of the folder ``node`` that were
    each too small for a tile of their own, ``grouped_size`` bytes together; it is not ``node`` itself.
    """

    node: Node
    rect: Rect
    depth: int
    header: float = 0.0
    grouped: int = 0
    grouped_size: int = 0


class _Group(NamedTuple):
    """A folder's entries too small for tiles of their own: how many, and their size together."""

    count: int
    size: int


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


def layout(root: Node, rect: Rect, *, max_depth: int | None = None, min_side: float = 3.0,  # noqa: PLR0913
           padding: float = 2.0, max_tiles: int = 20000, header: float = 0.0) -> list[Tile]:
    """Tiles for everything beneath ``root`` inside ``rect``, parents before their children.

    No tile is narrower than ``min_side``: the entries of a folder too small for
    a tile that size share one group tile (see ``Tile``), so many small files
    make one block rather than a mass of specks, and a group or an entry whose
    rectangle still comes out narrower is left out (its space stays empty).
    Folders are nested ``padding`` inside their own tile and open only when at
    least one of their entries gets a tile of its own; layout stops at
    ``max_depth`` levels or ``max_tiles`` tiles, so the cost stays bounded
    however large the tree is. With ``header``, an opened folder keeps a strip
    that high at its top for its name, when its tile is at least three strips
    wide and tall.
    """
    tiles: list[Tile] = []
    queue: deque[tuple[Node, Rect, int]] = deque([(root, rect, 1)])
    while queue and len(tiles) < max_tiles:
        folder, area, depth = queue.popleft()
        deeper = max_depth is None or depth < max_depth
        for child, child_rect, group in _place_children(folder, area, min_side):
            if group is not None:
                tiles.append(Tile(folder, child_rect, depth, grouped=group.count, grouped_size=group.size))
                opened = None
            else:
                opened = _opened(child, child_rect.inset(padding), header, min_side) if deeper else None
                tiles.append(Tile(child, child_rect, depth, opened[0] if opened else 0.0))
            if len(tiles) >= max_tiles:
                break
            if opened is not None:
                queue.append((child, opened[1], depth + 1))
    return tiles


def _opened(node: Node, inner: Rect, header: float, min_side: float) -> tuple[float, Rect] | None:
    """The header strip and the area for ``node``'s children inside ``inner``, or None when it stays one tile.

    A folder stays one tile when it is empty, has too little room, or when every entry in it would
    be too small for a tile of its own: a single group tile filling it would only repeat the folder.
    """
    if not node.is_dir or not node.children or node.accounted_size <= 0:
        return None
    strip = _strip(inner, header)
    body = Rect(inner.x, inner.y + strip, inner.width, inner.height - strip)
    if min(body.width, body.height) < min_side:
        return None
    largest = max(child.accounted_size for child in node.children)
    if largest * body.area / node.accounted_size < min_side * min_side:
        return None
    return strip, body


def _strip(inner: Rect, header: float) -> float:
    """The header strip an opened folder keeps: ``header`` when the folder is at least three strips wide and tall."""
    return header if header > 0 and min(inner.width, inner.height) >= 3 * header else 0.0


def _place_children(folder: Node, area: Rect, min_side: float) -> list[tuple[Node, Rect, _Group | None]]:
    """Squarify ``folder``'s non-empty children into ``area``: (child, rectangle, None) for each shown child.

    The children too small for a tile of their own are laid out together as
    one block, so the others keep their true proportions; it comes back as
    (folder, rectangle, group) when there are at least two of them.
    Rectangles narrower than ``min_side`` are dropped.
    """
    if folder.accounted_size <= 0 or area.area <= 0:
        return []
    min_area = min_side * min_side
    scale = area.area / folder.accounted_size
    entries: list[tuple[int, Node | None]] = []
    count = rest = 0
    for child in folder.children:
        if child.accounted_size * scale >= min_area:
            entries.append((child.accounted_size, child))
        elif child.accounted_size > 0:
            count += 1
            rest += child.accounted_size
    if rest > 0:
        entries.append((rest, None))
    entries.sort(key=_entry_size, reverse=True)  # stays right after a deletion shrank a folder
    rects = squarify([size for size, _ in entries], area)
    placed: list[tuple[Node, Rect, _Group | None]] = []
    for (_, child), rect in zip(entries, rects, strict=True):
        if min(rect.width, rect.height) < min_side:
            continue
        if child is not None:
            placed.append((child, rect, None))
        elif count > 1:
            placed.append((folder, rect, _Group(count, rest)))
    return placed


def _entry_size(entry: tuple[int, Node | None]) -> int:
    return entry[0]
