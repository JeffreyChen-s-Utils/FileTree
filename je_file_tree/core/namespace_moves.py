"""Reviewable same-volume move/rename batches over captured scan entries, with no overwriting or copying."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
import os
from pathlib import Path
import re
import stat
import threading

from je_file_tree.core.node import Node, outermost
from je_file_tree.core.no_replace import DirectoryStamp, anchored_directory, directory_stamps, rename_no_replace
from je_file_tree.core.operations import revalidate
from je_file_tree.core.pacing import give_way
from je_file_tree.core.protected import Protection, protected_places, protection_of
from je_file_tree.core.snapshot import stable_snapshot, stat_snapshot, unpack_snapshot
from je_file_tree.core.system_files import system_file

MAX_ITEMS = 1000
_NAME_LIMIT = 255
_COLLISION_LIMIT = 1000
_UNAVAILABLE = 0x1000 | 0x40000 | 0x400000
_CONTROL_LIMIT = 32
_SURROGATE_FIRST, _SURROGATE_LAST = 0xD800, 0xDFFF
_TOKEN = re.compile(r"\{(name|stem|ext|n)\}")
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class NamespaceItem:
    """One displayed source/destination pair, captured name/snapshot and eligibility reason."""

    node: Node
    source: str
    destination: str
    snapshot: bytes | None
    ancestors: tuple[DirectoryStamp, ...]
    target_ancestors: tuple[DirectoryStamp, ...]
    reason: str = ""
    detail: str = ""


@dataclass(frozen=True, slots=True)
class NamespacePlan:
    """Frozen bounded preview; only empty-reason rows are eligible after explicit GUI confirmation."""

    root: Node
    items: tuple[NamespaceItem, ...]
    places: tuple[Protection, ...]


@dataclass(slots=True)
class NamespaceResult:
    """Per-item outcomes and both affected parent paths; cancellation preserves completed moves."""

    moved: list[NamespaceItem] = field(default_factory=list)
    skipped: list[tuple[NamespaceItem, str]] = field(default_factory=list)
    failed: list[tuple[NamespaceItem, str]] = field(default_factory=list)
    parents: set[str] = field(default_factory=set)
    canceled: bool = False


def _name(pattern: str | None, node: Node, number: int) -> str:
    if pattern is None:
        return node.name
    if len(pattern) > _NAME_LIMIT or any(char in _TOKEN.sub("", pattern) for char in "{}"):
        raise ValueError("Only {name}, {stem}, {ext}, {n} filename tokens are supported")
    values = dict(name=node.name, stem=Path(node.name).stem, ext=Path(node.name).suffix, n=str(number))
    return _TOKEN.sub(lambda match: values[match[1]], pattern)


def _valid_name(name: str) -> None:
    if (not name or name in (".", "..") or any(char in name for char in "/\\\0")
            or any(ord(char) < _CONTROL_LIMIT or _SURROGATE_FIRST <= ord(char) <= _SURROGATE_LAST for char in name)):
        raise ValueError("Destination must be one readable filename")
    length = len(name.encode("utf-16-le")) // 2 if os.name == "nt" else len(os.fsencode(name))
    if length > _NAME_LIMIT:
        raise ValueError("Destination filename exceeds supported length")
    if os.name == "nt" and (name.endswith((" ", ".")) or any(char in name for char in '<>:"|?*')
                            or _RESERVED.fullmatch(name)):
        raise ValueError("Invalid or reserved Windows filename")


def _destination(parent: str, name: str, collision: str, reserved: set[str],
                 cancel: threading.Event | None) -> str:
    target = os.path.join(parent, name)
    if collision == "skip" or not (os.path.normcase(target) in reserved or os.path.lexists(target)):
        return target
    stem, suffix = os.path.splitext(name)
    for number in range(2, _COLLISION_LIMIT + 2):
        if cancel is not None and cancel.is_set():
            raise InterruptedError("Preview canceled")
        proposed = f"{stem} ({number}){suffix}"
        _valid_name(proposed)
        target = os.path.join(parent, proposed)
        if os.path.normcase(target) not in reserved and not os.path.lexists(target):
            return target
    raise ValueError("No free collision name within the preview limit")


def _descendant(target: str, sources: Sequence[Node]) -> bool:
    for node in sources:
        if node.is_dir:
            try:
                source = os.path.abspath(node.path)
                if os.path.commonpath((os.path.abspath(target), source)) == source:
                    return True
            except ValueError:  # Different drive letters cannot form a descendant path.
                continue
    return False


def _source_reason(node: Node, root: Node, places: Sequence[Protection], cancel: threading.Event | None,
                   overrides: dict[tuple[int, int], bytes] | None = None) -> str:
    snapshot = unpack_snapshot(node.snapshot) if node.snapshot is not None else None
    if snapshot is None or not snapshot.device or not snapshot.inode:
        return "unverified"
    if node.is_link or snapshot.is_link:
        return "link"
    if not (stat.S_ISREG(snapshot.mode) or stat.S_ISDIR(snapshot.mode)):
        return "special"
    for entry in node.iter_nodes():
        if cancel is not None and cancel.is_set():
            return "cancelled"
        if entry.snapshot is not None and unpack_snapshot(entry.snapshot).attributes & _UNAVAILABLE:
            return "unavailable"
    return revalidate(node, root, places=places, cancel=cancel, snapshot_overrides=overrides) or ""


def _prepare_item(root: Node, node: Node, fields: tuple[str | None, str | None, str, int],
                  context: tuple[Sequence[Node], tuple[Protection, ...], set[str]],
                  cancel: threading.Event | None) -> NamespaceItem:
    directory, pattern, collision, number = fields
    sources, places, reserved = context
    source, target, ancestors, target_ancestors = node.path, "", (), ()
    try:
        name = _name(pattern, node, number)
        _valid_name(name)
        parent = os.path.abspath(directory) if directory is not None else os.path.dirname(source)
        target = _destination(parent, name, collision, reserved, cancel)
        ancestors, target_ancestors = directory_stamps(os.path.dirname(source)), directory_stamps(parent)
        reason = _source_reason(node, root, places, cancel)
        if not reason:
            reason = _target_reason(source, target, node, sources, places, reserved, target_ancestors)
        if not reason:
            reserved.add(os.path.normcase(target))
        return NamespaceItem(node, source, target, node.snapshot, ancestors, target_ancestors, reason)
    except (OSError, ValueError) as exc:
        return NamespaceItem(node, source, target, node.snapshot, ancestors, target_ancestors, "error", str(exc))


def _target_reason(source: str, target: str, node: Node, sources: Sequence[Node], places: Sequence[Protection],
                   reserved: set[str], ancestors: tuple[DirectoryStamp, ...]) -> str:
    if os.path.normcase(source) == os.path.normcase(target):
        return "unchanged"
    if _descendant(target, sources):
        return "descendant"
    if protection_of(os.path.realpath(target), places) is not None or system_file(os.path.realpath(target)) is not None:
        return "protected_destination"
    if node.snapshot is None or unpack_snapshot(node.snapshot).device != unpack_snapshot(ancestors[-1].snapshot).device:
        return "volume"
    if os.path.normcase(target) in reserved or os.path.lexists(target):
        return "collision"
    return ""


def prepare_namespace(root: Node, nodes: Sequence[Node], *, directory: str | None = None,
                      pattern: str | None = None, collision: str = "skip",
                      cancel: threading.Event | None = None) -> NamespacePlan | None:
    """Build a read-only worker preview of every outermost source/destination, with bounded literal tokens.

    Choose either existing destination directory or filename pattern; explicit collision='rename'
    chooses reviewed available suffixes. Never changes files, creates directories or opens payloads.
    Links/special/unavailable/unverified/partial/protected sources and protected/descendant/cross-volume
    targets are ineligible. Cancellation suppresses the whole plan; at most 1000 raw selections.
    """
    if (directory is None) == (pattern is None) or collision not in ("skip", "rename"):
        raise ValueError("Choose one move-directory or rename-pattern and a supported collision choice")
    if not nodes or len(nodes) > MAX_ITEMS:
        raise ValueError("Review 1–1000 selected scan entries")
    sources, places, reserved = outermost(nodes), tuple(protected_places()), set()
    items = []
    for number, node in enumerate(sources, 1):
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        item = _prepare_item(root, node, (directory, pattern, collision, number), (sources, places, reserved), cancel)
        items.append(item)
    return None if cancel is not None and cancel.is_set() else NamespacePlan(root, tuple(items), places)


def _operate(plan: NamespacePlan, item: NamespaceItem, cancel: threading.Event | None,
              overrides: dict[tuple[int, int], bytes]) -> None:
    if item.node.path != item.source or item.node.snapshot != item.snapshot:
        raise ValueError("Captured source changed in the result tree")
    with (anchored_directory(item.ancestors) as old_fd,
          anchored_directory(item.target_ancestors) as new_fd):
        reason = _source_reason(item.node, plan.root, plan.places, cancel, overrides)
        if reason:
            raise ValueError(reason)
        reason = _target_reason(item.source, item.destination, item.node, (item.node,), plan.places, set(),
                                item.target_ancestors)
        if reason:
            raise ValueError(reason)
        # A folder survey may take time; pin names and recheck the top entry at the actual rename boundary.
        expected = overrides.get(unpack_snapshot(item.snapshot).identity, item.snapshot) if item.snapshot else None
        if expected is None or stable_snapshot(stat_snapshot(item.source)) != stable_snapshot(expected):
            raise ValueError("Source changed immediately before rename")
        if cancel is not None and cancel.is_set():
            raise InterruptedError("Operation canceled")
        rename_no_replace(item.source, item.destination, old_fd, new_fd)
        _receipt(item, expected, overrides, old_fd, new_fd)


def _receipt(item: NamespaceItem, expected: bytes, overrides: dict[tuple[int, int], bytes],
              old_fd: int | None, new_fd: int | None) -> None:
    try:
        current = stat_snapshot(item.destination)
        before, after = unpack_snapshot(expected), unpack_snapshot(current)
        if replace(after, changed_ns=before.changed_ns) != before:
            raise ValueError("Renamed entry changed during the operation")
    except (OSError, ValueError) as exc:
        try:
            rename_no_replace(item.destination, item.source, new_fd, old_fd)
        except (OSError, ValueError) as rollback:
            raise ValueError(f"{exc}; rollback failed: {rollback}; inspect {item.destination}") from rollback
        raise ValueError(f"{exc}; entry restored to {item.source}") from exc
    # A rename changes inode ctime for every hard-link name. Only this verified receipt is trusted.
    overrides[after.identity] = current


def execute_namespace(plan: NamespacePlan, *, cancel: threading.Event | None = None,
                      progress: Callable[[int, int], None] | None = None) -> NamespaceResult:
    """Execute only explicitly confirmed eligible rows, revalidating source/parents/destination per item.

    OS rename never overwrites or falls back to copying. Stops between entries; completed moves remain.
    Unsupported/locked/changed/colliding rows preserve their source and report individual errors.
    Parent anchors pin identities, not all filesystem activity: concurrent source renames are not an OS
    transaction with observation. GUI must report actual paths and rescan both affected parents.
    """
    result = NamespaceResult()
    overrides: dict[tuple[int, int], bytes] = {}
    for number, item in enumerate(plan.items, 1):
        if cancel is not None and cancel.is_set():
            result.canceled = True
            break
        give_way()
        if item.reason:
            result.skipped.append((item, item.reason))
        else:
            try:
                _operate(plan, item, cancel, overrides)
                result.moved.append(item)
                result.parents.update((os.path.dirname(item.source), os.path.dirname(item.destination)))
            except (OSError, ValueError) as exc:
                result.failed.append((item, str(exc)))
                result.parents.update((os.path.dirname(item.source), os.path.dirname(item.destination)))
        if progress is not None:
            progress(number, len(plan.items))
    result.canceled |= cancel is not None and cancel.is_set()
    return result
