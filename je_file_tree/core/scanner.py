"""Read a folder tree into ``Node`` objects.

Several worker threads read folders at the same time: listing a folder spends
most of its time waiting on the file system with the interpreter lock
released, so on a disk with many folders the waits overlap. The walk never
follows links (symlinks and Windows junctions are recorded with size 0, so a
link loop cannot make a scan run forever), and it keeps going past folders it
cannot read: those get ``Node.error`` and an entry in ``ScanResult.errors``.

The tree can be shown while it is being read (``on_root`` hands out the root
first): whenever a folder has been listed, its files are added to the totals
of every folder above it, so sizes grow as the scan goes. Children are only
ever appended during the scan; once every folder is read, the totals are
added up again bottom-up and each folder's children sorted largest first.
"""

from __future__ import annotations

import errno
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from je_file_tree.core.allocation import Allocation, allocation_for
from je_file_tree.core.exclusions import Excluded, exclusion_test
from je_file_tree.core.node import Node

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


# The common reasons are worded here instead of taken from the OS, whose text
# is in the system's language (a Chinese Windows answers 存取被拒。 in an
# English window); the GUI translates these, exports keep them as they are.
ACCESS_DENIED = "access denied"
NOT_FOUND = "not found"
PATH_TOO_LONG = "path too long"
_REASON_BY_ERRNO = {errno.EACCES: ACCESS_DENIED, errno.EPERM: ACCESS_DENIED, errno.ENOENT: NOT_FOUND,
                    errno.ENAMETOOLONG: PATH_TOO_LONG}
_WINDOWS_PATH_TOO_LONG = 206  # ERROR_FILENAME_EXCED_RANGE

# ``Node.error`` of a folder the scan never got to because it was stopped.
NOT_SCANNED = "not scanned: the scan was stopped first"
EXCLUDED = "excluded: skipped by the exclusions"


class ScanCancelledError(Exception):
    """Raised by ``scan`` when its ``cancel`` event is set.

    ``partial`` is what was read before the stop, added up and sorted like a
    finished scan; folders never read have ``error == NOT_SCANNED`` (when the
    stop came before anything was read, that is the root itself).
    """

    def __init__(self, partial: ScanResult | None = None) -> None:
        super().__init__("scan cancelled")
        self.partial = partial


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """What a scan includes and how many folders it reads at once."""

    include_hidden: bool = True
    workers: int = DEFAULT_WORKERS
    exclude: tuple[str, ...] = ()  # folder name patterns and folder paths to skip (see core/exclusions.py)


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
RootCallback = Callable[[Node], None]


@dataclass(slots=True)
class _FolderRead:
    """What reading one folder found."""

    subfolders: list[tuple[Node, str]] = field(default_factory=list)
    files: int = 0
    size: int = 0
    allocated: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


def scan(path: str | os.PathLike[str], *, options: ScanOptions | None = None,  # noqa: PLR0913
         progress: ProgressCallback | None = None, cancel: threading.Event | None = None,
         progress_interval: float = 0.1, on_root: RootCallback | None = None) -> ScanResult:
    """Scan the folder at ``path`` and return its tree.

    ``on_root`` is called once with the (still empty) root before any folder is
    read, for showing the tree while it grows. ``progress`` is called about
    every ``progress_interval`` seconds (and once at the end). Both run on the
    calling thread. Setting ``cancel`` stops the scan within one interval.

    :raises NotADirectoryError: when ``path`` is not an existing folder
    :raises ScanCancelledError: when ``cancel`` is set; ``partial`` holds what was read
    """
    root_path = os.path.abspath(os.fspath(path))
    if not os.path.isdir(root_path):
        raise NotADirectoryError(root_path)
    options = options or ScanOptions()
    started = time.monotonic()
    root = Node(name=root_path, is_dir=True, children=[])
    if on_root is not None:
        on_root(root)
    crawler = _Crawler(root, root_path, options, cancel)
    try:
        crawler.run(progress, cancel, progress_interval)
    except ScanCancelledError:
        for folder, _ in crawler.unread():
            folder.error = NOT_SCANNED
        _add_up(crawler.folders)
        raise ScanCancelledError(ScanResult(root, crawler.errors, time.monotonic() - started)) from None
    _add_up(crawler.folders)
    if progress is not None:
        progress(crawler.snapshot())
    return ScanResult(root=root, errors=crawler.errors, elapsed=time.monotonic() - started)


class _Crawler:
    """Worker threads sharing one stack of folders still to read."""

    def __init__(self, root: Node, root_path: str, options: ScanOptions,
                 cancel: threading.Event | None = None) -> None:
        self._options = options
        self._allocation = allocation_for(root_path)
        self._excluded = exclusion_test(options.exclude)
        self._cancel = cancel
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

    def unread(self) -> list[tuple[Node, str]]:
        """The folders still waiting to be read (after ``run`` has returned or raised)."""
        with self._condition:
            return list(self._pending)

    def snapshot(self) -> ScanProgress:
        """The counts so far."""
        with self._condition:
            return ScanProgress(self.files, len(self.folders) - 1, self.size, self._current)

    def run(self, progress: ProgressCallback | None, cancel: threading.Event | None,
            interval: float) -> None:
        """Read every folder, reporting progress and watching ``cancel`` from this thread.

        The workers watch ``cancel`` too and take no new folder once it is set,
        so a stop is immediate instead of up to one ``interval`` late; the
        folders already being read finish.
        """
        if cancel is not None and cancel.is_set():
            raise ScanCancelledError
        threads = [threading.Thread(target=self._work, name=f"file-tree-scan-{number}", daemon=True)
                   for number in range(max(1, self._options.workers))]
        for thread in threads:
            thread.start()
        try:
            while not self._done.wait(interval):
                if cancel is not None and cancel.is_set():
                    break
                if progress is not None:
                    progress(self.snapshot())
        finally:
            self._stop()
            for thread in threads:
                thread.join()
        if self._failure is not None:
            raise self._failure
        if cancel is not None and cancel.is_set():
            raise ScanCancelledError

    def _stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()
        self._done.set()

    def _work(self) -> None:
        while (task := self._take()) is not None:
            try:
                read = _read_folder(task[0], task[1], self._options, self._allocation, self._excluded)
            except BaseException as error:  # noqa: BLE001 - handed to the calling thread, which re-raises it
                with self._condition:
                    self._failure = error
                self._stop()
                return
            self._finish(task[0], task[1], read)

    def _take(self) -> tuple[Node, str] | None:
        """The next folder to read, or None once there is nothing left anywhere."""
        with self._condition:
            while not self._pending and self._busy and not self._stopped:
                self._condition.wait()
            cancelled = self._cancel is not None and self._cancel.is_set()
            if self._stopped or cancelled or not self._pending:
                self._condition.notify_all()
                self._done.set()
                return None
            self._busy += 1
            return self._pending.pop()

    def _finish(self, folder: Node, path: str, read: _FolderRead) -> None:
        with self._condition:
            self._busy -= 1
            self._pending.extend(read.subfolders)
            self.folders.extend(node for node, _ in read.subfolders)
            self.files += read.files
            self.size += read.size
            self.errors.extend(read.errors)
            self._current = path
            _add_to_ancestors(folder, read)
            if read.subfolders:
                self._condition.notify(len(read.subfolders))
            elif not self._busy and not self._pending:
                self._condition.notify_all()


def _add_to_ancestors(folder: Node, read: _FolderRead) -> None:
    """Count what reading ``folder`` found into it and every folder above it (running totals)."""
    subfolders = len(read.subfolders)
    node: Node | None = folder
    while node is not None:
        node.size += read.size
        node.allocated += read.allocated
        node.file_count += read.files
        node.dir_count += subfolders
        node = node.parent


def _read_folder(folder: Node, path: str, options: ScanOptions, allocation: Allocation,
                 excluded: Excluded | None = None) -> _FolderRead:
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
        child = _entry_node(entry, options, read, allocation, excluded)
        if child is None:
            continue
        child.parent = folder
        children.append(child)
        if child.is_dir and not child.is_link and child.error is None:
            read.subfolders.append((child, entry.path))
    return read


def _entry_node(entry: os.DirEntry[str], options: ScanOptions, read: _FolderRead,
                allocation: Allocation, excluded: Excluded | None = None) -> Node | None:
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
        return _folder_node(entry, info.st_mtime, excluded)
    allocated = allocation(entry, info)
    read.files += 1
    read.size += info.st_size
    read.allocated += allocated
    return Node(name=entry.name, is_dir=False, size=info.st_size, allocated=allocated, file_count=1,
                modified=info.st_mtime)


def _folder_node(entry: os.DirEntry[str], modified: float, excluded: Excluded | None) -> Node:
    """A folder to read, or, when the exclusions match it, one that is listed but never read."""
    skipped = excluded is not None and excluded(entry.name, entry.path)
    return Node(name=entry.name, is_dir=True, modified=modified, error=EXCLUDED if skipped else None, children=[])


def _is_hidden(name: str, info: os.stat_result) -> bool:
    return name.startswith(".") or bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_HIDDEN)


def _points_to_folder(entry: os.DirEntry[str]) -> bool:
    """Whether a link's target is a folder (False when the target is missing or unreadable)."""
    try:
        return entry.is_dir(follow_symlinks=True)
    except OSError:
        return False


def _describe(error: OSError) -> str:
    """One of the worded reasons above, or the system's own text for anything else."""
    if getattr(error, "winerror", None) == _WINDOWS_PATH_TOO_LONG:
        return PATH_TOO_LONG
    return _REASON_BY_ERRNO.get(error.errno) or error.strerror or type(error).__name__


def _size_first(node: Node) -> tuple[int, str]:
    return -node.size, node.name.lower()


def _add_up(folders: list[Node]) -> None:
    """Fill in folder totals, deepest folders first, and sort each folder's children largest first.

    ``folders`` must list every folder after its parent.
    """
    for folder in reversed(folders):
        size = allocated = files = subfolders = 0
        newest = folder.modified
        children = folder.children
        for child in children:
            size += child.size
            allocated += child.allocated
            files += child.file_count
            if child.is_dir and not child.is_link and child.error != EXCLUDED:
                subfolders += 1 + child.dir_count
            newest = max(newest, child.modified)
        folder.size = size
        folder.allocated = allocated
        folder.file_count = files
        folder.dir_count = subfolders
        folder.modified = newest
        if isinstance(children, list):
            children.sort(key=_size_first)
