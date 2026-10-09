"""Captured, reviewed detached dynamic VHD/VHDX compaction through the fixed native SDK."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
import ctypes
from dataclasses import dataclass, replace
import os
import stat
import threading
from typing import Any

from je_file_tree.core.compression import file_system
from je_file_tree.core.compression_ops import _kernel, _pinned_path
from je_file_tree.core.copy_io import check_cancel, check_file
from je_file_tree.core.no_replace import anchored_directory
from je_file_tree.core.protected import protected_places, protection_of
from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot
from je_file_tree.core.system_files import system_file
from je_file_tree.core.virtual_disk_info import (
    VirtualDiskInfo, _DEVICES, _DYNAMIC, _Guid, _library, _MICROSOFT, _Open, _query, _Storage, inspect_virtual_disk,
)
from je_file_tree.core.virtual_disk_runtime import DiskRuntime, stopped_runtime
from je_file_tree.core.virtual_disks import VirtualDisk
from je_file_tree.core.windows_allocation import file_allocation

_UNAVAILABLE = 0x1 | 0x4 | 0x400 | 0x800 | 0x1000 | 0x4000 | 0x40000 | 0x400000


class _Compact(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("reserved", ctypes.c_uint32)]


@dataclass(frozen=True, slots=True)
class CompactionPlan:
    """One frozen file/header/parent/provider review; never a command or permission to start a guest."""

    info: VirtualDiskInfo
    runtime: DiskRuntime


@dataclass(frozen=True, slots=True)
class CompactionOutcome:
    """Actual native completion and separately observed backing allocation; errors may follow success.

    Writable opens may repair native metadata even if compaction later fails. Once attempted, always
    rescan. Unknown post-call allocation is not zero; guest usage/free recovery is never inferred.
    """

    attempted: bool = False
    compacted: bool = False
    before: int | None = None
    after: int | None = None
    error: str = ""


def _eligible(disk: VirtualDisk) -> None:
    if os.name != "nt" or disk.kind not in _DEVICES or disk.snapshot is None or disk.issue:
        raise ValueError("Compaction requires an ordinary captured Windows VHD/VHDX")
    check_file(disk.path, disk.snapshot)
    info = unpack_snapshot(disk.snapshot)
    if info.links != 1 or info.attributes & _UNAVAILABLE:
        raise ValueError("Linked, read-only, compressed, encrypted, system or unavailable backing file")
    if protection_of(disk.path, protected_places()) is not None or system_file(disk.path) is not None:
        raise ValueError("Protected or system-managed backing file")
    if file_system(disk.path) != "NTFS":
        raise ValueError("Compaction currently requires a fixed local NTFS backing volume")


def _detached(info: VirtualDiskInfo) -> None:
    if not info.dynamic or info.loaded or info.identifier is None:
        raise ValueError("Compaction requires a detached dynamic disk with a known identifier")


def _pin_local(path: str) -> AbstractContextManager[None]:
    # WSL commonly registers extended drive paths; never turn an extended UNC/device path into local authority.
    local = path[4:] if path.startswith("\\\\?\\") else path
    return _pinned_path(local)


def prepare_compaction(disk: VirtualDisk, *, cancel: threading.Event | None = None) -> CompactionPlan:
    """Prepare a read-only review off the GUI thread; never elevate, attach, stop or mutate a disk.

    Require an ordinary one-link local NTFS file, nonlinked ancestors, complete registered/runtime
    state, a detached native dynamic VHD/VHDX and an exact UUID. Refuse fixed/differencing disks and
    unsupported formats. The caller must review the literal path/native zero-block operation with
    default-No approval and confirm the owning machine remains stopped before executing this plan.
    """
    check_cancel(cancel)
    _eligible(disk)
    with _pin_local(disk.path):
        runtime = stopped_runtime(disk, cancel=cancel)
        info = inspect_virtual_disk(disk, cancel=cancel)
        _detached(info)
        return CompactionPlan(info, runtime)


@contextmanager
def _writable(disk: VirtualDisk) -> Iterator[tuple[Any, ctypes.c_void_p]]:
    library = _library()
    storage = _Storage(_DEVICES[disk.kind], _Guid.from_buffer_copy(_MICROSOFT))
    parameters, handle = _Open(2, 0, 0, _Guid()), ctypes.c_void_p()
    code = library.OpenVirtualDisk(ctypes.byref(storage), disk.path, 0, 1,
                                   ctypes.byref(parameters), ctypes.byref(handle))
    if code:
        raise ctypes.WinError(code)
    if not handle.value or handle.value == ctypes.c_void_p(-1).value:
        raise ValueError("Native writable virtual-disk handle is invalid")
    try:
        yield library, handle
    finally:
        _kernel().CloseHandle(handle)


def _same_header(library: Any, handle: ctypes.c_void_p, expected: VirtualDiskInfo) -> None:
    storage = _query(library, handle, 6).value.storage
    if (storage.device != _DEVICES[expected.disk.kind] or bytes(storage.vendor) != _MICROSOFT
            or bytes(_query(library, handle, 2).value.guid) != expected.identifier
            or _query(library, handle, 7).value.subtype != _DYNAMIC
            or _query(library, handle, 13).value.loaded != 0
            or _query(library, handle, 1).value.size.virtual != expected.virtual_size):
        raise ValueError("Native format, UUID, dynamic type, detached state or capacity changed")


def _current_allocation(plan: CompactionPlan) -> int:
    disk = plan.info.disk
    current = unpack_snapshot(stat_snapshot(disk.path))
    before = unpack_snapshot(disk.snapshot)
    if (current.identity != before.identity or not stat.S_ISREG(current.mode) or current.is_link
            or current.links != 1 or current.attributes & _UNAVAILABLE):
        raise ValueError("Backing identity/availability changed during compaction; rescan required")
    allocation = file_allocation(disk.path, os.lstat(disk.path))
    if allocation is None:
        raise ValueError("Backing allocation is unknown after native operation")
    return allocation


def execute_compaction(plan: CompactionPlan, *, machine_stopped: bool,
                       cancel: threading.Event | None = None) -> CompactionOutcome:
    """Execute one explicitly approved frozen plan; joined zero-block compaction never attaches guests.

    Recheck complete file/parent identity, local NTFS scope, runtime registration/stopped observations
    and read-only header immediately before a writable Version2/NO_PARENTS native open. Requery exact
    native UUID/type/detachment/capacity on that same handle, then call CompactVirtualDisk with zero
    flags and synchronous completion. No command strings, automatic UAC, attach/detach/shutdown or
    fallback. Cancellation is checked before mutation; an active native call must finish and its true
    success remains visible, including later canceled/failed observations. Allocation deltas are
    observations, not guaranteed OS free recovery; zero saving is a valid success. Audit approvals
    must be durably recorded by the caller before this method; attempted results require a rescan.
    """
    attempted = compacted = False
    before = after = None
    try:
        check_cancel(cancel)
        if machine_stopped is not True:
            raise ValueError("Explicit stopped-machine confirmation is required")
        _detached(plan.info)
        _eligible(plan.info.disk)
        with anchored_directory(plan.info.parents), _pin_local(plan.info.disk.path):
            if stopped_runtime(plan.info.disk, cancel=cancel) != plan.runtime:
                raise ValueError("Registered runtime source changed since review")
            current = inspect_virtual_disk(plan.info.disk, cancel=cancel)
            # Anchors compare parent identities, not timestamps changed by unrelated sibling arrivals.
            if replace(current, parents=plan.info.parents) != plan.info:
                raise ValueError("Native read-only observations changed since review")
            before = _current_allocation(plan)
            check_file(plan.info.disk.path, plan.info.disk.snapshot)
            check_cancel(cancel)
            attempted = True
            with _writable(plan.info.disk) as (library, handle):
                _same_header(library, handle, plan.info)
                check_cancel(cancel)
                library.CompactVirtualDisk.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                                      ctypes.POINTER(_Compact), ctypes.c_void_p]
                library.CompactVirtualDisk.restype = ctypes.c_uint32
                parameters = _Compact(1, 0)
                code = library.CompactVirtualDisk(handle, 0, ctypes.byref(parameters), None)
                if code:
                    raise ctypes.WinError(code)
                compacted = True
                _same_header(library, handle, plan.info)
            after = _current_allocation(plan)
    except (OSError, ValueError, UnicodeError) as exc:
        return CompactionOutcome(attempted, compacted, before, after, str(exc))
    return CompactionOutcome(attempted, compacted, before, after)
