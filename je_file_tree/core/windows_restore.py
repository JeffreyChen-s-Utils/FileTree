"""Observed exact-item Shell undelete with captured no-follow payload/receipt identities."""

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import threading
import time

from je_file_tree.core.no_replace import DirectoryStamp, anchored_directory, directory_stamps
from je_file_tree.core.pacing import give_way
from je_file_tree.core.recycle_shell import recycle_item
from je_file_tree.core.snapshot import stable_snapshot, stat_snapshot, unpack_snapshot
from je_file_tree.core.trash_restore import RestoreResult, TrashOrigin, _unchanged

_LIMIT = 100_000
_DEPTH = 128
_RECEIPT_BYTES = 64 * 1024
_UNAVAILABLE = 0x400 | 0x1000 | 0x40000 | 0x400000
_OBSERVE_SECONDS = 15
_POLL_SECONDS = 0.02


@dataclass(frozen=True, slots=True)
class WindowsRestorePlan:
    """Exact Shell source/identity match and bounded payload/receipt observations after native Trash."""

    origin: TrashOrigin
    trashed: str
    ancestors: tuple[DirectoryStamp, ...]
    receipt: str
    receipt_snapshot: bytes
    entries: tuple[tuple[tuple[str, ...], bytes], ...]


def _ordinary(snapshot: bytes) -> None:
    info = unpack_snapshot(snapshot)
    if (not info.device or not info.inode or info.is_link or info.attributes & _UNAVAILABLE
            or not (stat.S_ISREG(info.mode) or info.is_dir)):
        raise ValueError("Undo payload is unidentified, linked, special or unavailable")


def _manifest(path: str, cancel: threading.Event | None) -> tuple[tuple[tuple[str, ...], bytes], ...]:
    root = stable_snapshot(stat_snapshot(path))
    _ordinary(root)
    entries, stack = [((), root)], [((), root)]
    while stack:
        parts, snapshot = stack.pop()
        if cancel is not None and cancel.is_set():
            raise ValueError("Undo capture canceled")
        if not unpack_snapshot(snapshot).is_dir:
            continue
        give_way()
        folder = os.path.join(path, *parts)
        with anchored_directory(directory_stamps(folder)):
            if stable_snapshot(stat_snapshot(folder)) != snapshot:
                raise ValueError("Undo folder changed before inventory")
            children = []
            with os.scandir(folder) as items:
                for item in items:
                    if len(entries) + len(children) >= _LIMIT or len(parts) >= _DEPTH:
                        raise ValueError("Undo payload exceeds entry/depth bounds")
                    recorded = stable_snapshot(stat_snapshot(item.path))
                    _ordinary(recorded)
                    children.append(((*parts, item.name), recorded))
            entries.extend(sorted(children))
            stack.extend(sorted(children, reverse=True))
            if stable_snapshot(stat_snapshot(folder)) != snapshot:
                raise ValueError("Undo folder changed during inventory")
    if stable_snapshot(stat_snapshot(path)) != root:
        raise ValueError("Undo payload changed during inventory")
    return tuple(entries)


def _receipt(path: str) -> tuple[str, bytes]:
    payload = Path(path)
    if (payload.parent.parent.name.casefold() != "$recycle.bin" or not payload.name.startswith("$R")
            or not payload.parent.name.startswith("S-1-")):
        raise ValueError("Undo requires an actual current-user Recycle Bin payload")
    receipt = str(payload.with_name("$I" + payload.name[2:]))
    snapshot = stable_snapshot(stat_snapshot(receipt))
    info = unpack_snapshot(snapshot)
    _ordinary(snapshot)
    if info.is_dir or info.size > _RECEIPT_BYTES:
        raise ValueError("Undo receipt is not recognized bounded metadata")
    return receipt, snapshot


def prepare_windows_restore(origin: TrashOrigin, *, actual: str | None = None,
                            cancel: threading.Event | None = None) -> WindowsRestorePlan:
    """Match one exact current-user Shell source/identity and capture metadata without invoking restore.

    Canonical original-name/folder properties include extensions and must match the recorded path.
    Linked/cloud/special/unknown or changed payloads are refused. Missing Qt destinations require a
    unique full Shell identity match; actual destinations restrict the lookup. Native parent anchors
    reject replacement/reparse ancestors; no payloads or receipt contents are read.
    """
    with anchored_directory(origin.ancestors), recycle_item(origin, actual=actual, cancel=cancel) as item:
        if os.path.lexists(origin.path):
            raise ValueError("Undo original path is occupied")
        ancestors = directory_stamps(os.path.dirname(item.trashed))
        with anchored_directory(ancestors):
            receipt, snapshot = _receipt(item.trashed)
            entries = _manifest(item.trashed, cancel)
            if not _unchanged(unpack_snapshot(origin.snapshot), unpack_snapshot(entries[0][1])):
                raise ValueError("Trashed identity differs from captured original")
        return WindowsRestorePlan(origin, item.trashed, ancestors, receipt, snapshot, entries)


def _observed(plan: WindowsRestorePlan) -> RestoreResult | None:
    if not os.path.lexists(plan.origin.path):
        return None
    top = unpack_snapshot(stat_snapshot(plan.origin.path))
    if top.identity != unpack_snapshot(plan.entries[0][1]).identity:
        raise ValueError("Original-path arrival is not the captured restored identity")
    if os.path.lexists(plan.trashed):
        return None
    retained = os.path.lexists(plan.receipt)
    try:
        current = _manifest(plan.origin.path, None)
        unchanged = _unchanged(unpack_snapshot(plan.entries[0][1]), unpack_snapshot(current[0][1]))
        error = ("Restored payload observations changed; inspect original path"
                 if not unchanged or current[1:] != plan.entries[1:] else "")
    except (OSError, ValueError) as exc:
        error = f"Restored identity observed, but payload verification failed: {exc}"
    if retained:
        error += ("; " if error else "") + "Shell retained the Recycle Bin receipt"
    return RestoreResult(True, plan.origin.path, plan.trashed, error, retained)


def _completion(plan: WindowsRestorePlan) -> RestoreResult:
    deadline, observed = time.monotonic() + _OBSERVE_SECONDS, None
    while time.monotonic() <= deadline:
        if observed is None or not os.path.lexists(plan.receipt):
            observed = _observed(plan)
            if observed is not None and not observed.receipt_retained:
                return observed
        time.sleep(_POLL_SECONDS)
    final = _observed(plan)
    if final is not None:
        return final
    raise ValueError("Shell restoration is unconfirmed; native work may still be active; inspect both paths")


def restore_windows(plan: WindowsRestorePlan, *, window: int = 0,
                    cancel: threading.Event | None = None) -> RestoreResult:
    """Invoke the exact captured Shell item's canonical undelete after immediate complete revalidation.

    Never manually moves/deletes payloads or $I metadata. Refuse occupied originals before invocation;
    Windows may still ask its own collision/error question on races, and this code never answers it.
    Request synchronous execution, join the call, then observe actual identity/location for up to 15s.
    An unconfirmed result is explicit, never a promised restore; native Shell work may still be active.
    Native modified/partial results retain visible actual locations, with no unsafe rollback fallback.
    """
    original = plan.origin
    try:
        with (anchored_directory(original.ancestors), anchored_directory(plan.ancestors),
              recycle_item(original, actual=plan.trashed, cancel=cancel) as item):
            if (os.path.lexists(original.path) or _receipt(plan.trashed) != (plan.receipt, plan.receipt_snapshot)
                    or _manifest(plan.trashed, cancel) != plan.entries):
                raise ValueError("Undo payload/receipt changed or original path is occupied")
            if cancel is not None and cancel.is_set():
                raise ValueError("Undo canceled before native restore")
            item.undelete(window=window)
            return _completion(plan)
    except (OSError, ValueError) as exc:
        try:
            observed = _observed(plan)
        except (OSError, ValueError):
            observed = None  # Neither location can confirm completion; retain the original error below.
        if observed is not None:
            return RestoreResult(True, original.path, plan.trashed,
                                 str(exc) + ("; " + observed.error if observed.error else ""),
                                 observed.receipt_retained)
        return RestoreResult(False, original.path, plan.trashed, str(exc))
