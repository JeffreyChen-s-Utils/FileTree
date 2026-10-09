"""Read-only native change feeds request fresh scans; notifications never grant source authority."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import stat
import sys
import threading

from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot

MAX_FOLDERS = 1_000_000
MAX_SHARED = 65536
MAX_CHANGED = 256
POLL_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class ChangeBatch:
    """Captured folder paths needing fresh scans, or a full-root request after loss/uncertainty."""

    folders: tuple[str, ...] = ()
    full: bool = False
    reason: str = ""


@dataclass(frozen=True, slots=True)
class WatchFolder:
    """A captured ordinary folder identity, never a notification-derived filesystem target."""

    path: str
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class WatchFile:
    """One observed shared ordinary inode and its captured parents, including external-alias changes."""

    path: str
    device: int
    inode: int
    parents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WatchScope:
    """Compact native feed metadata, separate from the scan tree and all operation approvals."""

    folders: tuple[WatchFolder, ...]
    shared: tuple[WatchFile, ...] = ()


def _shared_file(node: Node, device: int, files: dict) -> None:
    if node.is_dir or node.is_link or node.snapshot is None:
        return
    info = unpack_snapshot(node.snapshot)
    if not stat.S_ISREG(info.mode) or info.links <= 1:
        return
    if info.device != device or not info.inode or node.path is None or node.parent is None:
        raise ValueError("Shared watched file lacks a captured same-volume identity")
    if info.identity not in files:
        files[info.identity] = (node.path, set())
    files[info.identity][1].add(node.parent.path)
    if len(files) > MAX_SHARED:
        raise ValueError("Follow changes exceeds the shared-inode limit")


def captured_scope(root: Node, cancel: threading.Event) -> WatchScope:
    """Capture complete physical scopes off the GUI thread; links and mount nodes remain excluded."""
    if root.path is None or root.is_link or not root.is_dir or root.snapshot is None:
        raise ValueError("Follow changes requires a captured physical folder")
    coverage = coverage_of(root, cancel=cancel)
    if coverage is None:
        return WatchScope(())
    if not coverage.complete or coverage.unsafe:
        raise ValueError("Follow changes requires complete scan coverage")
    result, shared = [], {}
    device = unpack_snapshot(root.snapshot).device
    if not device:
        raise ValueError("Follow changes lacks a volume identity")
    for node in root.iter_nodes():
        if cancel.is_set():
            return WatchScope(())
        _shared_file(node, device, shared)
        if node.is_dir:
            give_way()
            if node.is_link:
                continue
            if node.snapshot is None:
                raise ValueError("Follow changes lacks a folder identity")
            info = unpack_snapshot(node.snapshot)
            if info.is_link or info.device != device or not info.inode or node.path is None:
                raise ValueError("Follow changes has an unknown folder identity")
            result.append(WatchFolder(node.path, info.device, info.inode))
            if len(result) > MAX_FOLDERS:
                raise ValueError("Follow changes exceeds the captured-folder limit")
    files = tuple(WatchFile(path, key[0], key[1], tuple(sorted(parents)))
                  for key, (path, parents) in shared.items())
    return WatchScope(tuple(result), files)


def check_folder(folder: WatchFolder) -> None:
    """Reject changed/linked folder paths; a passing observation grants no filesystem operation."""
    info = unpack_snapshot(stat_snapshot(folder.path))
    if (info.is_link or not stat.S_ISDIR(info.mode) or info.identity != (folder.device, folder.inode)
            or info.attributes & 0x400):
        raise ValueError("Watched folder identity changed")


def changed(folders: set[str], *, full: bool = False, reason: str = "") -> ChangeBatch:
    """Bound an event batch; too many affected folders conservatively request a full scan."""
    if full or len(folders) > MAX_CHANGED:
        return ChangeBatch(full=True, reason=reason or "overflow")
    return ChangeBatch(tuple(sorted(folders)), reason=reason)


def watch(root: Node, on_change: Callable[[ChangeBatch], None], cancel: threading.Event,
          *, ready: Callable[[str], None] | None = None) -> None:
    """Joinable native metadata feed; caller must rescan and separately revalidate later operations.

    Windows uses an existing NTFS USN journal when readable, otherwise one recursive directory
    handle. Linux uses one inotify descriptor and kernel watches for captured ordinary folders.
    No journal creation/deletion, payload reads, Qt watchers or filesystem mutations are involved.
    Overflow/gaps request full rescans; unsupported/failed feeds raise visible OSError/ValueError.
    Setup/rearm and concurrent scans remain observational rather than a consistent live snapshot.
    """
    scope = captured_scope(root, cancel)
    folders = scope.folders
    if not folders or cancel.is_set():
        return
    check_folder(folders[0])
    if sys.platform == "win32":
        from je_file_tree.core.windows_watch import watch_windows  # noqa: PLC0415 - native backend

        watch_windows(folders, on_change, cancel, ready, scope.shared)
    elif sys.platform.startswith("linux"):
        from je_file_tree.core.linux_watch import watch_linux  # noqa: PLC0415 - native backend

        watch_linux(folders, on_change, cancel, ready, scope.shared)
    else:
        raise ValueError("Follow changes is available on Windows and Linux")
