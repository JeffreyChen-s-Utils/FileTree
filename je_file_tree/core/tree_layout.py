"""Bounded, iterative layout for a folder hierarchy diagram (no Qt dependency)."""

from __future__ import annotations

import heapq
from collections.abc import Mapping
from dataclasses import dataclass

from je_file_tree.core.node import Node


MAX_VISIBLE = 240
PAGE_SIZE = 10


@dataclass(frozen=True, slots=True)
class DiagramItem:
    """One visible folder or an expandable group of its smaller siblings."""

    node: Node | None
    parent: int | None
    depth: int
    row: int
    hidden_count: int = 0
    hidden_size: int = 0


def layout(root: Node | None, *, expanded: frozenset[int] = frozenset(),
           visible_counts: Mapping[int, int] | None = None,
           page_offsets: Mapping[int, int] | None = None,
           max_visible: int = MAX_VISIBLE) -> list[DiagramItem]:
    """Return at most ``max_visible`` rows; folders expand by identity, never recursively.

    The root is always open. Other folders open only when listed in ``expanded``.
    ``visible_counts`` pages wide sibling lists; ``page_offsets`` advances them
    once the global node cap is reached. The remaining folders become a synthetic
    group row. Files are represented by their parent folder's totals.
    """
    if root is None or max_visible < 1:
        return []
    counts = visible_counts or {}
    offsets = page_offsets or {}
    result: list[DiagramItem] = []
    pending: list[tuple[Node | None, int | None, int, int, int]] = [(root, None, 0, 0, 0)]
    while pending and len(result) < max_visible:
        node, parent, depth, hidden_count, hidden_size = pending.pop()
        index = len(result)
        result.append(DiagramItem(node, parent, depth, index, hidden_count, hidden_size))
        if node is None or node.error is not None or (node is not root and id(node) not in expanded):
            continue
        limit = max(1, counts.get(id(node), PAGE_SIZE))
        offset = max(0, offsets.get(id(node), 0))
        # Reserve one row for the summary if more siblings exist. Pending rows
        # already own their slots; this also bounds a very deep expanded branch.
        free = max_visible - len(result) - len(pending)
        if free <= 0:
            continue
        folders = (child for child in node.children if child.is_dir and not child.is_link)
        top = heapq.nlargest(offset + min(limit, max(0, free - 1)), folders,
                             key=lambda child: child.allocated)
        shown = top[offset:]
        total = 0
        total_size = 0
        for child in node.children:
            if child.is_dir and not child.is_link:
                total += 1
                total_size += child.allocated
        hidden = total - len(top)
        remainder = total_size - sum(child.allocated for child in top)
        if hidden and free > len(shown):
            pending.append((None, index, depth + 1, hidden, remainder))
        for child in reversed(shown):
            pending.append((child, index, depth + 1, 0, 0))
    return result
