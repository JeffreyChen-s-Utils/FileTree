"""Reviewed freedesktop OS-bin scopes, anchored metadata inventories and bounded permanent emptying."""

from __future__ import annotations

import configparser
import os
import stat
import sys
import threading
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from je_file_tree.core.mounts import descriptor_mount, mount_points
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import pack_snapshot, unpack_snapshot
from je_file_tree.core.trash_size import TrashUsage, _locations

MAX_ENTRIES = 100_000
MAX_DEPTH = 128
MAX_RECEIPT_BYTES = 64 * 1024
_DIRECTORY_FLAGS = (getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0) | os.O_RDONLY)


class BinSurveyCancelledError(Exception):
    """The caller stopped a read-only bin approval inventory."""


@dataclass(frozen=True, slots=True)
class BinEntry:
    """Captured relative payload name and no-follow identity/change metadata."""

    parts: tuple[str, ...]
    snapshot: bytes
    directory: bool


@dataclass(frozen=True, slots=True)
class BinScope:
    """A recognized private uid Trash directory; only its files/info entries are removable."""

    directory: str
    snapshot: bytes
    entries: tuple[BinEntry, ...]
    receipts: tuple[BinEntry, ...]
    size: int
    count: int


@dataclass(frozen=True, slots=True)
class BinEmptyPlan:
    """Reviewable exact scopes, full metadata and logical totals for one mounted Linux volume."""

    root: str
    uid: int
    scopes: tuple[BinScope, ...]
    usage: TrashUsage


@dataclass(frozen=True, slots=True)
class BinEmptyResult:
    """Removed top-level payloads and bounded visible failures; partial work is not rolled back."""

    removed: int
    failures: tuple[str, ...]


def _check(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise BinSurveyCancelledError


def _volume(root: str) -> Path:
    if not sys.platform.startswith("linux"):
        raise ValueError("Freedesktop emptying requires Linux descriptor/mount guards")
    path = Path(root)
    if not path.is_absolute() or str(path.resolve(strict=True)) != str(path) or str(path) not in mount_points():
        raise ValueError("Trash approval requires one canonical mounted volume root")
    return path


def _candidates(root: Path) -> tuple[Path, ...]:
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return tuple(dict.fromkeys(path.parent for path in _locations(root, home, data, os.getuid(), sys.platform)))


@contextmanager
def _absolute_directory(path: Path) -> Iterator[int]:
    fd = os.open(os.sep, _DIRECTORY_FLAGS)
    try:
        for part in path.parts[1:]:
            child = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _relative_directory(root: int, parts: tuple[str, ...], mount: int,
                        identities: dict[tuple[str, ...], bytes] | None = None) -> Iterator[int]:
    fd = os.dup(root)
    prefix: tuple[str, ...] = ()
    try:
        for part in parts:
            if part in ("", ".", "..") or os.sep in part:
                raise ValueError("Invalid relative Trash member")
            child = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
            if descriptor_mount(fd) != mount or os.fstat(fd).st_uid != os.getuid():
                raise OSError("Mount boundary inside Trash")
            prefix = (*prefix, part)
            if identities is not None:
                expected, current = unpack_snapshot(identities[prefix]), os.fstat(fd)
                if expected.identity != (current.st_dev, current.st_ino) or current.st_uid != os.getuid():
                    raise OSError("Trash ancestor changed")
        yield fd
    finally:
        os.close(fd)


def _private_scope(fd: int, mount: int) -> bytes:
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or info.st_mode & 0o077 or not stat.S_ISDIR(info.st_mode):
        raise OSError("Trash scope must be a private current-user directory")
    if not info.st_dev or not info.st_ino:
        raise OSError("Trash scope identity is unavailable")
    if descriptor_mount(fd) != mount:
        raise OSError("Trash scope belongs to another mount")
    return pack_snapshot(info)


def _entry(info: os.stat_result, parts: tuple[str, ...]) -> BinEntry:
    if info.st_uid != os.getuid():
        raise OSError("Foreign owner inside Trash")
    if not info.st_dev or not info.st_ino:
        raise OSError("Trash entry identity is unavailable")
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)):
        raise OSError("Special entry inside Trash")
    return BinEntry(parts, pack_snapshot(info), stat.S_ISDIR(info.st_mode))


def _names(fd: int, limit: int, cancel: threading.Event | None) -> list[str]:
    names = []
    with os.scandir(fd) as children:
        for child in children:
            _check(cancel)
            if len(names) >= limit:
                raise OSError("Trash approval exceeds entry limits")
            names.append(child.name)
    return sorted(names)


def _payload(fd: int, mount: int, cancel: threading.Event | None) -> tuple[tuple[BinEntry, ...], int, int]:
    entries, stack = [], [()]
    identities: dict[tuple[str, ...], bytes] = {}
    size = count = 0
    while stack:
        _check(cancel)
        give_way()
        parts = stack.pop()
        with _relative_directory(fd, parts, mount, identities) as folder:
            names = _names(folder, MAX_ENTRIES - len(entries), cancel)
            for name in names:
                _check(cancel)
                if len(entries) == MAX_ENTRIES or len(parts) >= MAX_DEPTH:
                    raise OSError("Trash approval exceeds entry/depth limits")
                entry = _entry(os.stat(name, dir_fd=folder, follow_symlinks=False), (*parts, name))
                entries.append(entry)
                count += int(not parts)
                if entry.directory:
                    identities[entry.parts] = entry.snapshot
                    stack.append(entry.parts)
                else:
                    size += unpack_snapshot(entry.snapshot).size
    return tuple(entries), size, count


def _receipt(fd: int, name: str) -> BinEntry:
    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > MAX_RECEIPT_BYTES:
        raise OSError("Unrecognized Trash receipt")
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        if pack_snapshot(os.fstat(stream.fileno())) != pack_snapshot(info):
            raise OSError("Trash receipt changed before reading")
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(stream.read(MAX_RECEIPT_BYTES + 1))
        if not parser.has_section("Trash Info") or not parser.get("Trash Info", "Path", fallback=""):
            raise OSError("Unrecognized Trash receipt contents")
        if pack_snapshot(os.fstat(stream.fileno())) != pack_snapshot(info):
            raise OSError("Trash receipt changed while reading")
    return BinEntry((name,), pack_snapshot(info), False)


def _scope(path: Path, mount: int, cancel: threading.Event | None) -> BinScope:
    with _absolute_directory(path) as fd:
        before = _private_scope(fd, mount)
        with _relative_directory(fd, ("files",), mount) as files:
            entries, size, count = _payload(files, mount, cancel)
        with _relative_directory(fd, ("info",), mount) as info:
            listed = _names(info, MAX_ENTRIES, cancel)
            top_names = {entry.parts[0] + ".trashinfo" for entry in entries if len(entry.parts) == 1}
            if len(listed) > MAX_ENTRIES or set(listed) != top_names:
                raise OSError("Trash payload and receipts do not match; review orphan/unrecognized entries")
            receipts = tuple(_receipt(info, name) for name in listed)
        if _private_scope(fd, mount) != before:
            raise OSError("Trash scope changed during approval survey")
    return BinScope(str(path), before, entries, receipts, size, count)


def prepare_bin_empty(root: str, *, cancel: threading.Event | None = None) -> BinEmptyPlan | None:
    """Survey one recognized mounted Linux OS-bin scope off-thread, without deleting anything.

    None denotes cancellation. Linked/foreign/mounted/unknown/orphan entries make approval incomplete;
    known logical payload totals exclude directory and receipt bytes and never promise recovery.
    """
    path = _volume(root)
    scopes, errors = [], []
    try:
        _check(cancel)
        with _absolute_directory(path) as root_fd:
            mount = descriptor_mount(root_fd)
        for candidate in _candidates(path):
            _check(cancel)
            try:
                candidate.lstat()
            except FileNotFoundError:
                continue
            try:
                scopes.append(_scope(candidate, mount, cancel))
            except (OSError, ValueError, configparser.Error, UnicodeError) as exc:
                errors.append(f"{candidate}: {exc}")
    except BinSurveyCancelledError:
        return None
    size, count = sum(scope.size for scope in scopes), sum(scope.count for scope in scopes)
    usage = TrashUsage(size, count, not errors, "; ".join(errors[:3]))
    return BinEmptyPlan(str(path), os.getuid(), tuple(scopes), usage)


def _stable_scope(scope: BinScope, fd: int, mount: int) -> None:
    if str(Path(scope.directory).resolve(strict=True)) != scope.directory:
        raise OSError("Trash scope path became a link")
    if _private_scope(fd, mount) != scope.snapshot:
        raise OSError("Trash scope changed")
    if pack_snapshot(os.lstat(scope.directory)) != scope.snapshot:
        raise OSError("Trash scope moved or was replaced")


def _remove_entry(root: int, mount: int, entry: BinEntry,
                  identities: dict[tuple[str, ...], bytes] | None = None) -> None:
    with _relative_directory(root, entry.parts[:-1], mount, identities) as parent:
        info = os.stat(entry.parts[-1], dir_fd=parent, follow_symlinks=False)
        current = _entry(info, entry.parts)
        expected, actual = unpack_snapshot(entry.snapshot), unpack_snapshot(current.snapshot)
        matches = ((expected.identity, expected.mode) == (actual.identity, actual.mode) if entry.directory
                   else current.snapshot == entry.snapshot)
        if not matches:
            raise OSError("Trash entry changed; skipped")
        # Never follow payload links. rmdir also refuses directories containing newly arrived names.
        if entry.directory:
            os.rmdir(entry.parts[-1], dir_fd=parent)
        else:
            os.unlink(entry.parts[-1], dir_fd=parent)


def _empty_scope(scope: BinScope, mount: int) -> BinEmptyResult:
    failures, removed = deque(maxlen=20), 0
    identities = {entry.parts: entry.snapshot for entry in scope.entries if entry.directory}
    try:
        with _absolute_directory(Path(scope.directory)) as fd:
            _stable_scope(scope, fd, mount)
            if _scope(Path(scope.directory), mount, None) != scope:
                raise OSError("Trash entries changed; refresh and review again")
            with _relative_directory(fd, ("files",), mount) as files:
                for entry in reversed(scope.entries):
                    give_way()
                    try:
                        _stable_scope(scope, fd, mount)
                        _remove_entry(files, mount, entry, identities)
                        removed += int(len(entry.parts) == 1)
                    except (OSError, ValueError) as exc:
                        failures.append(str(exc))
            _remove_receipts(scope, fd, mount, failures)
    except (OSError, ValueError, configparser.Error, UnicodeError) as exc:
        failures.append(str(exc))
    return BinEmptyResult(removed, tuple(failures))


def _remove_receipts(scope: BinScope, fd: int, mount: int, failures: deque[str]) -> None:
    with (_relative_directory(fd, ("info",), mount) as info,
          _relative_directory(fd, ("files",), mount) as files):
        for receipt in scope.receipts:
            name = receipt.parts[0][:-len(".trashinfo")]
            try:
                os.stat(name, dir_fd=files, follow_symlinks=False)
            except FileNotFoundError:
                try:
                    _stable_scope(scope, fd, mount)
                    _remove_entry(info, mount, receipt)
                except (OSError, ValueError) as exc:
                    failures.append(str(exc))


def empty_posix_bin(approved: BinEmptyPlan) -> BinEmptyResult:
    """Permanently empty only captured files/info after two exact-scope GUI confirmations.

    Re-derive current uid/volume/scopes and match the complete metadata before any removal. Descriptor
    operations refuse links/mounts/changed entries; concurrent changes can still cause partial failure.
    No scope directory or source path from a receipt is removed. Once started, close must join it.
    """
    _volume(approved.root)
    if approved.uid != os.getuid() or not approved.usage.complete or approved.usage.count <= 0:
        raise ValueError("A complete nonempty current-user Trash approval is required")
    if prepare_bin_empty(approved.root) != approved:
        raise ValueError("Trash changed; refresh and review again")
    with _absolute_directory(Path(approved.root)) as fd:
        mount = descriptor_mount(fd)
    removed, failures = 0, deque(maxlen=20)
    for scope in approved.scopes:
        try:
            result = _empty_scope(scope, mount)
            removed += result.removed
            failures.extend(result.failures)
        except (OSError, ValueError) as exc:
            failures.append(f"{scope.directory}: {exc}")
    return BinEmptyResult(removed, tuple(failures))
