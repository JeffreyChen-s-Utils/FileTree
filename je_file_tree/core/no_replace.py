"""Anchored directory identities and native same-volume rename that never overwrites a destination."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
import ctypes
from dataclasses import dataclass
import errno
import os
from pathlib import Path
import stat
import sys

from je_file_tree.core.compression_ops import _kernel, _pin
from je_file_tree.core.snapshot import pack_snapshot, unpack_snapshot

_UNAVAILABLE = 0x400 | 0x1000 | 0x40000 | 0x400000
_RENAME_NOREPLACE = 1
_RENAME_EXCL = 4


@dataclass(frozen=True, slots=True)
class DirectoryStamp:
    """Captured component path and directory identity, never a followed link/cloud ancestor."""

    path: str
    snapshot: bytes


def directory_stamps(path: str) -> tuple[DirectoryStamp, ...]:
    """Capture a rooted existing directory and every ancestor without following their links."""
    directory = Path(os.path.abspath(path))
    entries = []
    for parent in (*reversed(directory.parents), directory):
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & _UNAVAILABLE or not info.st_dev or not info.st_ino):
            raise ValueError("Unidentified, linked or unavailable directory ancestor")
        entries.append(DirectoryStamp(str(parent), pack_snapshot(info)))
    return tuple(entries)


def _identity(stamp: DirectoryStamp, info: os.stat_result) -> None:
    expected = unpack_snapshot(stamp.snapshot)
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _UNAVAILABLE
            or expected.identity != (info.st_dev, info.st_ino)):
        raise ValueError("Approved directory identity changed")


@contextmanager
def anchored_directory(stamps: Sequence[DirectoryStamp]) -> Iterator[int | None]:
    """Pin Windows ancestors against rename/delete, or open POSIX components without following links."""
    if not stamps:
        raise ValueError("A captured directory chain is required")
    if os.name == "nt":
        with ExitStack() as stack:
            kernel = _kernel()
            for stamp in stamps:
                stack.enter_context(_pin(kernel, stamp.path))
                _identity(stamp, os.lstat(stamp.path))
            yield None
    else:
        descriptor = os.open(stamps[0].path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            _identity(stamps[0], os.fstat(descriptor))
            for stamp in stamps[1:]:
                child = os.open(Path(stamp.path).name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
                _identity(stamp, os.fstat(descriptor))
            yield descriptor
        finally:
            os.close(descriptor)


def _native(old_fd: int, old_name: str, new_fd: int, new_name: str) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    symbol, flags = (("renameat2", _RENAME_NOREPLACE) if sys.platform.startswith("linux") else
                     ("renameatx_np", _RENAME_EXCL) if sys.platform == "darwin" else ("", 0))
    function = getattr(library, symbol, None)
    if function is None:
        raise OSError(errno.ENOSYS, "Native exclusive rename is unavailable; source preserved")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(old_fd, os.fsencode(old_name), new_fd, os.fsencode(new_name), flags):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), new_name)


def rename_no_replace(source: str, destination: str, old_fd: int | None, new_fd: int | None) -> None:
    """Atomically rename on one volume using OS exclusive semantics; never copy or overwrite as fallback.

    Windows os.rename raises if a destination exists. POSIX uses anchored descriptor-relative
    Linux RENAME_NOREPLACE or macOS RENAME_EXCL; unsupported filesystem/kernel errors preserve source.
    Caller must hold captured parent anchors and validate source/scope immediately before invoking.
    """
    if os.name == "nt":
        os.rename(source, destination)
    elif old_fd is not None and new_fd is not None:
        _native(old_fd, os.path.basename(source), new_fd, os.path.basename(destination))
    else:
        raise ValueError("POSIX rename requires captured parent descriptors")
