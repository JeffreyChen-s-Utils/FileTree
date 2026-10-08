"""Conservative file-data recovery estimates for a reviewed selection."""

from __future__ import annotations

import shutil
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field

from je_file_tree.core.node import Node, outermost
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import unpack_snapshot

_ELSEWHERE = 0x1000 | 0x40000 | 0x400000


@dataclass(frozen=True, slots=True)
class Savings:
    """Logical named bytes, unique allocation, recovery range and current OS-reported free space.

    The recovery range concerns file data after emptying Trash, not immediate free space. Filesystem
    snapshots, shared extents and directory metadata cannot be measured from a scan; no positive lower
    bound is promised. Windows ordinary allocation is cluster-rounded; macOS allocation does not
    identify APFS shared extents or retained snapshots. Both remain explicitly uncertain.
    """

    logical: int
    allocated: int
    recoverable_min: int
    recoverable_max: int | None
    free_now: int | None
    uncertain: bool


def estimate_savings(nodes: Sequence[Node], *, root: Node | None = None,
                     cancel: threading.Event | None = None) -> Savings | None:
    """Estimate on a worker; collapse overlaps and release hard-link data only if every name is selected."""
    chosen = outermost(nodes)
    counter = _Counter()
    for selected in chosen:
        for node in selected.iter_nodes():
            if cancel is not None and cancel.is_set():
                return None
            if node.is_dir:
                give_way()
            if node.error is not None:
                counter.unknown = True
            if node.is_dir or node.is_link:
                continue
            counter.add_file(node)
    for selected_names, total_names, size in counter.links.values():
        counter.allocated += size
        if selected_names >= total_names:
            counter.recoverable += size
    path = root.path if root is not None else chosen[0].path if chosen else None
    try:
        free_now = shutil.disk_usage(path).free if path is not None else None
    except OSError:
        free_now = None
    return Savings(counter.logical, counter.allocated, 0, None if counter.unknown else counter.recoverable,
                   free_now, counter.uncertain or counter.unknown)


@dataclass(slots=True)
class _Counter:
    logical: int = 0
    allocated: int = 0
    recoverable: int = 0
    unknown: bool = False
    uncertain: bool = field(default_factory=lambda: sys.platform in ("win32", "darwin"))
    links: dict[tuple[int, int], list[int]] = field(default_factory=dict)

    def add_file(self, node: Node) -> None:
        self.logical += node.size
        if node.snapshot is None:
            self.unknown = True
            self.allocated += node.allocated
            return
        info = unpack_snapshot(node.snapshot)
        if not info.inode or not info.links:
            self.unknown = True
        if info.attributes & _ELSEWHERE:
            self.uncertain = True
        if info.links > 1 and info.inode:
            counts = self.links.setdefault(info.identity, [0, info.links, node.allocated])
            counts[0] += 1
            counts[1] = max(counts[1], info.links)
            counts[2] = max(counts[2], node.allocated)
        else:
            self.allocated += node.allocated
            self.recoverable += node.allocated
