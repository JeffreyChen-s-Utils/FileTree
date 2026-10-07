"""Bounded largest matching files and their containing folders, in one cancellable pass."""

from __future__ import annotations

import heapq
import threading
from collections.abc import Callable
from dataclasses import dataclass

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way


@dataclass(frozen=True, slots=True)
class TypeLocation:
    """Bytes and files of the selected extension directly inside one folder (no overlap)."""

    folder: Node
    size: int
    count: int


@dataclass(frozen=True, slots=True)
class TypeMatches:
    """Largest file/folder lists plus the total matching logical bytes before truncation."""

    files: list[Node]
    folders: list[TypeLocation]
    total: int


def type_locations(root: Node, keep: Callable[[Node], bool], limit: int = 1000,
                   cancel: threading.Event | None = None) -> TypeMatches | None:
    """Keep at most limit files/folders, yielding per folder; links are excluded and reads use scan data."""
    stack = [root]
    files: list[tuple[int, int, Node]] = []
    folders: list[tuple[int, int, TypeLocation]] = []
    total, serial = 0, 0
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        folder = stack.pop()
        give_way()
        size, count = 0, 0
        for node in folder.children:
            if cancel is not None and cancel.is_set():
                return None
            if node.is_link:
                continue
            if node.is_dir:
                stack.append(node)
            elif keep(node):
                size += node.size
                count += 1
                serial += 1
                _retain(files, (node.size, serial, node), limit)
        if count:
            total += size
            serial += 1
            _retain(folders, (size, serial, TypeLocation(folder, size, count)), limit)
    return TypeMatches([entry[2] for entry in sorted(files, reverse=True)],
                       [entry[2] for entry in sorted(folders, reverse=True)], total)


def _retain(heap: list, entry: tuple, limit: int) -> None:
    if limit <= 0:
        return
    if len(heap) < limit:
        heapq.heappush(heap, entry)
    elif entry[:2] > heap[0][:2]:
        heapq.heapreplace(heap, entry)
