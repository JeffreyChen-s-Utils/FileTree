"""Exact, conservative folder trends over owned scan-history snapshots."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from je_file_tree.core.compare import SavedScan, folder_key
from je_file_tree.core.history import HistoryCancelledError, HistoryEntry, ScanHistory, load_history
from je_file_tree.core.pacing import give_way

_MAX_POINTS = 1000
_MIN_ENDPOINTS = 2


class UnknownReason(str, Enum):
    """Why a retained observation cannot contribute a comparable size."""

    LEGACY = "legacy"
    INCOMPLETE = "incomplete"
    INCOMPATIBLE = "incompatible"
    MISSING = "missing"
    CORRUPT = "corrupt"
    TRUNCATED = "truncated"
    INSUFFICIENT = "insufficient"


def normalize_folder(path: str) -> str:
    """Normalize a root-relative folder without accepting drives or parent traversal."""
    if (not isinstance(path, str) or "\0" in path or path.startswith(("/", "\\"))
            or os.path.isabs(path) or (len(path) > 1 and path[1] == ":")):
        raise ValueError("Folder must be relative to the scanned root")
    parts = path.replace("\\", "/").split("/")
    if any(part == ".." for part in parts):
        raise ValueError("Folder must stay inside the scanned root")
    if any(part == "" for part in parts[1:-1]):
        raise ValueError("Folder path contains an empty component")
    return "/".join(part for part in parts if part and part != ".")


@dataclass(frozen=True, slots=True)
class TrendQuery:
    """One root-relative folder and an optional timezone-aware half-open period."""

    root: str
    folder: str = ""
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 1000

    def __post_init__(self) -> None:
        object.__setattr__(self, "folder", normalize_folder(self.folder))
        if not os.path.isabs(self.root) or type(self.limit) is not int or not 1 <= self.limit <= _MAX_POINTS:
            raise ValueError("Invalid trend root or limit")
        if any(value is not None and value.tzinfo is None for value in (self.start, self.end)):
            raise ValueError("Trend dates require explicit timezones")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("Trend start must precede end")


@dataclass(frozen=True, slots=True)
class TrendPoint:
    """One retained observation and its difference from the immediately previous observation."""

    entry: HistoryEntry
    size: int | None
    change: int | None
    reason: UnknownReason | None
    change_reason: UnknownReason | None = None


@dataclass(frozen=True, slots=True)
class ChildContribution:
    """A directly contained folder's actual endpoint sizes and net contribution."""

    folder: str
    before: int | None
    after: int | None
    change: int | None
    reason: UnknownReason | None


@dataclass(frozen=True, slots=True)
class HistoryTrend:
    """Bounded observations, actual endpoint net change and direct-child contributions."""

    query: TrendQuery
    points: tuple[TrendPoint, ...]
    children: tuple[ChildContribution, ...]
    net: int | None
    count: int
    invalid: int
    truncated: bool
    children_count: int = 0
    children_truncated: bool = False
    net_reason: UnknownReason | None = None


def _children(scan: SavedScan, folder: str, cancel: threading.Event | None) -> dict[str, tuple[str, int]]:
    prefix = folder_key(folder)
    result = {}
    for key, value in scan.folders.items():
        if cancel is not None and cancel.is_set():
            raise HistoryCancelledError
        give_way()
        if key == prefix or not key.startswith(prefix + "/" if prefix else ""):
            continue
        remainder = key[len(prefix) + 1:] if prefix else key
        if "/" not in remainder:
            result[key] = (value.path, value.size)
    return result


def _point(entry: HistoryEntry, folder: str,
           cancel: threading.Event | None) -> tuple[int | None, UnknownReason | None, dict[str, tuple[str, int]]]:
    if entry.measurement is None:
        reason = (UnknownReason.INCOMPATIBLE if entry.measurement_issue == "unsupported" else
                  UnknownReason.CORRUPT if entry.measurement_issue else UnknownReason.LEGACY)
        return None, reason, {}
    if entry.incomplete:
        return None, UnknownReason.INCOMPLETE, {}
    try:
        scan = load_history(entry, cancel=cancel)
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None, UnknownReason.CORRUPT, {}
    target = scan.folders.get(folder_key(folder))
    if target is None:
        return None, UnknownReason.MISSING, {}
    children = _children(scan, folder, cancel)
    direct_files = target.size - sum(value[1] for value in children.values())
    if direct_files < 0:
        return None, UnknownReason.CORRUPT, {}
    children["\0direct-files"] = ("", direct_files)
    return target.size, None, children


def _contributions(before: dict[str, tuple[str, int]], after: dict[str, tuple[str, int]],
                   endpoint_reason: UnknownReason | None,
                   cancel: threading.Event | None) -> tuple[tuple[ChildContribution, ...], int]:
    rows = []
    for key in sorted(before.keys() | after.keys()):
        if cancel is not None and cancel.is_set():
            raise HistoryCancelledError
        give_way()
        left, right = before.get(key), after.get(key)
        reason = endpoint_reason or (UnknownReason.MISSING if left is None or right is None else None)
        rows.append(ChildContribution((right or left)[0], left[1] if left else None, right[1] if right else None,
                                      right[1] - left[1] if reason is None else None, reason))
    count = len(rows)
    rows.sort(key=lambda row: (row.change is None, -(abs(row.change) if row.change is not None else 0), row.folder))
    return tuple(rows[:1000]), count


def query_trend(store: ScanHistory, query: TrendQuery, *,
                cancel: threading.Event | None = None) -> HistoryTrend:
    """Filter by parsed instant before capping, then load one saved tree at a time."""
    period = store.period(query.root, start=query.start, end=query.end, limit=query.limit, cancel=cancel)
    chosen = period.entries
    points = []
    first_children: dict[str, tuple[str, int]] = {}
    last_children: dict[str, tuple[str, int]] = {}
    for index, entry in enumerate(chosen):
        if cancel is not None and cancel.is_set():
            raise HistoryCancelledError
        size, reason, children = _point(entry, query.folder, cancel)
        previous = points[-1] if points else None
        compatible = previous is not None and previous.entry.measurement == entry.measurement
        change = (size - previous.size if compatible and size is not None and previous.size is not None else None)
        change_reason = (UnknownReason.INCOMPATIBLE if previous is not None and not compatible else
                         reason or (previous.reason if previous is not None else None)) if change is None else None
        points.append(TrendPoint(entry, size, change, reason, change_reason))
        if index == 0:
            first_children = children
        if index == len(chosen) - 1:
            last_children = children
    if period.truncated:
        endpoint_reason = UnknownReason.TRUNCATED
    elif len(points) < _MIN_ENDPOINTS:
        endpoint_reason = UnknownReason.INSUFFICIENT
    elif points[0].reason or points[-1].reason:
        endpoint_reason = points[0].reason or points[-1].reason
    elif points[0].entry.measurement != points[-1].entry.measurement:
        endpoint_reason = UnknownReason.INCOMPATIBLE
    else:
        endpoint_reason = None
    net = points[-1].size - points[0].size if endpoint_reason is None else None
    children, child_count = _contributions(first_children, last_children, endpoint_reason, cancel)
    if cancel is not None and cancel.is_set():
        raise HistoryCancelledError
    return HistoryTrend(query, tuple(points), children, net, period.count, period.invalid, period.truncated,
                        child_count, child_count > len(children), endpoint_reason)
