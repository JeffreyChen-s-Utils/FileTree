"""Linux mount-table boundaries, including same-device bind mounts that stat/ismount cannot identify."""

from __future__ import annotations

import os
import errno
import posixpath
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from je_file_tree.core.snapshot import unpack_snapshot

MOUNT_BOUNDARY = "mount boundary: not traversed"
_MOUNTINFO = Path("/proc/self/mountinfo")
_MAX_TABLE = 8 * 1024 * 1024
_ESCAPES = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}
_ESCAPE_PATTERN = re.compile(r"\\(040|011|012|134)")
_MIN_PREFIX = 6
_SUFFIX_FIELDS = 4
_FDINFO_LIMIT = 4096


class MountChangedError(OSError):
    """A scan cannot publish a result from changing or unknown mount boundaries."""

    def __init__(self) -> None:
        super().__init__("mount boundaries changed or could not be verified; scan again")


def descriptor_mount(fd: int) -> int:
    """Read Linux's mount ID for an already opened directory; missing IDs are unsafe."""
    with open(f"/proc/self/fdinfo/{fd}", encoding="utf-8") as stream:
        contents = stream.read(_FDINFO_LIMIT + 1)
    matches = re.findall(r"^mnt_id:\s*([0-9]+)$", contents, re.MULTILINE)
    if len(contents) > _FDINFO_LIMIT or len(matches) != 1:
        raise MountChangedError
    return int(matches[0])


class _AnchoredEntry:
    """Keep display/exclusion paths while stat calls use the live scandir directory descriptor."""

    def __init__(self, parent: str, entry: os.DirEntry[str]) -> None:
        self.name = entry.name
        self.path = os.path.join(parent, entry.name)
        self._entry = entry

    def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
        return self._entry.stat(follow_symlinks=follow_symlinks)

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        return self._entry.is_dir(follow_symlinks=follow_symlinks)


class MountSurvey:
    """Pin each Linux folder read and reject relevant namespace changes before publication.

    Directory descriptors stay open through all entry metadata reads. Mount IDs distinguish
    same-device bind mounts; device/inode checks reject replaced queued directories.
    This does not turn a mutable filesystem into a transactional snapshot.
    """

    def __init__(self, root: str, snapshot: bytes, points: frozenset[str]) -> None:
        self.root = root
        self._snapshot = snapshot
        self.actual = os.path.realpath(root)
        self.points = rebase_mount_points(root, points)
        self._relevant = self._scope(self.points)
        self._mount: int | None = None
        self._root_error: PermissionError | None = None
        if sys.platform.startswith("linux"):
            try:
                fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            except PermissionError as error:
                self._root_error = error
                return  # Unreadable roots produce incomplete coverage, without traversing anything.
            try:
                self._identity(fd, snapshot)
                self._mount = descriptor_mount(fd)
            finally:
                os.close(fd)

    def __contains__(self, path: str) -> bool:
        return path in self.points

    def _scope(self, points: frozenset[str]) -> frozenset[str]:
        root = boundary_path(self.root)
        prefix = root.rstrip(os.sep) + os.sep
        return frozenset(point for point in points if point == root or point.startswith(prefix)
                         or root.startswith(point.rstrip(os.sep) + os.sep))

    @staticmethod
    def _identity(fd: int, snapshot: bytes | None) -> None:
        if snapshot is None:
            raise OSError(errno.ESTALE, "folder identity unavailable")
        expected, actual = unpack_snapshot(snapshot), os.fstat(fd)
        if (expected.device, expected.inode) != (actual.st_dev, actual.st_ino):
            raise OSError(errno.ESTALE, "folder replaced during scan")

    @contextmanager
    def listing(self, path: str, snapshot: bytes | None) -> Iterator[Iterator[os.DirEntry[str]]]:
        """Read through a pinned Linux descriptor, without following a replacement folder link."""
        if self._root_error is not None:
            raise self._root_error
        if self._mount is None:
            with os.scandir(path) as entries:
                yield entries
            return
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            if descriptor_mount(fd) != self._mount:
                raise MountChangedError
            self._identity(fd, snapshot)
            with os.scandir(fd) as entries:
                yield (cast(os.DirEntry[str], _AnchoredEntry(path, entry)) for entry in entries)
        finally:
            os.close(fd)

    def verify(self, points: frozenset[str]) -> None:
        """Refuse a completed result if its root or relevant mount points changed."""
        if (os.path.realpath(self.root) != self.actual
                or self._scope(rebase_mount_points(self.root, points)) != self._relevant):
            raise MountChangedError
        if self._mount is not None:
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                self._identity(fd, self._snapshot)
                if descriptor_mount(fd) != self._mount:
                    raise MountChangedError
            finally:
                os.close(fd)


def parse_mountinfo(contents: str) -> frozenset[str]:
    """Decode mount points exactly once, preserving escaped whitespace/backslashes and Unicode."""
    points = set()
    for line in contents.splitlines():
        fields = line.split()
        try:
            separator = fields.index("-", _MIN_PREFIX)
        except ValueError as error:
            raise ValueError("Malformed Linux mount table") from error
        if len(fields) < separator + _SUFFIX_FIELDS or not fields[4].startswith("/"):
            raise ValueError("Malformed Linux mount table")
        if re.search(r"\\(?!040|011|012|134)", fields[4]):
            raise ValueError("Invalid Linux mount path escape")
        point = _ESCAPE_PATTERN.sub(lambda match: _ESCAPES[match[1]], fields[4])
        if "\0" in point:
            raise ValueError("Invalid Linux mount path")
        points.add(posixpath.normpath("/" + point.lstrip("/")))
    if not points:
        raise ValueError("Empty Linux mount table")
    return frozenset(points)


def mount_points() -> frozenset[str]:
    """Read the current Linux mount namespace; refuse unknown tables instead of crossing blindly."""
    if not sys.platform.startswith("linux"):
        return frozenset()
    with _MOUNTINFO.open(encoding="utf-8", errors="surrogateescape") as stream:
        contents = stream.read(_MAX_TABLE + 1)
    if len(contents) > _MAX_TABLE:
        raise OSError("Linux mount table exceeds the scan limit")
    try:
        return frozenset(os.path.normpath(path) for path in parse_mountinfo(contents))
    except ValueError as error:
        raise OSError("Linux mount boundaries could not be determined") from error


def boundary_path(path: str) -> str:
    """Normalize exact directory paths, including Linux's equivalent multiple leading slashes."""
    normalized = os.path.normpath(path)
    return "/" + normalized.lstrip("/") if normalized.startswith("/") else normalized


def rebase_mount_points(root: str, points: frozenset[str]) -> frozenset[str]:
    """Map namespace paths to an explicitly selected root reached through ancestor aliases."""
    if not points:
        return points
    selected, actual = boundary_path(root), boundary_path(os.path.realpath(root))
    if selected == actual:
        return points
    prefix = actual.rstrip(os.sep) + os.sep
    return frozenset(boundary_path(os.path.join(selected, os.path.relpath(point, actual)))
                     for point in points if point == actual or point.startswith(prefix))
