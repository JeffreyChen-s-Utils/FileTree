"""Explain recorded recall/offline/compressed/sparse metadata without opening or downloading files."""

from __future__ import annotations

import heapq
import threading
from dataclasses import dataclass

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import unpack_snapshot

_SPARSE, _COMPRESSED, _OFFLINE = 0x200, 0x800, 0x1000
_RECALL_OPEN, _RECALL_DATA = 0x40000, 0x400000
_FLAGS = ((_RECALL_OPEN | _RECALL_DATA, "recall"), (_OFFLINE, "offline"),
          (_COMPRESSED, "compressed"), (_SPARSE, "sparse"))


@dataclass(frozen=True, slots=True)
class SpecialEntry:
    """Recorded file states; logical size is full content length, never predicted downloaded allocation."""

    node: Node
    states: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SpecialFiles:
    """Largest bounded matching rows plus complete matching counts and unavailable metadata count."""

    rows: list[SpecialEntry]
    count: int
    logical: int
    allocated: int
    unknown: int
    incomplete: bool


def special_files(root: Node, *, limit: int = 1000,
                  cancel: threading.Event | None = None) -> SpecialFiles | None:
    """Survey stored snapshots on a worker; lower allocation without flags keeps its cause unknown."""
    if limit < 1:
        raise ValueError("limit must be positive")
    count = logical = allocated = unknown = 0
    incomplete = False
    heap: list[tuple[int, int, SpecialEntry]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if cancel is not None and cancel.is_set():
            return None
        incomplete |= bool(node.error)
        if node.is_link:
            continue
        if node.is_dir:
            give_way()
            stack.extend(node.children)
            continue
        if node.error or node.snapshot is None:
            unknown += 1
            continue
        info = unpack_snapshot(node.snapshot)
        states = tuple(state for mask, state in _FLAGS if info.attributes & mask)
        if not states and node.allocated < node.size:
            states = ("allocation_low",)
        if not states:
            continue
        count += 1
        logical += node.size
        allocated += node.allocated
        entry = (node.size, count, SpecialEntry(node, states))
        if len(heap) < limit:
            heapq.heappush(heap, entry)
        elif entry[:2] > heap[0][:2]:
            heapq.heapreplace(heap, entry)
    return SpecialFiles([entry for _size, _order, entry in sorted(heap, reverse=True)],
                        count, logical, allocated, unknown, incomplete)
