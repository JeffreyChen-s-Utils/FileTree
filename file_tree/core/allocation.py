"""The space a file takes on disk ("size on disk"), which can differ from its size.

A file takes whole clusters, so it usually takes a little more than its size; a compressed or
sparse file can take much less, and a file whose data is elsewhere (offline, or a cloud file kept
online only, such as a OneDrive placeholder) takes none.

- POSIX: ``st_blocks`` (512-byte units) is exact and comes with the ``stat`` the scan makes anyway.
- Windows: a directory listing has no allocation, and asking for it file by file
  (``GetCompressedFileSizeW``) took 100-145 µs per file (measured 2026-09-26 on 60,000 files of D:\\Codes),
  several times what the whole scan spends on a file. So an ordinary file is rounded up to whole
  clusters, which came within 0.64 % of the exact total on 765,000 entries (tiny files stored inside
  the MFT take no cluster of their own); only compressed and sparse files are asked for, and a file
  whose data is elsewhere counts 0 without being opened, so nothing is downloaded.

Cost, measured 2026-09-26 on 766,000 entries of D:\\Codes (median of five scans each): the scan takes
about 3 % longer (6.93 s to 7.12 s) and each entry 17.5 bytes more. Small sizes are handed out from a
table (``_SHARED``) so files of the same few clusters share one int object; without it each entry grew
by 44 bytes and the scan by 5-9 %.
"""

from __future__ import annotations

import ctypes
import functools
import os
import sys
from collections.abc import Callable
from typing import Any

Allocation = Callable[["os.DirEntry[str]", os.stat_result], int]
"""Tells the space a file takes on disk from its directory entry and its ``stat`` result."""

DEFAULT_CLUSTER = 4096

_SPARSE = 0x200
_COMPRESSED = 0x800
_OFFLINE = 0x1000
_RECALL_ON_OPEN = 0x40000
_RECALL_ON_DATA_ACCESS = 0x400000
_PACKED = _SPARSE | _COMPRESSED
_ELSEWHERE = _OFFLINE | _RECALL_ON_OPEN | _RECALL_ON_DATA_ACCESS
_UNUSUAL = _PACKED | _ELSEWHERE
_INVALID_FILE_SIZE = 0xFFFFFFFF
_VOLUME_PATH_LENGTH = 1024
_SHARED = 1024  # sizes of up to this many units (clusters or blocks) share their int object


def allocation_for(root: str) -> Allocation:
    """How to tell the space taken on disk by the files beneath ``root`` (a folder on one volume)."""
    if sys.platform == "win32":
        return windows_allocation(cluster_size(root))
    if hasattr(os.stat_result, "st_blocks"):
        return blocks_allocation()
    return _plain_size


def blocks_allocation() -> Allocation:
    """The POSIX rule: ``st_blocks`` 512-byte units."""
    shared = _multiples(512)

    def allocated(_entry: os.DirEntry[str], info: os.stat_result) -> int:
        blocks = info.st_blocks
        return shared[blocks] if blocks < _SHARED else blocks * 512

    return allocated


def windows_allocation(cluster: int) -> Allocation:
    """The Windows rule (see the module docstring) for a volume with ``cluster``-byte clusters."""

    shared = _multiples(cluster)

    def rounded(size: int) -> int:
        clusters = -(-size // cluster)
        return shared[clusters] if clusters < _SHARED else clusters * cluster

    def allocated(entry: os.DirEntry[str], info: os.stat_result) -> int:
        attributes = info.st_file_attributes
        if not attributes & _UNUSUAL:  # nearly every file: no call to the system
            return rounded(info.st_size)
        if attributes & _ELSEWHERE:
            return 0
        exact = compressed_size(entry.path)
        return rounded(info.st_size) if exact is None else exact

    return allocated


def cluster_size(path: str) -> int:
    """Bytes per cluster of the volume holding ``path`` (Windows; ``DEFAULT_CLUSTER`` when it cannot be told)."""
    kernel32 = _kernel32()
    volume = ctypes.create_unicode_buffer(_VOLUME_PATH_LENGTH)
    if not kernel32.GetVolumePathNameW(os.path.abspath(path), volume, _VOLUME_PATH_LENGTH):
        return DEFAULT_CLUSTER
    sectors, sector_bytes, free, total = (ctypes.c_ulong() for _ in range(4))
    if not kernel32.GetDiskFreeSpaceW(volume.value, ctypes.byref(sectors), ctypes.byref(sector_bytes),
                                      ctypes.byref(free), ctypes.byref(total)):
        return DEFAULT_CLUSTER
    return sectors.value * sector_bytes.value or DEFAULT_CLUSTER


def compressed_size(path: str) -> int | None:
    """The bytes a compressed or sparse file really takes (Windows); None when the system cannot say."""
    high = ctypes.c_ulong()
    low = _kernel32().GetCompressedFileSizeW(path, ctypes.byref(high))
    if low == _INVALID_FILE_SIZE and ctypes.get_last_error():
        return None
    return (high.value << 32) | low


@functools.cache
def _kernel32() -> Any:
    """kernel32 with the signatures used here (its own instance, so other modules' settings never clash)."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32.GetVolumePathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
    kernel32.GetVolumePathNameW.restype = ctypes.c_int
    kernel32.GetDiskFreeSpaceW.argtypes = [ctypes.c_wchar_p] + [ctypes.POINTER(ctypes.c_ulong)] * 4
    kernel32.GetDiskFreeSpaceW.restype = ctypes.c_int
    kernel32.GetCompressedFileSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel32.GetCompressedFileSizeW.restype = ctypes.c_ulong
    return kernel32


def _multiples(unit: int) -> tuple[int, ...]:
    return tuple(range(0, _SHARED * unit, unit))


def _plain_size(_entry: os.DirEntry[str], info: os.stat_result) -> int:
    return info.st_size
