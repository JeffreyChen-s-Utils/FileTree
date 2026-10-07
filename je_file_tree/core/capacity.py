"""Compare known file allocation with OS capacity, without filling unknown buckets with zero."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field

from je_file_tree.core.coverage import Coverage, coverage_of
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot


@dataclass(frozen=True, slots=True)
class CapacityLedger:
    """An estimated ledger, not a filesystem audit or a promise of recoverable space.

    Recycle Bin allocation seen is included in unique allocation. Unaccounted is only computed for a
    complete whole-volume scan with known identities and compatible OS totals. Metadata, omitted data
    and other mounted volumes have no measured byte total. Values refer to different instants; live
    filesystem changes, shared extents, snapshots and Windows cluster estimates affect the remainder.
    """

    total: int | None
    used: int | None
    free: int | None
    unavailable_free: int | None
    named_allocated: int
    unique_allocated: int | None
    hard_link_overcount: int | None
    recycle_bin_seen: int | None
    recycle_bin_complete: bool
    mounted_folders: int
    foreign_allocated_seen: int | None
    coverage: Coverage
    status: str
    unaccounted: int | None
    measured_at: float
    metadata_bytes: int | None = None
    omitted_bytes: int | None = None
    other_volumes_bytes: int | None = None


def capacity_ledger(root: Node, *, partial: bool = False) -> CapacityLedger:
    """Survey on a worker; report why a folder, interrupted or unreadable scan cannot reconcile a volume."""
    coverage = coverage_of(root)
    counts = _Counts()
    root_info = unpack_snapshot(root.snapshot) if root.snapshot is not None else None
    device = root_info.device if root_info is not None else None
    stack = [(root, _is_trash(root.path))]
    while stack:
        node, in_bin = stack.pop()
        give_way()
        info = unpack_snapshot(node.snapshot) if node.snapshot is not None else None
        counts.unknown |= info is None or not info.inode
        if in_bin:
            counts.bin_found = True
            counts.bin_complete &= node.error is None and not node.is_link
        parent_info = unpack_snapshot(node.parent.snapshot) if node.parent and node.parent.snapshot else None
        if info is not None and parent_info is not None and info.device != parent_info.device:
            counts.mounts += 1
        if not node.is_link:
            for child in node.children:
                if child.is_dir:
                    stack.append((child, in_bin or _trash_node(child)))
                elif not child.is_link:
                    counts.add(child, device, in_bin)
    counts.finish()
    total, used, free, unavailable = _usage(root.path)
    status = _status(root, coverage, counts.unknown or root_info is None, partial)
    if total is None:
        status = "capacity_unavailable"
    elif status == "estimated" and used is not None and counts.unique > used:
        status = "allocation_exceeds_used"
    remainder = used - counts.unique if status == "estimated" and used is not None else None
    known = not counts.unknown and root_info is not None
    return CapacityLedger(total, used, free, unavailable, counts.named, counts.unique if known else None,
                          counts.named - counts.unique if known else None, counts.bin_seen if known else None,
                          counts.bin_found and counts.bin_complete, counts.mounts, counts.foreign if known else None,
                          coverage, status, remainder, time.time())


def _usage(path: str) -> tuple[int | None, int | None, int | None, int | None]:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None, None, None, None
    return usage.total, usage.used, usage.free, max(0, usage.total - usage.used - usage.free)


def _status(root: Node, coverage: Coverage, unknown: bool, partial: bool) -> str:
    try:
        whole_volume = os.path.ismount(root.path)
        current = stat_snapshot(root.path)
    except OSError:
        return "capacity_unavailable"
    if root.snapshot is not None and unpack_snapshot(current).identity != unpack_snapshot(root.snapshot).identity:
        return "root_changed"
    if not whole_volume:
        return "folder_only"
    if partial or not coverage.complete:
        return "incomplete"
    return "identity_unknown" if unknown else "estimated"


def _is_trash(path: str) -> bool:
    """Recognise platform Trash namespaces, not an arbitrary folder called Trash."""
    normal = path.replace("\\", "/").rstrip("/")
    name = normal.rsplit("/", 1)[-1]
    if os.name == "nt":
        return name.casefold() == "$recycle.bin" and os.path.ismount(os.path.dirname(path))
    home = os.path.expanduser("~").replace("\\", "/").rstrip("/")
    if normal in (home + "/.Trash", home + "/.local/share/Trash"):
        return True
    return (name in (".Trash", ".Trashes") or name.startswith(".Trash-") and name[7:].isdigit()) and (
        os.path.ismount(os.path.dirname(path)))


def _trash_node(node: Node) -> bool:
    name = node.name.casefold()
    return node.is_dir and (name in ("$recycle.bin", ".trash", ".trashes", "trash") or name.startswith(".trash-")) and (
        _is_trash(node.path))


@dataclass(slots=True)
class _Counts:
    named: int = 0
    unique: int = 0
    bin_seen: int = 0
    foreign: int = 0
    mounts: int = 0
    unknown: bool = False
    bin_found: bool = False
    bin_complete: bool = True
    links: dict[tuple[int, int], list[int]] = field(default_factory=dict)

    def add(self, node: Node, device: int | None, in_bin: bool) -> None:
        info = unpack_snapshot(node.snapshot) if node.snapshot is not None else None
        foreign = info is not None and device is not None and info.device != device
        if not foreign:
            self.named += node.allocated
        self.unknown |= info is None or not info.inode or not info.links or node.error is not None
        if info is not None and info.inode and info.links > 1:
            group = self.links.setdefault(info.identity, [node.allocated, int(in_bin), int(foreign)])
            group[0] = max(group[0], node.allocated)
            group[1] |= int(in_bin)
        else:
            self.count(node.allocated, in_bin, foreign)

    def count(self, allocated: int, in_bin: bool, foreign: bool) -> None:
        if foreign:
            self.foreign += allocated
        else:
            self.unique += allocated
            if in_bin:
                self.bin_seen += allocated

    def finish(self) -> None:
        for allocated, in_bin, foreign in self.links.values():
            self.count(allocated, bool(in_bin), bool(foreign))
