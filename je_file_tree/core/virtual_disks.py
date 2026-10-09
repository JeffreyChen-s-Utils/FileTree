"""Read-only bounded virtual-disk discovery; guest usage and compaction authority remain unknown."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
import heapq
import os
import stat
import threading

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import pack_snapshot, stable_snapshot, unpack_snapshot
from je_file_tree.core.virtual_disk_sources import DiskRegistration, DiskRegistrations, registered_disks
from je_file_tree.core.windows_allocation import file_allocation

FORMATS = frozenset({"vhdx", "vhd", "vmdk", "vdi", "qcow2"})
MAX_DISKS = 1000
_UNAVAILABLE = 0x400 | 0x1000 | 0x40000 | 0x400000
_EXTENDED_DRIVE_LENGTH = len("\\\\?\\c:\\")


@dataclass(frozen=True, slots=True)
class VirtualDisk:
    """One captured backing file; recorded allocation is an estimate, never guest-used bytes."""

    path: str
    kind: str
    source: str
    name: str
    node: Node | None
    size: int | None
    allocated: int | None
    snapshot: bytes | None
    issue: str = ""
    distro: str | None = None
    guest_used: int | None = None
    virtual_size: int | None = None


@dataclass(frozen=True, slots=True)
class VirtualDisks:
    """Bounded largest backing-file rows, full discovered count and incomplete/omitted source evidence."""

    rows: tuple[VirtualDisk, ...]
    count: int
    issues: int
    incomplete: bool


def _key(path: str) -> str:
    path = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    if os.name == "nt" and path.startswith("\\\\?\\unc\\"):
        return "\\\\" + path[8:]
    if (os.name == "nt" and path.startswith("\\\\?\\") and len(path) >= _EXTENDED_DRIVE_LENGTH and
            "a" <= path[4] <= "z" and path[5:7] == ":\\"):
        return path[4:]
    return path


def _kind(path: str) -> str:
    return os.path.splitext(path)[1].removeprefix(".").lower()


def _recorded(node: Node) -> VirtualDisk:
    issue = "unverified" if node.snapshot is None else ""
    if node.snapshot is not None:
        info = unpack_snapshot(node.snapshot)
        if node.is_dir or node.is_link or info.is_link or not stat.S_ISREG(info.mode) or info.attributes & _UNAVAILABLE:
            issue = "unavailable"
        elif not info.device or not info.inode:
            issue = "unverified"
        elif info.links != 1:
            issue = "duplicate_hard_links"
    if node.error is not None:
        issue = node.error
    return VirtualDisk(node.path, _kind(node.path), "scan", node.name, node, node.size,
                       node.allocated, node.snapshot, issue)


def _external(source: DiskRegistration) -> VirtualDisk:
    row = VirtualDisk(source.path, _kind(source.path), source.source, source.name, None, None, None, None,
                      distro=source.distro)
    try:
        info = os.lstat(source.path)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_ino
                or getattr(info, "st_file_attributes", 0) & _UNAVAILABLE):
            return replace(row, issue="unavailable")
        allocation = (file_allocation(source.path, info) if os.name == "nt" else
                      info.st_blocks * 512 if hasattr(info, "st_blocks") else None)
        snapshot = pack_snapshot(info)
        if stable_snapshot(pack_snapshot(os.lstat(source.path))) != stable_snapshot(snapshot):
            return replace(row, issue="changed")
        return replace(row, size=info.st_size, allocated=allocation, snapshot=snapshot)
    except OSError as exc:
        return replace(row, issue=str(exc))


def _add(rows: list[tuple[int, int, str, int, VirtualDisk]], row: VirtualDisk, count: int) -> None:
    rank = (row.allocated if row.allocated is not None else -1,
            row.size if row.size is not None else -1, row.path, count, row)
    if len(rows) < MAX_DISKS:
        heapq.heappush(rows, rank)
    else:
        heapq.heappushpop(rows, rank)


def _sources(registrations: Sequence[DiskRegistration] | None,
             cancel: threading.Event | None) -> DiskRegistrations | None:
    if cancel is not None and cancel.is_set():
        return None
    if registrations is None:
        return registered_disks(cancel=cancel)
    if len(registrations) > MAX_DISKS:
        raise ValueError("Virtual-disk provider overrides exceed 1,000 registrations")
    return DiskRegistrations(tuple(registrations))


def find_virtual_disks(root: Node, *, registrations: Sequence[DiskRegistration] | None = None,
                       partial: bool = False, cancel: threading.Event | None = None) -> VirtualDisks | None:
    """Find recorded VHD/VHDX/VMDK/VDI/QCOW2 files and current-user WSL/default Docker locations.

    Iterate folders off the GUI thread, yielding per folder; no headers, guests, mounts or commands
    are opened. Registered locations outside the scan use no-follow file metadata only. Merge exact
    paths with recorded rows, retaining the provider name and original scan node. Windows extended
    UNC/drive forms match ordinary recorded paths; other device prefixes remain explicit. Display
    at most 1,000 largest files; include full discovered/omitted counts and incomplete coverage. Missing,
    linked/cloud/changed external entries remain visible as unknown. File lengths/allocation are
    backing-file observations, never guest-used bytes or virtual capacity, and grant no compaction
    permission. Cancellation returns None, including after final provider metadata reads.
    """
    found = _sources(registrations, cancel)
    if found is None:
        return None
    providers = {_key(source.path): source for source in found.rows}
    issues = found.issues
    rows, count, incomplete = [], 0, partial
    stack = [root]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        folder = stack.pop()
        incomplete |= folder.error is not None or folder.is_link
        for node in folder.children:
            if cancel is not None and cancel.is_set():
                return None
            incomplete |= node.error is not None
            if node.is_dir and not node.is_link:
                stack.append(node)
            elif _kind(node.name) in FORMATS:
                row = _recorded(node)
                if source := providers.pop(_key(row.path), None):
                    row = replace(row, source=source.source, name=source.name, distro=source.distro)
                count += 1
                issues += bool(row.issue)
                _add(rows, row, count)
    for source in providers.values():
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        row = _external(source)
        count += 1
        issues += bool(row.issue)
        _add(rows, row, count)
    ordered = sorted((rank[-1] for rank in rows), key=lambda row: (-(row.allocated or 0), -(row.size or 0), row.path))
    issues += max(0, count - MAX_DISKS)
    if cancel is not None and cancel.is_set():
        return None
    return VirtualDisks(tuple(ordered), count, issues, incomplete or bool(issues))
