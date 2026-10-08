"""Native FreeBSD 12+ statfs mount boundaries and pinned filesystem identities."""

from __future__ import annotations

import ctypes
import functools
import os
import posixpath
import sys
from typing import Any

_VERSION = 0x20140518
_PATH_BYTES = 1024
_MAX_MOUNTS = 4096
_STRUCT_BYTES = 2344
_LONG_BYTES = 8


class _StatFS(ctypes.Structure):
    """FreeBSD sys/sys/mount.h statfs ABI; obsolete FreeBSD11 layouts are never accepted."""

    _fields_ = [("version", ctypes.c_uint32), ("type", ctypes.c_uint32),
                ("flags", ctypes.c_uint64), ("block_size", ctypes.c_uint64), ("io_size", ctypes.c_uint64),
                ("blocks", ctypes.c_uint64), ("free", ctypes.c_uint64), ("available", ctypes.c_int64),
                ("files", ctypes.c_uint64), ("free_files", ctypes.c_int64),
                ("statistics", ctypes.c_uint64 * 4), ("vnode_count", ctypes.c_uint32),
                ("spare0", ctypes.c_uint32), ("spare", ctypes.c_uint64 * 9),
                ("name_max", ctypes.c_uint32), ("owner", ctypes.c_uint32), ("fsid", ctypes.c_int32 * 2),
                ("char_spare", ctypes.c_char * 80), ("fs_type", ctypes.c_char * 16),
                ("mounted_from", ctypes.c_char * _PATH_BYTES), ("mounted_on", ctypes.c_char * _PATH_BYTES)]


@functools.cache
def _function(name: str) -> Any:
    if (not sys.platform.startswith("freebsd") or ctypes.sizeof(_StatFS) != _STRUCT_BYTES
            or ctypes.sizeof(ctypes.c_long) != _LONG_BYTES):
        raise OSError("Native FreeBSD mount ABI unavailable")
    library = ctypes.CDLL(None, use_errno=True)
    try:
        function = getattr(library, name)
    except AttributeError as error:
        raise OSError("Native FreeBSD mount function unavailable") from error
    function.argtypes = ([ctypes.POINTER(_StatFS), ctypes.c_long, ctypes.c_int] if name == "getfsstat" else
                        [ctypes.c_int, ctypes.POINTER(_StatFS)])
    function.restype = ctypes.c_int
    return function


def _check(info: _StatFS) -> None:
    if info.version != _VERSION:
        raise OSError("Unknown FreeBSD statfs version")


def _points(table: Any, count: int) -> frozenset[str]:
    points = set()
    for entry in table[:count]:
        _check(entry)
        raw = entry.mounted_on
        if not raw.startswith(b"/") or len(raw) >= _PATH_BYTES:
            raise OSError("Invalid native FreeBSD mount path")
        points.add(posixpath.normpath("/" + os.fsdecode(raw).lstrip("/")))
    return frozenset(points)


def mount_points() -> frozenset[str]:
    """Read a bounded private native table; unknown or changing metadata refuses the scan."""
    function = _function("getfsstat")
    for _attempt in range(3):
        count = function(None, 0, 2)
        if not 0 < count < _MAX_MOUNTS:
            raise OSError("FreeBSD mount table unavailable or exceeds the scan limit")
        capacity = count + 1
        table = (_StatFS * capacity)()
        copied = function(table, ctypes.sizeof(table), 2)
        current = function(None, 0, 2)
        if 0 < copied < capacity and current == copied:
            return _points(table, copied)
    raise OSError("FreeBSD mount table changed during its query; scan again")


def descriptor_mount(fd: int) -> tuple[int, int]:
    """Return the pinned directory's actual filesystem ID; unknown identities never permit traversal."""
    info = _StatFS()
    if _function("fstatfs")(fd, ctypes.byref(info)) != 0:
        raise OSError(ctypes.get_errno(), "Native FreeBSD directory mount ID unavailable")
    _check(info)
    identity = tuple(info.fsid)
    if identity == (0, 0):
        raise OSError("Native FreeBSD directory mount ID is unknown")
    return identity
