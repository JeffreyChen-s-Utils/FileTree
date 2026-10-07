"""Explicit freedesktop undo with captured identities, exact receipts and exclusive restoration."""

import configparser
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import posixpath
import re
import threading
from urllib.parse import unquote_to_bytes

from je_file_tree.core import bin_empty
from je_file_tree.core.bin_empty import BinEntry
from je_file_tree.core.mounts import descriptor_mount
from je_file_tree.core.no_replace import DirectoryStamp, anchored_directory, directory_stamps, rename_no_replace
from je_file_tree.core.snapshot import Snapshot, pack_snapshot, stable_snapshot, stat_snapshot, unpack_snapshot

_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


@dataclass(frozen=True, slots=True)
class TrashOrigin:
    """Original path, pre-Trash snapshot and parent identities captured before the OS move."""

    path: str
    snapshot: bytes
    ancestors: tuple[DirectoryStamp, ...]


@dataclass(frozen=True, slots=True)
class RestorePlan:
    """One recognized current-user receipt and complete bounded no-follow payload observation."""

    origin: TrashOrigin
    trashed: str
    volume: str
    uid: int
    mount: int
    files: tuple[DirectoryStamp, ...]
    info: tuple[DirectoryStamp, ...]
    receipt: BinEntry
    entries: tuple[BinEntry, ...]


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """Truthful payload restoration and any remaining receipt/rollback error; never deletes payloads."""

    restored: bool
    source: str
    trashed: str
    error: str = ""
    receipt_retained: bool = True


def capture_origin(path: str, snapshot: bytes) -> TrashOrigin:
    """Capture an existing scanned entry before Trash; reject changed records and linked parents."""
    path = os.path.abspath(path)
    ancestors = directory_stamps(os.path.dirname(path))
    with anchored_directory(ancestors):
        if stable_snapshot(stat_snapshot(path)) != stable_snapshot(snapshot):
            raise ValueError("Original changed before capturing Trash undo")
    return TrashOrigin(path, stable_snapshot(snapshot), ancestors)


def receipt_destination(contents: str, *, topdir: str | None = None) -> str:
    """Strictly decode the freedesktop Path/DeletionDate; relative locations require the mounted topdir.

    Returns a POSIX path only. It is metadata, never authorization: preparation must match the captured
    original path and independently validate the current-user private bin and filesystem identities.
    """
    if len(contents.encode("utf-8")) > bin_empty.MAX_RECEIPT_BYTES:
        raise ValueError("Trash receipt exceeds size limit")
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(contents)
        raw = parser.get("Trash Info", "Path")
        datetime.strptime(parser.get("Trash Info", "DeletionDate"), "%Y-%m-%dT%H:%M:%S")
        if not raw or _ESCAPE.search(raw):
            raise ValueError("Invalid percent-encoded original path")
        path = os.fsdecode(unquote_to_bytes(raw))
    except (configparser.Error, UnicodeError) as exc:
        raise ValueError("Unrecognized Trash receipt") from exc
    if "\0" in path or posixpath.normpath(path) != path or any(part in (".", "..") for part in path.split("/")):
        raise ValueError("Invalid original path in Trash receipt")
    if not path.startswith("/"):
        if topdir is None or not topdir.startswith("/"):
            raise ValueError("Relative Trash path requires its mounted topdir")
        path = posixpath.join(topdir, path)
    return path


def _unchanged(before: Snapshot, after: Snapshot) -> bool:
    # The operating system's own rename legitimately changes only the top-level ctime.
    return (before.identity, before.size, before.modified_ns, before.mode, before.attributes, before.links) == (
        after.identity, after.size, after.modified_ns, after.mode, after.attributes, after.links)


def _inventory(files: int, name: str, mount: int, cancel: threading.Event | None) -> tuple[BinEntry, ...]:
    bin_empty._check(cancel)
    root = bin_empty._entry(os.stat(name, dir_fd=files, follow_symlinks=False), (name,))
    descriptor = os.open(name, os.O_PATH | os.O_NOFOLLOW, dir_fd=files)
    try:
        if descriptor_mount(descriptor) != mount or pack_snapshot(os.fstat(descriptor)) != root.snapshot:
            raise ValueError("Undo payload identity/mount changed")
    finally:
        os.close(descriptor)
    entries = [BinEntry((), root.snapshot, root.directory)]
    if root.directory:
        with bin_empty._relative_directory(files, (name,), mount, {(name,): root.snapshot}) as folder:
            children, _size, _count = bin_empty._payload(folder, mount, cancel)
            entries.extend(children)
    if root.snapshot != _stat_snapshot_at(files, name):
        raise ValueError("Trashed payload changed during undo capture")
    if len(entries) > bin_empty.MAX_ENTRIES:
        raise ValueError("Undo payload exceeds entry bounds")
    return tuple(entries)


def _stat_snapshot_at(parent: int, name: str) -> bytes:
    return pack_snapshot(os.stat(name, dir_fd=parent, follow_symlinks=False))


def _receipt(info: int, name: str, scope: Path, volume: Path) -> tuple[BinEntry, str]:
    entry = bin_empty._receipt(info, name)
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=info)
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        if (_stat_snapshot_at(info, name) != entry.snapshot
                or pack_snapshot(os.fstat(stream.fileno())) != entry.snapshot):
            raise ValueError("Trash receipt changed before undo reading")
        contents = stream.read(bin_empty.MAX_RECEIPT_BYTES + 1)
        if (_stat_snapshot_at(info, name) != entry.snapshot
                or pack_snapshot(os.fstat(stream.fileno())) != entry.snapshot):
            raise ValueError("Trash receipt changed during undo reading")
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    home_scope = (data if data.is_absolute() else Path.home() / ".local" / "share") / "Trash"
    destination = receipt_destination(contents, topdir=None if scope == home_scope else str(volume))
    return entry, destination


def _scope(files: int, info: int, original: int, scope: int, mount: int) -> None:
    bin_empty._private_scope(scope, mount)
    for descriptor in (files, info, original):
        if descriptor_mount(descriptor) != mount:
            raise ValueError("Undo crossed a captured filesystem mount")
    if any(os.fstat(fd).st_uid != os.getuid() for fd in (files, info)):
        raise ValueError("Undo Trash directories belong to another user")


def prepare_restore(origin: TrashOrigin, trashed: str, volume: str, *,
                    cancel: threading.Event | None = None) -> RestorePlan:
    """Observe one native same-volume freedesktop receipt after successful Trash, without mutations.

    Linux only: require known mount identity, private current-user recognized files/info scope,
    original pre-Trash identity and exact receipt path. Other/cross-volume/missing/changed receipts
    cannot promise undo. Directory inventories are capped at 100k entries/128 levels, never following links.
    """
    root = bin_empty._volume(volume)
    payload = Path(trashed)
    scope = payload.parent.parent
    if (not payload.is_absolute() or str(payload) != os.path.normpath(trashed)
            or payload.parent.name != "files" or scope not in bin_empty._candidates(root)):
        raise ValueError("Undo requires the actual recognized Trash destination")
    files_chain, info_chain = directory_stamps(str(payload.parent)), directory_stamps(str(scope / "info"))
    with (anchored_directory(files_chain) as files, anchored_directory(info_chain) as info,
          anchored_directory(origin.ancestors) as original, anchored_directory(files_chain[:-1]) as scope_fd):
        mount = descriptor_mount(files)
        _scope(files, info, original, scope_fd, mount)
        receipt, destination = _receipt(info, payload.name + ".trashinfo", scope, root)
        if destination != origin.path or os.path.lexists(origin.path):
            raise ValueError("Undo original path differs or is occupied")
        entries = _inventory(files, payload.name, mount, cancel)
        if not _unchanged(unpack_snapshot(origin.snapshot), unpack_snapshot(entries[0].snapshot)):
            raise ValueError("Trashed identity differs from the original")
    return RestorePlan(origin, str(payload), str(root), os.getuid(), mount, files_chain, info_chain, receipt, entries)


def _post_matches(expected: tuple[BinEntry, ...], current: tuple[BinEntry, ...]) -> bool:
    return (len(expected) == len(current) and _unchanged(unpack_snapshot(expected[0].snapshot),
                                                       unpack_snapshot(current[0].snapshot))
            and expected[1:] == current[1:])


def _paths(plan: RestorePlan, root: Path) -> None:
    payload = Path(plan.trashed)
    if not plan.files or not plan.info or not plan.origin.ancestors or not plan.entries:
        raise ValueError("Undo requires a complete captured plan")
    if (payload.parent.parent not in bin_empty._candidates(root)
            or payload.parent.name != "files" or not payload.is_absolute()
            or str(payload) != os.path.normpath(plan.trashed)
            or plan.files[-1].path != str(payload.parent)
            or plan.info[-1].path != str(payload.parent.parent / "info")
            or plan.receipt.parts != (payload.name + ".trashinfo",)
            or plan.origin.ancestors[-1].path != os.path.dirname(plan.origin.path)):
        raise ValueError("Undo scope/paths changed or are unrecognized")


def restore(plan: RestorePlan, *, cancel: threading.Event | None = None) -> RestoreResult:
    """Restore only an explicitly selected plan using native exclusive rename; never overwrite arrivals.

    Recheck every captured payload/receipt, parent identity, owner and mount. On changed post-rename
    metadata, attempt exclusive rollback; errors name actual retained locations. Remove only this
    recognized .trashinfo after successful restoration; metadata failure still reports restored=True.
    No payload deletion/copy fallback exists. Concurrent mutation remains observational.
    """
    original, payload = plan.origin, Path(plan.trashed)
    restored = False
    try:
        root = bin_empty._volume(plan.volume)
        _paths(plan, root)
        if plan.uid != os.getuid():
            raise ValueError("Undo user changed")
        with (anchored_directory(plan.files) as files, anchored_directory(plan.info) as info,
              anchored_directory(original.ancestors) as target,
              anchored_directory(plan.files[:-1]) as scope):
            _scope(files, info, target, scope, plan.mount)
            entry, destination = _receipt(info, plan.receipt.parts[0], payload.parent.parent, root)
            if (entry != plan.receipt or destination != original.path or os.path.lexists(original.path)
                    or _inventory(files, payload.name, plan.mount, cancel) != plan.entries):
                raise ValueError("Undo payload/receipt changed or original path is occupied")
            bin_empty._check(cancel)
            rename_no_replace(plan.trashed, original.path, files, target)
            restored = True
            current = _inventory(target, os.path.basename(original.path), plan.mount, None)
            if not _post_matches(plan.entries, current):
                if _inventory(target, os.path.basename(original.path), plan.mount, None) != current:
                    raise ValueError("Rollback source changed; payload retained at original path")
                rename_no_replace(original.path, plan.trashed, target, files)
                restored = False
                raise ValueError("Restored metadata changed; payload rolled back to Trash")
            bin_empty._remove_entry(info, plan.mount, plan.receipt)
        return RestoreResult(True, original.path, plan.trashed, receipt_retained=False)
    except (OSError, ValueError, bin_empty.BinSurveyCancelledError) as exc:
        return RestoreResult(restored, original.path, plan.trashed, str(exc))
