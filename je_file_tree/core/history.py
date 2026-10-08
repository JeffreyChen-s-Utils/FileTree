"""Bounded local scan history using compatible saved-scan JSON and owned metadata retention."""

from __future__ import annotations

import hashlib
import ctypes
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TextIO

from je_file_tree.core.compare import SavedFolder, SavedScan, folder_key
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.export import JSON_FORMAT, _atomic_file, _folder_json
from je_file_tree.core.node import Node
from je_file_tree.core.operation_journal import _lock
from je_file_tree.core.pacing import give_way

DEFAULT_LIMIT = 1024 * 1024 * 1024
_HEADER_LIMIT = 65536
_ENTRY_LIMIT = 100000
_KEY = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"scan-[0-9]{20}-[0-9a-f]{32}\.json\Z")
_SUFFIX = ', "root":\n'
_CHILDREN = ', "children": ['


class HistoryCancelledError(Exception):
    """The caller stopped a history operation; no partial saved tree is published."""


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """A bounded header read, with logical/allocation totals and incomplete coverage visibility."""

    path: Path
    root: str
    saved: str
    size: int
    allocated: int
    incomplete: bool
    disk_bytes: int


@dataclass(frozen=True, slots=True)
class HistoryRead:
    """Latest entries in chronological order, complete count and rejected metadata count."""

    entries: list[HistoryEntry]
    count: int
    invalid: int


def root_key(path: str) -> str:
    """Hash the normalized absolute selected path; Windows casing aliases share one bucket."""
    normalized = os.path.normcase(os.path.abspath(path))
    return hashlib.sha256(normalized.encode("utf-8", errors="surrogatepass")).hexdigest()


def _check(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise HistoryCancelledError


def _directory(path: Path, *, create: bool = False) -> bool:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise OSError("History directory is a link or is not a directory")
    return True


def _header(stream: TextIO, path: Path, info: os.stat_result) -> HistoryEntry:
    line = stream.readline(_HEADER_LIMIT + 1)
    if len(line) > _HEADER_LIMIT or not line.endswith(_SUFFIX):
        raise ValueError("Invalid history header")
    data = json.loads(line[:-len(_SUFFIX)] + "}")
    history = data.get("history")
    if not isinstance(history, dict) or data.get("format") != JSON_FORMAT:
        raise ValueError("Not a compatible scan history")
    if history.get("format") != "file-tree-history/1" or history.get("id") != path.name:
        raise ValueError("Not owned scan-history metadata")
    root, saved = history.get("root"), data.get("saved")
    if not isinstance(root, str) or not os.path.isabs(root) or root_key(root) != path.parent.name:
        raise ValueError("History root does not match its bucket")
    if not isinstance(saved, str) or datetime.fromisoformat(saved).tzinfo is None:
        raise ValueError("Invalid history date")
    for key in ("size", "allocated"):
        if type(history.get(key)) is not int or history[key] < 0:
            raise ValueError("Invalid history total")
    if type(history.get("incomplete")) is not bool:
        raise ValueError("Invalid history coverage")
    return HistoryEntry(path, root, saved, history["size"], history["allocated"], history["incomplete"], info.st_size)


def _read_entry(path: Path, directory_fd: int | None = None) -> HistoryEntry:
    info = path.lstat() if directory_fd is None else os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
    if (not _NAME.fullmatch(path.name) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise ValueError("Not a private regular history file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path if directory_fd is None else path.name, flags, dir_fd=directory_fd)
    with os.fdopen(descriptor, encoding="utf-8") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("History file changed while opening")
        return _header(stream, path, opened)


@contextmanager
def _pinned_directory(path: Path, parent_fd: int | None = None) -> Iterator[int | None]:
    """Anchor POSIX retention to directory descriptors; prevent Windows directory rename/delete."""
    if os.name == "nt":
        with _windows_directory(path):
            yield None
        return
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path if parent_fd is None else path.name, flags, dir_fd=parent_fd)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def _windows_directory(path: Path) -> Iterator[None]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                  ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    kernel.GetFileInformationByHandleEx.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    # GENERIC_READ, READ|WRITE sharing (no DELETE), OPEN_EXISTING, BACKUP_SEMANTICS|OPEN_REPARSE_POINT.
    handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = (ctypes.c_uint32 * 2)()
        if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not attributes[0] & 0x10 or attributes[0] & 0x400:
            raise OSError("History directory handle is a reparse point or not a directory")
        yield
    finally:
        kernel.CloseHandle(handle)


class ScanHistory:
    """Atomically store folder metadata; enforce a global byte cap only on recognized owned entries."""

    def __init__(self, directory: str | os.PathLike[str], *, max_bytes: int = DEFAULT_LIMIT) -> None:
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("History byte limit must be positive")
        self.directory, self.max_bytes = Path(directory), max_bytes

    def save(self, root: Node, *, cancel: threading.Event | None = None) -> HistoryEntry:
        """Save a stable completed tree on its scan worker; retain globally across root buckets.

        A scan exceeding the cap is refused before publication. Cancellation preserves prior entries.
        Coverage errors are recorded; partial scans must be rejected by the caller before invoking this.
        """
        _check(cancel)
        if root.path is None:
            raise ValueError("Save individual source roots for history; the virtual root has no path")
        _directory(self.directory, create=True)
        lock = self.directory / ".history-lock"
        try:
            lock_info = lock.lstat()
        except FileNotFoundError:
            lock_info = None
        if lock_info is not None and (not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink != 1
                                      or getattr(lock_info, "st_file_attributes", 0) & 0x400):
            raise OSError("History lock is linked or not a regular file")
        with _lock(lock):
            bucket = self.directory / root_key(root.path)
            _directory(bucket, create=True)
            name = f"scan-{time.time_ns():020d}-{uuid.uuid4().hex}.json"
            target = bucket / name
            coverage = coverage_of(root, cancel=cancel)
            _check(cancel)
            header = {"format": JSON_FORMAT, "saved": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                      "history": {"format": "file-tree-history/1", "id": name, "root": root.path,
                                  "size": root.size, "allocated": root.allocated,
                                  "incomplete": not coverage.complete}}
            encoded = json.dumps(header, ensure_ascii=False)[:-1] + _SUFFIX
            if len(encoded) > _HEADER_LIMIT:
                raise ValueError("History header exceeds the limit")
            with _atomic_file(target, encoding="utf-8") as stream:
                stream.write(encoded)
                size = len(encoded.encode("utf-8"))
                for chunk in _folder_json(root, None):
                    _check(cancel)
                    size += len(chunk.encode("utf-8")) + 1
                    if size + 2 > self.max_bytes:
                        raise ValueError("Scan metadata exceeds the configured history byte limit")
                    stream.write(chunk + "\n")
                _check(cancel)
                stream.write("}\n")
            self._retain(target, None)
            return _read_entry(target)

    def _entries(self, cancel: threading.Event | None) -> tuple[list[HistoryEntry], int]:
        entries, invalid, examined = [], 0, 0
        if not _directory(self.directory):
            return entries, invalid
        for bucket in self.directory.iterdir():
            _check(cancel)
            give_way()
            if not _KEY.fullmatch(bucket.name):
                continue
            if not _directory(bucket):
                continue
            for path in bucket.iterdir():
                _check(cancel)
                examined += 1
                if examined > _ENTRY_LIMIT:
                    raise OSError("History inventory exceeds the entry limit")
                if not _NAME.fullmatch(path.name):
                    continue
                try:
                    entries.append(_read_entry(path))
                except (OSError, ValueError, UnicodeError, RecursionError):
                    invalid += 1
        return entries, invalid

    def read(self, root: str, *, limit: int = 1000, cancel: threading.Event | None = None) -> HistoryRead:
        """Read only small headers on a worker; chart/table rows are bounded, total counts are complete."""
        entries, invalid = self._entries(cancel)
        key = root_key(root)
        matching = sorted((entry for entry in entries if entry.path.parent.name == key),
                          key=lambda entry: (entry.saved, entry.path.name))
        return HistoryRead(matching[-max(1, limit):], len(matching), invalid)

    def _retain(self, latest: Path, cancel: threading.Event | None) -> None:
        entries, _invalid = self._entries(cancel)
        total = sum(entry.disk_bytes for entry in entries)
        for entry in sorted(entries, key=lambda entry: (entry.saved, entry.path.name)):
            _check(cancel)
            if total <= self.max_bytes:
                break
            if entry.path == latest:
                continue
            with (_pinned_directory(self.directory) as root_fd,
                  _pinned_directory(entry.path.parent, root_fd) as bucket_fd):
                if _read_entry(entry.path, bucket_fd) != entry:
                    raise OSError("History entry changed before retention")
                # Only recognized metadata in the anchored bucket, never its recorded source path.
                os.unlink(entry.path if bucket_fd is None else entry.path.name, dir_fd=bucket_fd)
            total -= entry.disk_bytes


def _folder_record(piece: str, entry: HistoryEntry, is_root: bool) -> tuple[dict, bool]:
    opened = piece.endswith(_CHILDREN)
    data = json.loads(piece[:-len(_CHILDREN)] + "}" if opened else piece)
    if not isinstance(data, dict) or not isinstance(data.get("name"), str) or type(data.get("size")) is not int:
        raise ValueError("Invalid history folder")
    if data["size"] < 0:
        raise ValueError("Invalid history folder size")
    if is_root and (data["name"] != entry.root or data["size"] != entry.size):
        raise ValueError("History root does not match its header")
    return data, opened


def load_history(entry: HistoryEntry, *, cancel: threading.Event | None = None) -> SavedScan:
    """Read the owned line-oriented saved JSON iteratively, including trees deeper than json.loads accepts."""
    if _read_entry(entry.path) != entry:
        raise ValueError("History changed; refresh the view")
    folders, stack, seen_root = {}, [], False
    with entry.path.open(encoding="utf-8") as stream:
        _header(stream, entry.path, os.fstat(stream.fileno()))
        for line in iter(lambda: stream.readline(_HEADER_LIMIT + 1), ""):
            _check(cancel)
            give_way()
            if len(line) > _HEADER_LIMIT:
                raise ValueError("History folder record exceeds the limit")
            piece = line.rstrip("\n")
            if piece == ", ":
                continue
            if piece == "]}":
                if not stack:
                    raise ValueError("Invalid history nesting")
                stack.pop()
                continue
            if piece == "}":
                if stack or not seen_root or stream.read(1):
                    raise ValueError("Incomplete history tree")
                return SavedScan(entry.root, entry.saved, folders)
            data, opened = _folder_record(piece, entry, not seen_root)
            if seen_root and not stack:
                raise ValueError("Invalid history root")
            path = (stack[-1] + "/" + data["name"]).lstrip("/") if seen_root else ""
            key = folder_key(path)
            if key in folders:
                raise ValueError("Ambiguous folder paths in history")
            folders[key] = SavedFolder(path, data["size"])
            seen_root = True
            if opened:
                stack.append(path)
    raise ValueError("Truncated history tree")
