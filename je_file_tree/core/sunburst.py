"""Sunburst layout: the folder shown in the centre, each deeper level as a ring around it.

Every entry gets the part of its parent's arc that its size is of the parent's size, so the
angles add up level after level and the rings show the whole hierarchy at once. Angles are
fractions of the full circle (0 to 1, clockwise from twelve o'clock); drawing is up to the GUI.
The cost stays bounded: arcs thinner than ``min_span`` are left out (the entries of a folder are
taken largest first, so the rest are thinner still) and layout stops at ``max_segments``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from je_file_tree.core.node import Node


@dataclass(frozen=True, slots=True)
class Segment:
    """One entry's arc: its node, its ring (1 = around the centre) and where its arc starts and how far it spans."""

    node: Node
    depth: int
    start: float
    span: float

    def contains(self, fraction: float) -> bool:
        """Whether the angle ``fraction`` (0 to 1) falls in this arc."""
        return self.start <= fraction < self.start + self.span


def layout(root: Node, *, max_depth: int = 4, min_span: float = 0.002, max_segments: int = 5000) -> list[Segment]:
    """The arcs for everything beneath ``root`` down to ``max_depth`` rings, parents before their children."""
    segments: list[Segment] = []
    queue: deque[tuple[Node, float, float, int]] = deque([(root, 0.0, 1.0, 1)])
    while queue and len(segments) < max_segments:
        folder, start, span, depth = queue.popleft()
        if folder.size <= 0:
            continue
        offset = start
        for child in sorted(folder.children, key=_size, reverse=True):
            child_span = span * child.size / folder.size
            if child_span < min_span or len(segments) >= max_segments:
                break
            segments.append(Segment(child, depth, offset, child_span))
            if child.is_dir and not child.is_link and child.children and depth < max_depth:
                queue.append((child, offset, child_span, depth + 1))
            offset += child_span
    return segments


def segment_at(segments: list[Segment], depth: int, fraction: float) -> Segment | None:
    """The arc on ring ``depth`` at the angle ``fraction``, if any."""
    return next((segment for segment in segments if segment.depth == depth and segment.contains(fraction)), None)


def _size(node: Node) -> int:
    return node.size
