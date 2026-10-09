"""Bounded read-only archive inventories, kept outside the scanned filesystem tree."""

from __future__ import annotations

import os
import io
import stat
import threading
import zipfile
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import BinaryIO

from je_file_tree.core.duplicates import _check_snapshot
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import pack_snapshot, stat_snapshot, unpack_snapshot

MAX_METADATA_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 100_000
MAX_NAME_LENGTH = 1024
MAX_DEPTH = 128
CONTROL_CHAR_LIMIT = 32


class ArchiveError(OSError):
    """An archive is unavailable, unsafe, changed, malformed or exceeds inventory limits."""


class ArchiveCancelledError(Exception):
    """The caller stopped an archive inventory."""


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    """An untrusted archive member name and declared uncompressed bytes, never a disk path."""

    name: str
    size: int
    is_dir: bool = False
    is_link: bool = False


@dataclass(slots=True, eq=False)
class VirtualEntry(Node):
    """Display-only entry; never attached to the actual scanned Node.children tree."""

    member: str = ""


@dataclass(frozen=True, slots=True)
class ArchiveInventory:
    """Virtual children and declared totals; rejected names make the inventory incomplete."""

    children: list[VirtualEntry]
    files: int
    size: int
    rejected: int


class MetadataReader(io.BufferedIOBase):
    """Seekable wrapper limiting cumulative parser reads; checks Stop before each read/seek."""

    def __init__(self, stream: BinaryIO, cancel: threading.Event | None) -> None:
        self._stream, self._cancel = stream, cancel
        self._remaining = MAX_METADATA_BYTES

    def read(self, size: int = -1) -> bytes:
        """Read only within the shared metadata budget; unbounded reads are refused."""
        _check_cancel(self._cancel)
        if size < 0:
            position = self._stream.tell()
            size = self._stream.seek(0, os.SEEK_END) - position
            self._stream.seek(position)
        if size > self._remaining:
            raise ArchiveError("Archive metadata exceeds the 32 MiB read budget")
        data = self._stream.read(size)
        self._remaining -= len(data)
        return data

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        """Seek without reading member data."""
        _check_cancel(self._cancel)
        return self._stream.seek(offset, whence)

    def tell(self) -> int:
        """Current offset in the opened archive."""
        return self._stream.tell()

    def seekable(self) -> bool:
        """Archive metadata readers require random access."""
        return True


ArchiveReader = Callable[[MetadataReader], Iterable[ArchiveMember]]


def zip_members(stream: MetadataReader) -> Iterable[ArchiveMember]:
    """List ZIP central-directory entries without opening or decompressing a member."""
    try:
        with zipfile.ZipFile(stream) as archive:
            for info in archive.infolist():
                mode = info.external_attr >> 16
                yield ArchiveMember(info.filename, info.file_size, info.is_dir(), stat.S_ISLNK(mode))
    except (zipfile.BadZipFile, NotImplementedError, EOFError, ValueError) as exc:
        raise ArchiveError(str(exc)) from exc


@contextmanager
def _opened(node: Node) -> Iterator[BinaryIO]:
    current = stat_snapshot(node.path)
    _check_snapshot(node, current)
    if not stat.S_ISREG(unpack_snapshot(current).mode):
        raise ArchiveError("Only regular recorded files can be read")
    # A FIFO substituted after the path check must not block the worker before fstat can refuse it.
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))
    descriptor = os.open(node.path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        before = pack_snapshot(os.fstat(stream.fileno()))
        _check_snapshot(node, before, descriptor=True)
        yield stream
        if before != pack_snapshot(os.fstat(stream.fileno())):
            raise ArchiveError("Archive metadata changed while reading")
        _check_snapshot(node, stat_snapshot(node.path))


def read_archive(node: Node, *, reader: ArchiveReader = zip_members,
                 cancel: threading.Event | None = None) -> ArchiveInventory:
    """Read guarded metadata in a worker; preserve source bytes/totals and never extract members.

    Known cloud/link entries are refused. Cancellation is checked between parser reads and members;
    a parser's current header decoding call must finish before its thread can be joined.
    """
    _check_cancel(cancel)
    with _opened(node) as stream:
        result = _inventory(node, reader(MetadataReader(stream, cancel)), cancel)
    _check_cancel(cancel)
    return result


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise ArchiveCancelledError


def _parts(name: str) -> list[str] | None:
    parts = name.replace("\\", "/").rstrip("/").split("/")
    if (not name or len(name) > MAX_NAME_LENGTH or len(parts) > MAX_DEPTH
            or any(part in ("", ".", "..") or ":" in part
                   or any(ord(char) < CONTROL_CHAR_LIMIT for char in part) for part in parts)):
        return None
    return parts


def _inventory(source: Node, members: Iterable[ArchiveMember], cancel: threading.Event | None) -> ArchiveInventory:
    virtual_root = VirtualEntry("", True, parent=source, children=[])
    entries: dict[str, VirtualEntry] = {"": virtual_root}
    rejected, files, size = 0, 0, 0
    for count, member in enumerate(members, 1):
        _check_cancel(cancel)
        give_way()
        if count > MAX_MEMBERS:
            raise ArchiveError("Archive has more than 100,000 members")
        parts = _parts(member.name)
        if parts is None or member.is_link or member.size < 0 or member.size > 2**63 - 1:
            rejected += 1
            continue
        if not _add_member(entries, parts, member):
            rejected += 1
        elif not member.is_dir:
            files += 1
            size += member.size
    _rollup(virtual_root, cancel)
    # The synthetic container is not shown; top-level parents point at the real archive file.
    for child in virtual_root.children:
        child.parent = source
    return ArchiveInventory(list(virtual_root.children), files, size, rejected)


def _add_member(entries: dict[str, VirtualEntry], parts: list[str], member: ArchiveMember) -> bool:
    parent, path = entries[""], ""
    for position, part in enumerate(parts):
        path = f"{path}/{part}" if path else part
        folder = position < len(parts) - 1 or member.is_dir
        found = entries.get(path)
        if found is not None:
            if not found.is_dir or not folder:
                return False
        else:
            if len(entries) > MAX_MEMBERS:
                raise ArchiveError("Archive virtual tree exceeds 100,000 entries")
            found = VirtualEntry(part, folder, size=0 if folder else member.size, parent=parent,
                                 children=[] if folder else (), member=path)
            parent.children.append(found)
            entries[path] = found
        parent = found
    return True


def _rollup(root: VirtualEntry, cancel: threading.Event | None) -> None:
    folders, stack = [], [root]
    while stack:
        _check_cancel(cancel)
        node = stack.pop()
        if node.is_dir:
            folders.append(node)
            stack.extend(node.children)
    for node in reversed(folders):
        give_way()
        node.size = sum(child.size for child in node.children)
        node.file_count = sum(child.file_count if child.is_dir else 1 for child in node.children)
        node.dir_count = sum(child.dir_count + 1 for child in node.children if child.is_dir)
        node.children.sort(key=lambda child: child.size, reverse=True)
