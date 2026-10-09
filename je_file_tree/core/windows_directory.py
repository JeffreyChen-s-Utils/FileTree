"""Permission-checked no-follow directory metadata; no raw-volume access or privilege changes."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import functools
import os
import stat
import struct
import sys
from typing import Any

from je_file_tree.core.snapshot import Snapshot

_HEADER = struct.Struct("<II6qIIII16s")
_BUFFER = 65536
_NAME_BYTES = 510
_DIRECTORY = 0x10
_REPARSE = 0x400
_ELSEWHERE = 0x1000 | 0x40000 | 0x400000
_NO_MORE_FILES = 18
_EPOCH = 116444736000000000
_DIRECTORY_INFO = 19
_RESTART_INFO = 20
_FILE_ID_INFO = 18
_TAG_INFO = 9
_ALIGN = 8


@dataclass(frozen=True, slots=True)
class WindowsEntry:
    """One native visible name and 128-bit identity, sizes, attributes/tag and four NTFS dates.

    Dates are creation, access, modification and metadata change in Unix nanoseconds.
    Allocation is an OS observation, not a claim of independently recoverable space.
    Only reparse-marked entries have a meaningful tag; names never contain path separators.
    """

    name: str
    file_id: int
    size: int
    allocated: int
    attributes: int
    reparse_tag: int
    times: tuple[int, int, int, int]


def _decode(data: bytes, offset: int, end: int) -> WindowsEntry | None:
    if end - offset < _HEADER.size:
        raise ValueError("Truncated native directory header")
    _next, _index, created, accessed, modified, changed, size, allocated, attributes, length, _ea, tag, identifier = (
        _HEADER.unpack_from(data, offset))
    if not 0 < length <= _NAME_BYTES or length % 2 or _HEADER.size + length > end - offset:
        raise ValueError("Invalid native directory name bounds")
    name = data[offset + _HEADER.size:offset + _HEADER.size + length].decode("utf-16-le", errors="surrogatepass")
    if name in (".", ".."):
        return None
    if any(character in name for character in "\0/\\:"):
        raise ValueError("Unsafe native directory name")
    file_id = int.from_bytes(identifier, "little")
    if not file_id or size < 0 or allocated < 0 or min(created, accessed, modified, changed) < 0:
        raise ValueError("Invalid native directory identity/metadata")
    dates = tuple((ticks - _EPOCH) * 100 for ticks in (created, accessed, modified, changed))
    return WindowsEntry(name, file_id, size, allocated, attributes, tag if attributes & _REPARSE else 0, dates)


def _entries(data: bytes) -> Iterator[WindowsEntry]:
    if not _HEADER.size <= len(data) <= _BUFFER:
        raise ValueError("Invalid native directory reply size")
    offset = 0
    while offset < len(data):
        if len(data) - offset < _HEADER.size:
            raise ValueError("Truncated native directory chain")
        following, = struct.unpack_from("<I", data, offset)
        if following and (following % _ALIGN or following < _HEADER.size or following > len(data) - offset):
            raise ValueError("Invalid native directory chain offset")
        entry = _decode(data, offset, offset + following if following else len(data))
        if entry is not None:
            yield entry
        if not following:
            return
        offset += following
    raise ValueError("Unterminated native directory chain")


@functools.cache
def _kernel() -> Any:
    if sys.platform != "win32":
        raise OSError("Native directory identities are Windows-only")
    kernel = ctypes.WinDLL("kernel32.dll", winmode=0x800, use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                  ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    kernel.GetFileInformationByHandleEx.restype = ctypes.c_int
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [ctypes.c_void_p], ctypes.c_int
    return kernel


def _identity(path: str, expected: Snapshot) -> None:
    current = os.lstat(path)
    attributes = getattr(current, "st_file_attributes", 0)
    if (not expected.is_dir or expected.is_link or not expected.inode
            or expected.attributes & (_REPARSE | _ELSEWHERE)
            or not stat.S_ISDIR(current.st_mode) or attributes & (_REPARSE | _ELSEWHERE)
            or (current.st_dev, current.st_ino) != expected.identity):
        raise ValueError("Native directory identity/boundary changed or unsupported")


def _handle_identity(kernel: Any, handle: int, expected: Snapshot) -> None:
    identifier = ctypes.create_string_buffer(24)
    tag = ctypes.create_string_buffer(8)
    if (not kernel.GetFileInformationByHandleEx(handle, _FILE_ID_INFO, identifier, len(identifier))
            or not kernel.GetFileInformationByHandleEx(handle, _TAG_INFO, tag, len(tag))):
        raise ctypes.WinError(ctypes.get_last_error())
    serial, inode = struct.unpack("<Q16s", identifier.raw)
    attributes, _tag = struct.unpack("<II", tag.raw)
    if (expected.device not in (serial, serial & 0xFFFFFFFF) or int.from_bytes(inode, "little") != expected.inode
            or not attributes & _DIRECTORY or attributes & (_REPARSE | _ELSEWHERE)):
        raise ValueError("Native directory handle differs from captured scope")


@contextmanager
def _directory(path: str, expected: Snapshot) -> Iterator[tuple[Any, int]]:
    _identity(path, expected)
    kernel, handle = None, None
    try:
        # FindFirstFile enforces ordinary listing permission before a backup-semantics handle.
        with os.scandir(path) as permission:
            next(permission, None)
            _identity(path, expected)
            kernel = _kernel()
            handle = kernel.CreateFileW(path, 0x81, 3, None, 3, 0x02200000, None)
            if handle == ctypes.c_void_p(-1).value:
                handle = None
                raise ctypes.WinError(ctypes.get_last_error())
        _handle_identity(kernel, handle, expected)
        _identity(path, expected)
        yield kernel, handle
        _identity(path, expected)
    finally:
        if handle is not None and not kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())


def directory_entries(path: str, expected: Snapshot, *,
                      check: Callable[[], None] | None = None) -> Iterator[WindowsEntry]:
    """Stream metadata under ordinary directory permission and a checked no-follow owned handle.

    The caller must anchor parent directories and consume/close the iterator on its owning worker.
    Each batch/entry propagates check exceptions; every exit closes this function's own handle.
    Unsupported replies, identity/reparse changes and native failures remain visible. The directory
    is pinned against rename/delete during iteration; observations are not transactional.
    No user file contents, raw-volume access, elevation or privilege changes are involved.
    """
    if check is not None:
        check()
    with _directory(path, expected) as (kernel, handle):
        information_class = _RESTART_INFO
        while True:
            if check is not None:
                check()
            _identity(path, expected)
            buffer = ctypes.create_string_buffer(_BUFFER)
            if not kernel.GetFileInformationByHandleEx(handle, information_class, buffer, len(buffer)):
                error = ctypes.get_last_error()
                if error == _NO_MORE_FILES:
                    return
                raise ctypes.WinError(error)
            information_class = _DIRECTORY_INFO
            for entry in _entries(buffer.raw):
                if check is not None:
                    check()
                yield entry
