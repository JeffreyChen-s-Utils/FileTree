"""Native Darwin INODE64 mount metadata; no shell, Qt, payload read or filesystem mutation."""

from __future__ import annotations

import ctypes
import functools
import os
import platform
import posixpath
import sys
from typing import Any

_NOWAIT = 2
_MAX_MOUNTS = 4096
_STRUCT_BYTES = 2168
_PATH_BYTES = 1024


class _StatFS(ctypes.Structure):
    """Darwin 64-bit-inode statfs ABI from Apple's XNU bsd/sys/mount.h; names are 1024 bytes."""

    _fields_ = [("block_size", ctypes.c_uint32), ("io_size", ctypes.c_int32),
                ("counts", ctypes.c_uint64 * 5), ("fsid", ctypes.c_int32 * 2),
                ("kinds", ctypes.c_uint32 * 4), ("fs_type", ctypes.c_char * 16),
                ("mounted_on", ctypes.c_char * _PATH_BYTES), ("mounted_from", ctypes.c_char * _PATH_BYTES),
                ("reserved", ctypes.c_uint32 * 8)]


@functools.cache
def _function(name: str) -> Any:
    if sys.platform != "darwin" or ctypes.sizeof(_StatFS) != _STRUCT_BYTES:
        raise OSError("Native Darwin mount ABI unavailable")
    library = ctypes.CDLL(None, use_errno=True)
    candidates = (name + "$INODE64", name + "64")
    if platform.machine().casefold() == "arm64":
        candidates += (name,)  # arm64 exports only the modern inode ABI, with the unsuffixed name.
    for candidate in candidates:
        try:
            function = getattr(library, candidate)
        except AttributeError:
            continue  # Never use the legacy x86 statfs layout as a fallback.
        function.argtypes = ([ctypes.POINTER(_StatFS), ctypes.c_int, ctypes.c_int] if name == "getfsstat" else
                            [ctypes.c_int, ctypes.POINTER(_StatFS)])
        function.restype = ctypes.c_int
        return function
    raise OSError("Native Darwin mount function unavailable")


def _points(table: Any, count: int) -> frozenset[str]:
    points = set()
    for entry in table[:count]:
        raw = entry.mounted_on
        if not raw.startswith(b"/") or len(raw) >= _PATH_BYTES:
            raise OSError("Invalid native Darwin mount path")
        points.add(posixpath.normpath("/" + os.fsdecode(raw).lstrip("/")))
    return frozenset(points)


def mount_points() -> frozenset[str]:
    """Read a bounded complete private buffer and refuse truncation/changing native mount counts."""
    function = _function("getfsstat")
    for _attempt in range(3):
        count = function(None, 0, _NOWAIT)
        if not 0 < count < _MAX_MOUNTS:
            raise OSError("Darwin mount table unavailable or exceeds the scan limit")
        capacity = count + 1
        table = (_StatFS * capacity)()
        copied = function(table, ctypes.sizeof(table), _NOWAIT)
        current = function(None, 0, _NOWAIT)
        if 0 < copied < capacity and current == copied:
            return _points(table, copied)
    raise OSError("Darwin mount table changed during its query; scan again")


def descriptor_mount(fd: int) -> tuple[int, int]:
    """Return the actual pinned directory filesystem ID; unknown metadata never permits traversal."""
    info = _StatFS()
    if _function("fstatfs")(fd, ctypes.byref(info)) != 0:
        raise OSError(ctypes.get_errno(), "Native Darwin directory mount ID unavailable")
    identity = tuple(info.fsid)
    if identity == (0, 0):
        raise OSError("Native Darwin directory mount ID is unknown")
    return identity
