"""Find files with the same content anywhere in a scanned tree.

Files are compared in three rounds, each only among the files the round before left together:
the same size (no reading), the same hash of the first 64 KB, then the same hash of the whole
file. Hard links (one file under several names) are one file, not duplicates: they take the space
once. Files smaller than ``min_size`` (and always empty ones), links and files that cannot be read
(counted in ``DuplicateResult.skipped``) are left out.

Reading is what costs: on D:\\Codes (766,000 entries, measured 2026-09-26) 619,000 files share a size
with another one, and one thread had not finished reading their heads after ten minutes; from
1 MB up only 1,785 files do. Hence ``DEFAULT_MIN_SIZE``, and files are read by ``workers`` threads
(hashing and reading release the GIL).
"""

from __future__ import annotations

import hashlib
import os
import threading
from collections import defaultdict
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import BinaryIO

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.savings import Savings, estimate_savings

HEAD_BYTES = 64 * 1024
DEFAULT_MIN_SIZE = 1024 * 1024
DEFAULT_WORKERS = 4
_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    """Two or more files with the same content, each ``size`` bytes."""

    size: int
    files: list[Node]

    @property
    def extra(self) -> int:
        """Logical size of every copy but one; not unique allocation or recoverable space."""
        return self.size * (len(self.files) - 1)


@dataclass(frozen=True, slots=True)
class DuplicateResult:
    """The groups found (the most space taken by extra copies first) and what the search did."""

    groups: list[DuplicateGroup]
    files_read: int
    bytes_read: int
    skipped: int

    @property
    def extra(self) -> int:
        """Logical size of all extra copies; not an estimate of free-space recovery."""
        return sum(group.extra for group in self.groups)


@dataclass(frozen=True, slots=True)
class DuplicateSavings:
    """Extra-copy estimates assuming the first listed (oldest) copy of every group remains."""

    total: Savings
    groups: list[Savings]


def estimate_duplicate_savings(groups: list[DuplicateGroup], root: Node, *, limit: int = 1000,
                               cancel: threading.Event | None = None) -> DuplicateSavings | None:
    """Estimate all extra copies and the first ``limit`` groups on a worker, without reading contents.

    The ordering matches the current duplicate list; it is an accounting assumption, not an approval
    to remove copies. Other hard-link names can keep data allocated, and snapshots/shared extents or
    directory metadata remain unmeasured. A changed scan must discard this result.
    """
    all_extras: list[Node] = []
    by_group: list[Savings] = []
    for position, group in enumerate(groups):
        give_way()
        if cancel is not None and cancel.is_set():
            return None
        extras = sorted(group.files, key=lambda node: (node.modified, node.path))[1:]
        all_extras.extend(extras)
        if position < limit:
            value = estimate_savings(extras, root=root, cancel=cancel)
            if value is None:
                return None
            by_group.append(value)
    total = estimate_savings(all_extras, root=root, cancel=cancel)
    return DuplicateSavings(total, by_group) if total is not None else None


@dataclass(frozen=True, slots=True)
class DuplicateProgress:
    """How far a search is: files and bytes read so far, out of those known to need reading."""

    files_read: int
    files_total: int
    bytes_read: int
    bytes_total: int


ProgressCallback = Callable[[DuplicateProgress], None]


class DuplicateSearchCancelledError(Exception):
    """The search was stopped before it finished."""


def find_duplicates(root: Node, *, min_size: int = DEFAULT_MIN_SIZE, workers: int = DEFAULT_WORKERS,
                    progress: ProgressCallback | None = None,
                    cancel: threading.Event | None = None) -> DuplicateResult:
    """The groups of files with the same content beneath ``root`` (see the module docstring).

    ``progress`` is called (from the reading threads) after every file read; ``cancel`` is checked
    before every file and every 1 MB, and ``DuplicateSearchCancelledError`` is raised once it is set.
    """
    reader = _Reader(progress, cancel)
    same_size = [files for files in _by_size(root.iter_files(), max(min_size, 1)).values() if len(files) > 1]
    with ThreadPoolExecutor(max_workers=max(workers, 1), thread_name_prefix="file-tree-duplicates") as pool:
        same_head = reader.round(pool, same_size, whole=False)
        groups = [DuplicateGroup(files[0].size, files) for files in same_head if files[0].size <= HEAD_BYTES]
        longer = [files for files in same_head if files[0].size > HEAD_BYTES]
        groups += [DuplicateGroup(files[0].size, files) for files in reader.round(pool, longer, whole=True)]
    groups.sort(key=lambda group: (-group.extra, group.files[0].name.lower()))
    return DuplicateResult(groups, reader.files_read, reader.bytes_read, reader.skipped)


def _by_size(files: Iterable[Node], min_size: int) -> dict[int, list[Node]]:
    sizes: dict[int, list[Node]] = defaultdict(list)
    for node in files:
        if node.size >= min_size and node.error is None:
            sizes[node.size].append(node)
    return sizes


class _Reader:
    """Hashes files on a thread pool, counting what it read."""

    def __init__(self, progress: ProgressCallback | None, cancel: threading.Event | None) -> None:
        self._progress = progress
        self._cancel = cancel
        self._lock = threading.Lock()
        self.files_read = 0
        self.bytes_read = 0
        self.skipped = 0
        self._files_total = 0
        self._bytes_total = 0

    def round(self, pool: ThreadPoolExecutor, groups: list[list[Node]], *, whole: bool) -> list[list[Node]]:
        """Split each group into groups of two or more with the same hash (of the head, or ``whole``)."""
        files = [node for group in groups for node in group]
        with self._lock:
            self._files_total += len(files)
            self._bytes_total += sum(node.size if whole else min(node.size, HEAD_BYTES) for node in files)
        futures = [pool.submit(self._hash, node, whole) for node in files]
        try:
            hashes = [future.result() for future in futures]
        except DuplicateSearchCancelledError:
            for future in futures:
                future.cancel()
            raise
        return _regroup(groups, iter(hashes))

    def _hash(self, node: Node, whole: bool) -> tuple[tuple[int, int], bytes] | None:
        """``(file identity, hash)`` of ``node``'s head or whole content; None when it cannot be read."""
        self._check()
        give_way()
        hasher = hashlib.blake2b(digest_size=16)
        try:
            with open(node.path, "rb") as stream:
                info = os.fstat(stream.fileno())
                read = self._read_into(hasher, stream, node.size if whole else HEAD_BYTES)
        except OSError:
            with self._lock:
                self.skipped += 1
            return None
        with self._lock:
            self.files_read += 1
            self.bytes_read += read
            snapshot = DuplicateProgress(self.files_read, self._files_total, self.bytes_read, self._bytes_total)
        if self._progress is not None:
            self._progress(snapshot)
        return (info.st_dev, info.st_ino), hasher.digest()

    def _read_into(self, hasher: hashlib._Hash, stream: BinaryIO, limit: int) -> int:
        read = 0
        while read < limit:
            chunk = stream.read(min(_CHUNK_BYTES, limit - read))
            if not chunk:
                break
            hasher.update(chunk)
            read += len(chunk)
            self._check()
        return read

    def _check(self) -> None:
        if self._cancel is not None and self._cancel.is_set():
            raise DuplicateSearchCancelledError


def _regroup(groups: list[list[Node]], hashes: Iterable[tuple[tuple[int, int], bytes] | None]) -> list[list[Node]]:
    """The groups split by hash (in the order the files were handed out), each hard-linked file counted once."""
    result: list[list[Node]] = []
    for group in groups:
        by_hash: dict[bytes, list[Node]] = defaultdict(list)
        identities: set[tuple[int, int]] = set()
        for node in group:
            found = next(hashes)
            if found is None:
                continue
            identity, digest = found
            if identity[1] and identity in identities:
                continue  # another name of a file already counted
            identities.add(identity)
            by_hash[digest].append(node)
        result.extend(same for same in by_hash.values() if len(same) > 1)
    return result
