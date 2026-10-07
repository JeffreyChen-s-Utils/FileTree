"""Read-only NTFS compression candidates from recorded file types, with explicit allocation limits."""

from __future__ import annotations

import ctypes
import heapq
import os
import stat
import sys
import threading
from dataclasses import dataclass

from je_file_tree.core.allocation import allocation_unit
from je_file_tree.core.analysis import CATEGORY_EXTENSIONS, extension_of
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import unpack_snapshot

_LIMIT = 1000
_TYPES = (CATEGORY_EXTENSIONS["code"] - {".pyc"}) | {
    ".log", ".txt", ".md", ".csv", ".rtf", ".bmp", ".tif", ".tiff", ".raw", ".psd", ".exe", ".dll",
}
_UNSUITABLE = 0x2 | 0x4 | 0x200 | 0x400 | 0x800 | 0x1000 | 0x40000 | 0x400000
_BUFFER = 1024


@dataclass(frozen=True, slots=True)
class CompressionPlan:
    """Largest candidates/full counts; potential saving is only 0..recorded candidate allocation."""

    root: Node
    rows: list[Node]
    count: int
    logical: int
    allocated: int
    total_files: int
    unknown_files: int
    incomplete: bool
    filesystem: str | None
    unit: int | None

    @property
    def ntfs(self) -> bool:
        """A positively identified NTFS scope; unknown filesystems never qualify."""
        return self.filesystem is not None and self.filesystem.casefold() == "ntfs"


def compression_plan(root: Node, *, cancel: threading.Event | None = None,
                     include_compressed: bool = False) -> CompressionPlan | None:
    """Survey recorded text/code/uncompressed-image types without reading file contents.

    Extension-based candidates are not proof of compressibility. Unknown snapshots and hidden,
    system, sparse, compressed, reparse/cloud/offline entries are omitted; hard-linked names may
    overcount allocation. include_compressed lists all safe regular types for restoration, since WOF
    files may lack compression flags. Directory metadata/shared extents remain unknown. Cancel drops results.
    """
    count = logical = allocated = total = unknown = 0
    incomplete = False
    heap: list[tuple[int, int, Node]] = []
    for node in root.iter_nodes():
        if cancel is not None and cancel.is_set():
            return None
        incomplete |= bool(node.error)
        if node.is_dir:
            give_way()
        if node.is_dir or node.is_link:
            continue
        total += 1
        if node.snapshot is None or node.error:
            unknown += 1
            continue
        info = unpack_snapshot(node.snapshot)
        unsuitable = _UNSUITABLE & ~0x800 if include_compressed else _UNSUITABLE
        if (info.is_link or not stat.S_ISREG(info.mode) or info.attributes & unsuitable
                or (not include_compressed and extension_of(node.name) not in _TYPES)):
            continue
        count += 1
        logical += node.size
        allocated += node.allocated
        entry = (node.size, count, node)
        if len(heap) < _LIMIT:
            heapq.heappush(heap, entry)
        elif entry[:2] > heap[0][:2]:
            heapq.heapreplace(heap, entry)
    if cancel is not None and cancel.is_set():
        return None
    filesystem = file_system(root.path)
    unit = allocation_unit(root.path) if sys.platform == "win32" else None
    if cancel is not None and cancel.is_set():
        return None
    return CompressionPlan(root, [node for _size, _order, node in sorted(heap, reverse=True)], count,
                           logical, allocated, total, unknown, incomplete, filesystem, unit)


def file_system(path: str) -> str | None:
    """Query the Windows filesystem name read-only; unavailable/non-Windows scopes remain unknown."""
    if sys.platform != "win32":
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetVolumePathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
    kernel.GetVolumePathNameW.restype = ctypes.c_int
    kernel.GetVolumeInformationW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong] + [
        ctypes.POINTER(ctypes.c_ulong)] * 3 + [ctypes.c_wchar_p, ctypes.c_ulong]
    kernel.GetVolumeInformationW.restype = ctypes.c_int
    volume, name = ctypes.create_unicode_buffer(_BUFFER), ctypes.create_unicode_buffer(_BUFFER)
    if not kernel.GetVolumePathNameW(os.path.abspath(path), volume, _BUFFER):
        return None
    if not kernel.GetVolumeInformationW(volume, None, 0, None, None, None, name, _BUFFER):
        return None
    return name.value or None
