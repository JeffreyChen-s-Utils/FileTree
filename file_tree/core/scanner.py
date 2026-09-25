"""Read a folder tree into ``Node`` objects.

Several worker threads read folders at the same time: listing a folder spends
most of its time waiting on the file system with the interpreter lock
released, so on a disk with many folders the waits overlap. The walk never
follows links (symlinks and Windows junctions are recorded with size 0, so a
link loop cannot make a scan run forever), and it keeps going past folders it
cannot read: those get ``Node.error`` and an entry in ``ScanResult.errors``.
Totals are added up bottom-up once every folder has been read.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from file_tree.core.node import Node

# Windows reparse tags of links that must not be followed. A junction (and a
# volume mounted into a folder) is a mount point; ``is_symlink()`` is False for
# it, and ``is_dir(follow_symlinks=False)`` is True, so only the tag tells.
_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
_IO_REPARSE_TAG_SYMLINK = 0xA000000C
_LINK_REPARSE_TAGS = frozenset({_IO_REPARSE_TAG_MOUNT_POINT, _IO_REPARSE_TAG_SYMLINK})
_FILE_ATTRIBUTE_HIDDEN = 0x2

# Measured on an SSD (warm cache): 1 thread 1.27 s, 2 0.88 s, 4 0.67 s, 8 0.72 s for
# 62k files; past four the threads mostly wait for the interpreter lock.
DEFAULT_WORKERS = min(4, os.cpu_count() or 1)


class ScanCancelledError(Exception):
    """Raised by ``scan`` when its ``cancel`` event is set."""


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """What a scan includes and how many folders it reads at once."""

    include_hidden: bool = True
    workers: int = DEFAULT_WORKERS


@dataclass(frozen=True, slots=True)
class ScanProgress:
    """A snapshot of a running scan, for progress displays."""

    files: int
    folders: int
    size: int
    current: str


@dataclass(slots=True)
class ScanResult:
    """A finished scan: the tree, the entries that could not be read, and how long it took."""

    root: Node
    errors: list[tuple[str, str]] = field(default_factory=list)
    elapsed: float = 0.0


ProgressCallback = Callable[[ScanProgress], None]


@dataclass(slots=True)
class _FolderRead:
    """What reading one folder found."""

    subfolders: list[tuple[Node, str]] = field(default_factory=list)
    files: int = 0
    size: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


def scan(path: str | os.PathLike[str], *, options: ScanOptions | None = None,
         progress: ProgressCallback | None = None, cancel: threading.Event | None = None,
         progress_interval: float = 0.1) -> ScanResult:
    """Scan the folder at ``path`` and return its tree.

    ``progress`` is called about every ``progress_interval`` seconds (and once
    at the end), always from the calling thread. Setting ``cancel`` stops the
    scan with ``ScanCancelledError`` within one interval.

    :raises NotADirectoryError: when ``path`` is not an existing folder
    :raises ScanCancelledError: when ``cancel`` is set during the scan
    """
    root_path = os.path.abspath(os.fspath(path))
    if not os.path.isdir(root_path):
        raise NotADirectoryError(root_path)
    options = options or ScanOptions()
    started = time.monotonic()
    root = Node(name=root_path, is_dir=True, children=[])
    crawler = _Crawler(root, root_path, options)
    crawler.run(progress, cancel, progress_interval)
    _add_up(crawler.folders)
    if progress is not None:
        progress(crawler.snapshot())
    return ScanResult(root=root, errors=crawler.errors, elapsed=time.monotonic() - started)


class _Crawler:
    """Worker threads sharing one stack of folders still to read."""

    def __init__(self, root: Node, root_path: str, options: ScanOptions) -> None:
        self._options = options
        self._pending: list[tuple[Node, str]] = [(root, root_path)]
        self._busy = 0
        self._stopped = False
        self._failure: BaseException | None = None
        self._condition = threading.Condition()
        self._done = threading.Event()
        self._current = root_path
        self.folders: list[Node] = [root]  # every folder after its parent
        self.errors: list[tuple[str, str]] = []
        self.files = 0
        self.size = 0

    def snapshot(self) -> ScanProgress:
        """The counts so far."""
        with self._condition:
            return ScanProgress(self.files, len(self.folders) - 1, self.size, self._current)

    def run(self, progress: ProgressCallback | None, cancel: threading.Event | None,
            interval: float) -> None:
        """Read every folder, reporting progress and watching ``cancel`` from this thread."""
        if cancel is not None and cancel.is_set():
            raise ScanCancelledError
        threads = [threading.Thread(target=self._work, name=f"file-tree-scan-{number}", daemon=True)
                   for number in range(max(1, self._options.workers))]
        for thread in threads:
            thread.start()
        try:
            while not self._done.wait(interval):
                if cancel is not None and cancel.is_set():
                    raise ScanCancelledError
                if progress is not None:
                    progress(self.snapshot())
        finally:
            self._stop()
            for thread in threads:
                thread.join()
        if self._failure is not None:
            raise self._failure

    def _stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()
        self._done.set()

    def _work(self) -> None:
        while (task := self._take()) is not None:
            try:
                read = _read_folder(task[0], task[1], self._options)
            except BaseException as error:  # noqa: BLE001 - handed to the calling thread, which re-raises it
                with self._condition:
                    self._failure = error
                self._stop()
                return
            self._finish(task[1], read)

    def _take(self) -> tuple[Node, str] | None:
        """The next folder to read, or None once there is nothing left anywhere."""
        with self._condition:
            while not self._pending and self._busy and not self._stopped:
                self._condition.wait()
            if self._stopped or not self._pending:
                self._condition.notify_all()
                self._done.set()
                return None
            self._busy += 1
            return self._pending.pop()

    def _finish(self, path: str, read: _FolderRead) -> None:
        with self._condition:
            self._busy -= 1
            self._pending.extend(read.subfolders)
            self.folders.extend(node for node, _ in read.subfolders)
            self.files += read.files
            self.size += read.size
            self.errors.extend(read.errors)
            self._current = path
            if read.subfolders:
                self._condition.notify(len(read.subfolders))
            elif not self._busy and not self._pending:
                self._condition.notify_all()


def _read_folder(folder: Node, path: str, options: ScanOptions) -> _FolderRead:
    """Add ``folder``'s entries as its children and report what was found."""
    read = _FolderRead()
    try:
        with os.scandir(path) as entries:
            listing = list(entries)
    except OSError as error:
        folder.error = _describe(error)
        read.errors.append((path, folder.error))
        return read
    children = cast(list[Node], folder.children)  # folders are always created with a list
    for entry in listing:
        child = _entry_node(entry, options, read)
        if child is None:
            continue
        child.parent = folder
        children.append(child)
        if child.is_dir and not child.is_link:
            read.subfolders.append((child, entry.path))
    return read


def _entry_node(entry: os.DirEntry[str], options: ScanOptions, read: _FolderRead) -> Node | None:
    """The node for one directory entry, or None when it is skipped or unreadable."""
    try:
        info = entry.stat(follow_symlinks=False)
    except FileNotFoundError:
        return None  # removed while we were scanning
    except OSError as error:
        read.errors.append((entry.path, _describe(error)))
        return None
    if not options.include_hidden and _is_hidden(entry.name, info):
        return None
    if entry.is_symlink() or getattr(info, "st_reparse_tag", 0) in _LINK_REPARSE_TAGS:
        return Node(name=entry.name, is_dir=_points_to_folder(entry), modified=info.st_mtime,
                    is_link=True)
    if entry.is_dir(follow_symlinks=False):
        return Node(name=entry.name, is_dir=True, modified=info.st_mtime, children=[])
    read.files += 1
    read.size += info.st_size
    return Node(name=entry.name, is_dir=False, size=info.st_size, file_count=1,
                modified=info.st_mtime)


def _is_hidden(name: str, info: os.stat_result) -> bool:
    return name.startswith(".") or bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_HIDDEN)


def _points_to_folder(entry: os.DirEntry[str]) -> bool:
    """Whether a link's target is a folder (False when the target is missing or unreadable)."""
    try:
        return entry.is_dir(follow_symlinks=True)
    except OSError:
        return False


def _describe(error: OSError) -> str:
    return error.strerror or type(error).__name__


def _size_first(node: Node) -> tuple[int, str]:
    return -node.size, node.name.lower()


def _add_up(folders: list[Node]) -> None:
    """Fill in folder totals, deepest folders first, and sort each folder's children largest first.

    ``folders`` must list every folder after its parent.
    """
    for folder in reversed(folders):
        size = files = subfolders = 0
        newest = folder.modified
        children = folder.children
        for child in children:
            size += child.size
            files += child.file_count
            if child.is_dir and not child.is_link:
                subfolders += 1 + child.dir_count
            newest = max(newest, child.modified)
        folder.size = size
        folder.file_count = files
        folder.dir_count = subfolders
        folder.modified = newest
        if isinstance(children, list):
            children.sort(key=_size_first)
