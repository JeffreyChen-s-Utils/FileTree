"""Bounded read-only age queries from optional file timestamps, with explicit access-policy limits."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
import sys
import threading
import time

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

if sys.platform == "win32":
    import winreg

_DAY = 86400
_MAX_DAYS = 36500
_LIMIT = 1000
_FILE_SYSTEM = r"SYSTEM\CurrentControlSet\Control\FileSystem"
_FLAGS = 0x80000003


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    """Reported NTFS registry configuration; it is not proof of the effective policy on every volume."""

    state: str
    raw: int | None = None


def access_policy() -> AccessPolicy:
    """Read NtfsDisableLastAccessUpdate without changing it; unavailable values remain unknown."""
    if sys.platform != "win32":
        return AccessPolicy("platform")
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _FILE_SYSTEM, 0, winreg.KEY_READ) as key:
            value, kind = winreg.QueryValueEx(key, "NtfsDisableLastAccessUpdate")
    except OSError:
        return AccessPolicy("unknown")  # This state is displayed and cannot produce access-age matches.
    if kind != winreg.REG_DWORD or type(value) is not int or value < 0 or value & ~_FLAGS:
        return AccessPolicy("unknown")
    return AccessPolicy("disabled" if value & 1 else "enabled", value)


@dataclass(frozen=True, slots=True)
class TimeInventory:
    """Largest matching recorded files and complete match/unknown counts; overlapping folders are absent."""

    rows: list[Node]
    count: int
    size: int
    unknown: int
    total: int
    policy: AccessPolicy
    incomplete: bool = False


def files_older_than(root: Node, days: int, *, clock: str = "accessed", now: float | None = None,
                     cancel: threading.Event | None = None, policy: AccessPolicy | None = None) -> TimeInventory | None:
    """Query recorded access/creation dates without filesystem reads; cancel returns no inventory.

    Access grouping is refused when Windows' NTFS configuration is disabled or unknown. Other
    filesystems can defer/suppress atime too: matching a recorded date never proves nonuse.
    Future or missing dates count as unknown, never as old. Rows are capped, counts cover all files.
    """
    if type(days) is not int or not 0 <= days <= _MAX_DAYS or clock not in ("accessed", "created"):
        raise ValueError("Invalid recorded-time query")
    now = time.time() if now is None else now
    if not math.isfinite(now):
        raise ValueError("Invalid query time")
    policy = access_policy() if policy is None else policy
    usable = clock != "accessed" or policy.state not in ("disabled", "unknown")
    cutoff = now - days * _DAY
    count = size = unknown = total = 0
    incomplete = False
    heap = []
    for node in root.iter_nodes():
        if node.is_dir:
            give_way()
        if cancel is not None and cancel.is_set():
            return None
        incomplete |= node.error is not None
        if node.is_dir or node.is_link:
            continue
        total += 1
        stamp = getattr(node, clock) if usable else None
        if stamp is None or stamp > now:
            unknown += 1
            continue
        if stamp > cutoff:
            continue
        count += 1
        size += node.size
        item = (node.size, -total, node)
        if len(heap) < _LIMIT:
            heapq.heappush(heap, item)
        elif item[:2] > heap[0][:2]:
            heapq.heapreplace(heap, item)
    return TimeInventory([item[2] for item in sorted(heap, reverse=True)],
                         count, size, unknown, total, policy, incomplete)
