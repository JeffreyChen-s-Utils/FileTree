"""Optional per-file Windows allocation from a no-follow metadata handle, including WOF/XPRESS files."""

from __future__ import annotations

import ctypes
import functools
import os
import sys
from typing import Any

_DIRECTORY = 0x10
_UNAVAILABLE = 0x400 | 0x1000 | 0x40000 | 0x400000
_UNIX_EPOCH = 116444736000000000
_NS_PER_TICK = 100
_EXTENDED_STAT = (3, 12)


class _Standard(ctypes.Structure):
    _fields_ = [("allocation", ctypes.c_int64), ("eof", ctypes.c_int64), ("links", ctypes.c_uint32),
                ("pending", ctypes.c_ubyte), ("directory", ctypes.c_ubyte)]


class _Identity(ctypes.Structure):
    _fields_ = [("attributes", ctypes.c_uint32), ("created", ctypes.c_uint32 * 2),
                ("accessed", ctypes.c_uint32 * 2), ("modified", ctypes.c_uint32 * 2),
                ("device", ctypes.c_uint32), ("size_high", ctypes.c_uint32), ("size_low", ctypes.c_uint32),
                ("links", ctypes.c_uint32), ("inode_high", ctypes.c_uint32), ("inode_low", ctypes.c_uint32)]


class _FileID(ctypes.Structure):
    _fields_ = [("device", ctypes.c_uint64), ("inode", ctypes.c_ubyte * 16)]


def file_allocation(path: str, expected: os.stat_result) -> int | None:
    """Read FILE_STANDARD_INFO allocation through a no-follow FILE_READ_ATTRIBUTES handle.

    Verify recorded identity/size/mtime and reject links, cloud/offline data, directories and delete
    pending entries. No payload read or privilege change occurs. Unsupported/denied/changed metadata
    returns None, so the caller retains an explicitly documented size estimate. Shared extents and
    directory metadata are not measured; this is not a transactional filesystem snapshot.
    """
    kernel = _kernel()
    handle = kernel.CreateFileW(path, 0x80, 7, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        return None
    try:
        identity, standard, file_id = _Identity(), _Standard(), _FileID()
        if not kernel.GetFileInformationByHandle(handle, ctypes.byref(identity)):
            return None
        if (not kernel.GetFileInformationByHandleEx(handle, 18, ctypes.byref(file_id), ctypes.sizeof(file_id))
                or not _matches(identity, file_id, expected)):
            return None
        if not kernel.GetFileInformationByHandleEx(handle, 1, ctypes.byref(standard), ctypes.sizeof(standard)):
            return None
        if standard.directory or standard.pending or standard.allocation < 0 or standard.eof != expected.st_size:
            return None
        return standard.allocation
    finally:
        kernel.CloseHandle(handle)


def _matches(info: _Identity, file_id: _FileID, expected: os.stat_result) -> bool:
    inode = int.from_bytes(file_id.inode, "little")
    size = (info.size_high << 32) | info.size_low
    modified = ((info.modified[1] << 32) | info.modified[0]) - _UNIX_EPOCH
    same_identity = inode == expected.st_ino and file_id.device == expected.st_dev
    if sys.version_info[:2] < _EXTENDED_STAT:
        legacy_inode = (info.inode_high << 32) | info.inode_low
        same_identity |= legacy_inode == expected.st_ino and info.device == expected.st_dev
    return (not info.attributes & (_DIRECTORY | _UNAVAILABLE) and same_identity and size == expected.st_size
            and modified * _NS_PER_TICK == expected.st_mtime_ns)


@functools.cache
def _kernel() -> Any:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                  ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.GetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Identity)]
    kernel.GetFileInformationByHandle.restype = ctypes.c_int
    kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    kernel.GetFileInformationByHandleEx.restype = ctypes.c_int
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [ctypes.c_void_p], ctypes.c_int
    return kernel
