"""Explicit read-only native VHD/VHDX header information, without attachment or guest launches."""

from contextlib import contextmanager
from collections.abc import Iterator
import ctypes
from dataclasses import dataclass
import functools
import os
import threading
from typing import Any
import uuid

from je_file_tree.core.compression_ops import _kernel
from je_file_tree.core.copy_io import _pinned_file, check_cancel, check_file
from je_file_tree.core.no_replace import DirectoryStamp, anchored_directory, directory_stamps
from je_file_tree.core.virtual_disks import VirtualDisk

_DEVICES = {"vhd": 2, "vhdx": 3}
_MICROSOFT = uuid.UUID("ec984aec-a0f9-47e9-901f-71415a66345b").bytes_le
_ACCESS_NONE = 0
_NO_PARENTS = 1
_DYNAMIC = 3
_MINIMUMS = {1: 32, 2: 24, 6: 28, 7: 12, 13: 12}


class _Guid(ctypes.Structure):
    _fields_ = [("first", ctypes.c_uint32), ("second", ctypes.c_uint16), ("third", ctypes.c_uint16),
                ("tail", ctypes.c_ubyte * 8)]


class _Storage(ctypes.Structure):
    _fields_ = [("device", ctypes.c_uint32), ("vendor", _Guid)]


class _Open(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("get_info_only", ctypes.c_int32),
                ("read_only", ctypes.c_int32), ("resiliency", _Guid)]


class _Size(ctypes.Structure):
    _fields_ = [("virtual", ctypes.c_uint64), ("physical", ctypes.c_uint64),
                ("block", ctypes.c_uint32), ("sector", ctypes.c_uint32)]


class _Value(ctypes.Union):
    _fields_ = [("size", _Size), ("guid", _Guid), ("storage", _Storage),
                ("subtype", ctypes.c_uint32), ("loaded", ctypes.c_int32)]


class _Info(ctypes.Structure):
    _fields_ = [("version", ctypes.c_int32), ("value", _Value)]


@dataclass(frozen=True, slots=True)
class VirtualDiskInfo:
    """Captured native provider observations; physical bytes/capacity never mean guest-used bytes."""

    disk: VirtualDisk
    parents: tuple[DirectoryStamp, ...]
    virtual_size: int
    physical_size: int
    subtype: int
    loaded: bool
    identifier: bytes | None

    @property
    def dynamic(self) -> bool:
        """Whether the native provider reports a dynamically expandable disk, not fixed/differencing."""
        return self.subtype == _DYNAMIC


@functools.cache
def _library() -> Any:
    library = ctypes.WinDLL("virtdisk.dll", winmode=0x800, use_last_error=True)
    library.OpenVirtualDisk.argtypes = [ctypes.POINTER(_Storage), ctypes.c_wchar_p, ctypes.c_uint32,
                                        ctypes.c_uint32, ctypes.POINTER(_Open), ctypes.POINTER(ctypes.c_void_p)]
    library.OpenVirtualDisk.restype = ctypes.c_uint32
    library.GetVirtualDiskInformation.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
                                                 ctypes.POINTER(_Info), ctypes.POINTER(ctypes.c_uint32)]
    library.GetVirtualDiskInformation.restype = ctypes.c_uint32
    return library


@contextmanager
def _opened(disk: VirtualDisk) -> Iterator[tuple[Any, ctypes.c_void_p]]:
    library = _library()
    storage = _Storage(_DEVICES[disk.kind], _Guid.from_buffer_copy(_MICROSOFT))
    parameters = _Open(2, 1, 1, _Guid())  # Version2: metadata-only/read-only, never writable backing stores.
    handle = ctypes.c_void_p()
    code = library.OpenVirtualDisk(ctypes.byref(storage), disk.path, _ACCESS_NONE, _NO_PARENTS,
                                   ctypes.byref(parameters), ctypes.byref(handle))
    if code:
        raise ctypes.WinError(code)
    if not handle.value or handle.value == ctypes.c_void_p(-1).value:
        raise ValueError("Native virtual-disk provider returned no valid handle")
    try:
        yield library, handle
    finally:
        _kernel().CloseHandle(handle)


def _query(library: Any, handle: ctypes.c_void_p, version: int) -> _Info:
    info = _Info(version, _Value())
    size, used = ctypes.c_uint32(ctypes.sizeof(info)), ctypes.c_uint32()
    code = library.GetVirtualDiskInformation(handle, ctypes.byref(size), ctypes.byref(info), ctypes.byref(used))
    if code:
        raise ctypes.WinError(code)
    if (info.version != version or not _MINIMUMS[version] <= used.value <= ctypes.sizeof(info)
            or not _MINIMUMS[version] <= size.value <= ctypes.sizeof(info)):
        raise ValueError("Native virtual-disk information has an unexpected version/size")
    return info


def inspect_virtual_disk(disk: VirtualDisk, *, cancel: threading.Event | None = None) -> VirtualDiskInfo:
    """Explicitly query only a captured ordinary VHD/VHDX through read-only native header APIs.

    Pin captured nonlinked parents/file identity, refuse unavailable/changed records, open only the
    named backing file with metadata-only/read-only flags and NO_PARENTS, and close every native
    handle. Verify native format/vendor, provider subtype, virtual/physical sizes, mounted state and
    optional disk identifier, then recheck the original file snapshot. Fixed/differencing/loaded
    disks may be inspected but this observation grants no compaction authority or stopped-VM proof.
    Guest-used bytes remain unknown. No attachment, guest launch, elevation, mutation or fallback.
    Cancellation is checked before/after native queries; active calls remain synchronous/joined.
    """
    check_cancel(cancel)
    if os.name != "nt" or disk.kind not in _DEVICES or disk.snapshot is None or disk.issue:
        raise ValueError("Native VHD information requires an ordinary captured Windows VHD/VHDX")
    parents = directory_stamps(os.path.dirname(disk.path))
    with anchored_directory(parents), _pinned_file(disk.path):
        check_file(disk.path, disk.snapshot)
        check_cancel(cancel)
        return _inspect(disk, parents, cancel)


def _inspect(disk: VirtualDisk, parents: tuple[DirectoryStamp, ...],
             cancel: threading.Event | None) -> VirtualDiskInfo:
    with _opened(disk) as (library, handle):
        storage = _query(library, handle, 6).value.storage
        if storage.device != _DEVICES[disk.kind] or bytes(storage.vendor) != _MICROSOFT:
            raise ValueError("Native virtual-disk format/vendor differs from its captured candidate")
        size = _query(library, handle, 1).value.size
        subtype = _query(library, handle, 7).value.subtype
        loaded = _query(library, handle, 13).value.loaded
        identity = bytes(_query(library, handle, 2).value.guid)
        if loaded not in (0, 1) or subtype not in (2, _DYNAMIC, 4) or not size.virtual:
            raise ValueError("Native virtual-disk state/subtype/size is unknown")
        check_file(disk.path, disk.snapshot)
        check_cancel(cancel)
    return VirtualDiskInfo(disk, parents, size.virtual, size.physical, subtype, bool(loaded),
                           identity if any(identity) else None)
