"""Complete current-user Finder Trash approval and fixed global OS emptying, never path deletion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import ctypes
import os
from pathlib import Path
import subprocess  # nosec B404 - fixed osascript command, no shell or path interpolation
import sys
import tempfile
import threading

from je_file_tree.core.bin_empty import (MAX_ENTRIES, MAX_DEPTH, BinEntry, BinSurveyCancelledError,
                                        _absolute_directory, _check, _entry, _names, _DIRECTORY_FLAGS)
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import pack_snapshot, unpack_snapshot
from je_file_tree.core.trash_size import TrashUsage

MAX_ROOTS = 256
_ERROR_BYTES = 64 * 1024
_SCRIPT = 'tell application "Finder" to empty the trash'
MountProvider = Callable[[], tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class FinderScope:
    """Recognized private user Trash path and full bounded no-follow metadata inventory."""

    directory: str
    snapshot: bytes
    entries: tuple[BinEntry, ...]
    size: int
    count: int


@dataclass(frozen=True, slots=True)
class FinderEmptyPlan:
    """Finder-wide approval: all OS-reported mounted roots, current uid and deduplicated scopes."""

    roots: tuple[str, ...]
    uid: int
    scopes: tuple[FinderScope, ...]
    usage: TrashUsage


def _require_mac() -> None:
    if sys.platform != "darwin" or os.name != "posix":
        raise ValueError("Finder emptying requires macOS")
    _current_user()


def _current_user() -> int:
    uid = os.getuid()
    if not uid or os.geteuid() != uid or _console_uid() != uid:
        raise ValueError("Finder emptying requires the logged-in console user, without elevated identity")
    return uid


def _console_uid() -> int:
    configuration = ctypes.CDLL("/System/Library/Frameworks/SystemConfiguration.framework/SystemConfiguration")
    foundation = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    try:
        query, release = configuration.SCDynamicStoreCopyConsoleUser, foundation.CFRelease
    except AttributeError as exc:
        raise OSError("Console user query is unavailable") from exc
    query.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]
    query.restype = ctypes.c_void_p
    release.argtypes, release.restype = [ctypes.c_void_p], None
    uid = ctypes.c_uint32()
    user = query(None, ctypes.byref(uid), None)
    if not user:
        raise OSError("No logged-in primary console user could be identified")
    try:
        return uid.value
    finally:
        release(user)


def _home() -> Path:
    import pwd  # noqa: PLC0415 - POSIX account API is unavailable on Windows
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError as exc:
        raise OSError("The current user's account home directory is unavailable") from exc


def _roots(provider: MountProvider) -> tuple[str, ...]:
    roots = tuple(sorted(set(provider())))
    if not roots or len(roots) > MAX_ROOTS:
        raise ValueError("Incomplete or oversized mounted-volume inventory")
    for root in roots:
        path = Path(root)
        if not path.is_absolute() or str(path.resolve(strict=True)) != root or not path.is_dir():
            raise ValueError("Mounted roots must be canonical absolute directories")
    return roots


def _relative(fd: int, parts: tuple[str, ...], device: int,
              identities: dict[tuple[str, ...], bytes]) -> int:
    current = os.dup(fd)
    prefix: tuple[str, ...] = ()
    try:
        for part in parts:
            child = os.open(part, _DIRECTORY_FLAGS, dir_fd=current)
            os.close(current)
            current = child
            prefix = (*prefix, part)
            info = os.fstat(current)
            expected = unpack_snapshot(identities[prefix])
            if info.st_dev != device or info.st_uid != os.getuid() or expected.identity != (info.st_dev, info.st_ino):
                raise OSError("Finder Trash ancestor changed or crossed a volume")
        return current
    except (OSError, ValueError, KeyError):
        os.close(current)
        raise


def _inventory(fd: int, path: Path, roots: tuple[str, ...], cancel: threading.Event | None,
               limit: int) -> tuple[tuple[BinEntry, ...], int, int]:
    entries, stack = [], [()]
    identities: dict[tuple[str, ...], bytes] = {}
    size = count = 0
    device = os.fstat(fd).st_dev
    while stack:
        _check(cancel)
        give_way()
        parts = stack.pop()
        folder = _relative(fd, parts, device, identities)
        try:
            for name in _names(folder, limit - len(entries), cancel):
                _check(cancel)
                if len(parts) >= MAX_DEPTH:
                    raise OSError("Finder Trash approval exceeds depth limits")
                entry = _entry(os.stat(name, dir_fd=folder, follow_symlinks=False), (*parts, name))
                if str(path.joinpath(*entry.parts)) in roots or unpack_snapshot(entry.snapshot).device != device:
                    raise OSError("Mounted entry inside Finder Trash")
                entries.append(entry)
                count += int(not parts)
                if entry.directory:
                    identities[entry.parts] = entry.snapshot
                    stack.append(entry.parts)
                else:
                    size += unpack_snapshot(entry.snapshot).size
        finally:
            os.close(folder)
    return tuple(entries), size, count


def _private(fd: int) -> bytes:
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or info.st_mode & 0o077 or not info.st_dev or not info.st_ino:
        raise OSError("Finder Trash scope is not an identified private current-user directory")
    return pack_snapshot(info)


def _known_scope(path: Path, snapshot: bytes) -> None:
    with _absolute_directory(path) as fd:
        if _private(fd) != snapshot or pack_snapshot(path.lstat()) != snapshot:
            raise OSError("Known Finder Trash scope changed at its alias")


def _scope(path: Path, roots: tuple[str, ...], cancel: threading.Event | None, limit: int) -> FinderScope:
    with _absolute_directory(path) as fd:
        before = _private(fd)
        entries, size, count = _inventory(fd, path, roots, cancel, limit)
        if _private(fd) != before or pack_snapshot(path.lstat()) != before:
            raise OSError("Finder Trash scope changed during approval")
    return FinderScope(str(path), before, entries, size, count)


def prepare_finder_empty(provider: MountProvider, *, cancel: threading.Event | None = None) -> FinderEmptyPlan | None:
    """Survey Finder-wide current-user Trash using a complete trusted native mount provider.

    The GUI supplies all QStorageInfo mounted roots, refuses unavailable/omitted roots and rechecks this
    provider throughout approval. Deduplicate physical scopes; incomplete information disables deletion.
    Logical payload bytes exclude directory metadata and never promise recoverable capacity.
    """
    _require_mac()
    if cancel is not None and cancel.is_set():
        return None
    roots = _roots(provider)
    candidates = (_home() / ".Trash", *(Path(root) / ".Trashes" / str(os.getuid()) for root in roots))
    scopes, errors, seen = [], [], {}
    remaining = MAX_ENTRIES
    try:
        for path in dict.fromkeys(candidates):
            _check(cancel)
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                errors.append(f"{path}: {exc}")
                continue
            try:
                identity = (info.st_dev, info.st_ino)
                if identity in seen:
                    _known_scope(path, seen[identity])
                    continue
                scope = _scope(path, roots, cancel, remaining)
                identity = unpack_snapshot(scope.snapshot).identity
                scopes.append(scope)
                seen[identity] = scope.snapshot
                remaining -= len(scope.entries)
            except (OSError, ValueError) as exc:
                errors.append(f"{path}: {exc}")
        _check(cancel)
        if _roots(provider) != roots:
            errors.append("Mounted volumes changed during Finder Trash survey")
        _require_mac()
    except BinSurveyCancelledError:
        return None
    usage = TrashUsage(sum(scope.size for scope in scopes), sum(scope.count for scope in scopes),
                       not errors, "; ".join(errors[:3]))
    return FinderEmptyPlan(roots, os.getuid(), tuple(scopes), usage)


def _run_finder_empty() -> None:
    # Default AppleScript application responses are awaited; never use "ignoring responses".
    with tempfile.TemporaryFile() as errors:
        result = subprocess.run(["/usr/bin/osascript", "-e", _SCRIPT], check=False,  # noqa: S603 # nosec B603
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors)
        if result.returncode:
            errors.seek(0)
            reason = errors.read(_ERROR_BYTES).decode("utf-8", "replace")
            raise OSError(f"Finder emptying failed ({result.returncode}): {reason}; "
                          "Finder may still be working; refresh to inspect remaining contents")


def empty_finder_bin(approved: FinderEmptyPlan, provider: MountProvider) -> TrashUsage:
    """After two Finder-wide questions, recheck all metadata then call only fixed Finder osascript.

    Finder acts on all current-user mounted Trash, including new arrivals during its operation. No
    arbitrary paths are passed, no direct deletion occurs and active emptying is never terminated.
    Native automation/permission/partial failures remain visible; macOS validation is still required.
    """
    _require_mac()
    if approved.uid != os.getuid() or not approved.usage.complete or approved.usage.count <= 0:
        raise ValueError("Complete nonempty current-user Finder-wide approval required")
    if prepare_finder_empty(provider) != approved:
        raise ValueError("Finder Trash or mounted volumes changed; refresh and review again")
    _require_mac()
    _run_finder_empty()
    remaining = prepare_finder_empty(provider)
    if remaining is not None and remaining.roots != approved.roots:
        raise OSError("Mounted volumes changed during Finder emptying; refresh to inspect the global scope")
    if remaining is None or not remaining.usage.complete or remaining.usage.count:
        raise OSError("Finder Trash remains nonempty or unavailable; refresh to inspect partial results")
    return remaining.usage
