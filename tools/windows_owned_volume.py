"""Fresh disposable VHD/VHDX NTFS fixtures; never accept existing images, drives or disks."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import uuid

from je_file_tree.core import virtual_disk_info as native
from je_file_tree.core.copy_io import _pinned_file
from je_file_tree.core.no_replace import anchored_directory, directory_stamps
from je_file_tree.core.snapshot import pack_snapshot
from je_file_tree.core.virtual_disks import VirtualDisk

_CAPACITY = 512 * 1024 * 1024
_CAPACITIES = (_CAPACITY, 2048 * 1024 * 1024)
_PREFIX = "filetree-owned-ntfs-"


class _Create(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("padding", ctypes.c_uint32), ("guid", native._Guid),
               ("maximum", ctypes.c_uint64), ("block", ctypes.c_uint32), ("sector", ctypes.c_uint32),
               ("physical", ctypes.c_uint32), ("parent", ctypes.c_wchar_p), ("source", ctypes.c_wchar_p),
               ("flags", ctypes.c_uint32), ("parent_type", native._Storage), ("source_type", native._Storage),
               ("resiliency", native._Guid)]


class _Privilege(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32), ("low", ctypes.c_uint32),
               ("high", ctypes.c_int32), ("attributes", ctypes.c_uint32)]


@dataclass(frozen=True, slots=True)
class OwnedVolume:
    """One live owned test image and its native mapped device/OS-assigned drive; no user selector."""

    image: Path
    identifier: bytes
    physical: str
    root: Path
    volume_id: str
    label: str
    handle: ctypes.c_void_p
    creation_identifier: bytes = b""
    capacity: int = _CAPACITY


def require(condition: bool, message: str) -> None:
    """Refuse uncertain fixture ownership or native results before another operation."""
    if not condition:
        raise RuntimeError(message)


def _administrator() -> None:
    require(sys.platform == "win32", "Native Windows fixture required")
    shell = ctypes.WinDLL("shell32.dll", winmode=0x800)
    require(bool(shell.IsUserAnAdmin()), "Administrator fixture runner required; no elevation is requested")


def _enable_volume_privilege() -> None:
    kernel = native._kernel()
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    advapi = ctypes.WinDLL("advapi32.dll", winmode=0x800, use_last_error=True)
    advapi.OpenProcessToken.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    advapi.LookupPrivilegeValueW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
    advapi.AdjustTokenPrivileges.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
                                           ctypes.c_void_p, ctypes.c_void_p]
    token = ctypes.c_void_p()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x28, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        privilege = _Privilege(1, 0, 0, 2)
        if not advapi.LookupPrivilegeValueW(None, "SeManageVolumePrivilege", ctypes.byref(privilege, 4)):
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.set_last_error(0)
        if not advapi.AdjustTokenPrivileges(token, False, ctypes.byref(privilege), 0, None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(token)


def _library():
    library = native._library()
    library.CreateVirtualDisk.argtypes = [ctypes.POINTER(native._Storage), ctypes.c_wchar_p, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(_Create), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p)]
    library.CreateVirtualDisk.restype = ctypes.c_uint32
    library.AttachVirtualDisk.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                          ctypes.c_void_p, ctypes.c_void_p]
    library.AttachVirtualDisk.restype = ctypes.c_uint32
    library.DetachVirtualDisk.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    library.DetachVirtualDisk.restype = ctypes.c_uint32
    library.GetVirtualDiskPhysicalPath.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_wchar_p]
    library.GetVirtualDiskPhysicalPath.restype = ctypes.c_uint32
    return library


def _create(library, path: Path, identity: bytes, capacity: int = _CAPACITY) -> ctypes.c_void_p:
    require(capacity in _CAPACITIES, "Refusing an unapproved fixture capacity")
    require(not os.path.lexists(path), "Refusing an existing fixture image")
    kind = path.suffix.removeprefix(".")
    require(kind in native._DEVICES, "Refusing an unsupported fresh fixture format")
    storage = native._Storage(native._DEVICES[kind], native._Guid.from_buffer_copy(native._MICROSOFT))
    parameters = _Create()
    parameters.version, parameters.guid = 2, native._Guid.from_buffer_copy(identity)
    parameters.maximum, parameters.sector = capacity, 512
    handle = ctypes.c_void_p()
    code = library.CreateVirtualDisk(ctypes.byref(storage), str(path), 0, None, 0, 0,
                                    ctypes.byref(parameters), None, ctypes.byref(handle))
    if code:
        raise ctypes.WinError(code)
    require(bool(handle.value), "Creation returned no owned image handle")
    return handle


def _physical(library, handle: ctypes.c_void_p) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    size = ctypes.c_uint32(ctypes.sizeof(buffer))
    code = library.GetVirtualDiskPhysicalPath(handle, ctypes.byref(size), buffer)
    if code:
        raise ctypes.WinError(code)
    require(re.fullmatch(r"\\\\\.\\PhysicalDrive[1-9][0-9]*", buffer.value) is not None,
            "Refusing an unknown/host physical disk mapping")
    return buffer.value


def _initialize(physical: str, label: str, capacity: int = _CAPACITY) -> dict[str, str]:
    require(capacity in _CAPACITIES, "Refusing an unapproved fixture capacity")
    require(re.fullmatch(r"\\\\\.\\PhysicalDrive[1-9][0-9]*", physical) is not None,
            "Refusing an unknown physical fixture mapping")
    require(re.fullmatch(r"FT-[0-9a-f]{12}", label) is not None, "Refusing an unknown fixture label")
    number = physical.removeprefix("\\\\.\\PhysicalDrive")
    program = Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = Path(__file__).with_name("initialize_owned_ntfs.ps1").resolve(strict=True)
    result = subprocess.run([str(program), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script),  # noqa: S603
                             "-DiskNumber", number, "-Label", label, "-ExpectedCapacity", str(capacity)],
                            check=True, timeout=60,
                            capture_output=True, encoding="utf-8")
    data = json.loads(result.stdout)
    require(isinstance(data, dict) and re.fullmatch(r"[A-Z]:\\", data.get("root", "")) is not None,
            "Fixture did not receive a valid OS-assigned drive root")
    require(data.get("label") == label and data.get("filesystem") == "NTFS" and bool(data.get("volume_id")),
            "Fixture volume identity/NTFS format could not be confirmed")
    return data


def _cleanup(owned: Path, image: Path, directory_id: tuple[int, int], image_id: tuple[int, int]) -> None:
    _owned_image(owned, image, directory_id, image_id)
    with anchored_directory(directory_stamps(str(owned))):
        _owned_image(owned, image, directory_id, image_id)
        image.unlink()
    owned.rmdir()


def _owned_image(owned: Path, image: Path, directory_id: tuple[int, int], image_id: tuple[int, int]) -> None:
    require(owned.name.startswith(_PREFIX) and owned.resolve(strict=True) == owned,
            "Refusing redirected/unowned fixture cleanup")
    info = owned.lstat()
    require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == directory_id
            and not getattr(info, "st_file_attributes", 0) & 0x400,
            "Fixture scratch identity changed; retain it")
    require(image.parent == owned and set(owned.iterdir()) == {image}, "Unexpected scratch entries; retain them")
    info = image.lstat()
    require(stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
            and (info.st_dev, info.st_ino) == image_id, "Fixture image identity changed; retain it")


def _after_detach(owned: Path, image: Path, identities: tuple[tuple[int, int], tuple[int, int]],
                  volume: OwnedVolume, callback: Callable[[OwnedVolume], None]) -> None:
    _owned_image(owned, image, *identities)
    with anchored_directory(directory_stamps(str(owned))), _pinned_file(str(image)):
        _owned_image(owned, image, *identities)
        # Setup explicitly writes/formats the newly created disk. Review only its final detached
        # header; creation-time UUID is evidence, not approval for the setup-modified backing file.
        info = image.lstat()
        disk = VirtualDisk(str(image), image.suffix.removeprefix("."), "scan", image.name, None,
                           info.st_size, None, pack_snapshot(info))
        observed = native.inspect_virtual_disk(disk)
        require(observed.identifier is not None and observed.dynamic and not observed.loaded,
                "Owned setup did not produce a valid detached dynamic disk")
        callback(replace(volume, identifier=observed.identifier))


def verify_volume(volume: OwnedVolume) -> None:
    """Recheck the live owned VHD handle's device and the root's exact OS volume GUID before mutation."""
    require(_physical(_library(), volume.handle) == volume.physical, "Owned device mapping changed")
    kernel = native._kernel()
    kernel.GetVolumeNameForVolumeMountPointW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    buffer = ctypes.create_unicode_buffer(256)
    if not kernel.GetVolumeNameForVolumeMountPointW(str(volume.root), buffer, len(buffer)):
        raise ctypes.WinError(ctypes.get_last_error())
    require(buffer.value.casefold() == volume.volume_id.casefold(), "Owned drive's volume GUID changed")


@contextmanager
def owned_ntfs_volume(*, kind: str = "vhdx",
                      after_detach: Callable[[OwnedVolume], None] | None = None,
                      capacity: int = _CAPACITY) -> Iterator[OwnedVolume]:
    """Create, map and format only one new private VHD/VHDX, then detach before owned image cleanup.

    No existing path, drive, physical disk or bin is accepted. Format only the exact native mapping
    of this newly created UUID with a RAW/no-partitions/no-boot/no-system/size proof in the fixed
    PowerShell script. The OS assigns the unused drive letter. Detachment failure retains scratch.
    This validation-only tool requires an existing administrator token; it never prompts for UAC.
    An optional hook runs only after successful body/detach/handle-close, with original directory/file
    identities rechecked and pinned. Hook failure retains the image, including possible attachment.
    Capacity is restricted to 512 MiB or 2 GiB and must match the exact new disk before formatting.
    """
    require(capacity in _CAPACITIES, "Refusing an unapproved fixture capacity")
    _administrator()
    _enable_volume_privilege()
    require(kind in native._DEVICES, "Only fresh VHD/VHDX fixture formats are allowed")
    owned = Path(tempfile.mkdtemp(prefix=_PREFIX)).resolve(strict=True)
    initial = owned.lstat()
    require(not list(owned.iterdir()) and not getattr(initial, "st_file_attributes", 0) & 0x400,
            "Fresh owned scratch required")
    image, identity = owned / ("owned." + kind), uuid.uuid4().bytes_le
    library = _library()
    handle = _create(library, image, identity, capacity)
    attached = False
    detached = False
    image_info = volume = None
    completed = False
    try:
        image_info = image.lstat()
        require(bytes(native._query(library, handle, 2).value.guid) == identity, "Created UUID differs")
        code = library.AttachVirtualDisk(handle, None, 2, 0, None, None)
        if code:
            raise ctypes.WinError(code)
        attached = True
        physical = _physical(library, handle)
        data = _initialize(physical, "FT-" + uuid.uuid4().hex[:12], capacity)
        require(_physical(library, handle) == physical, "Native fixture mapping changed during formatting")
        volume = OwnedVolume(image, identity, physical, Path(data["root"]), data["volume_id"], data["label"],
                             handle, identity, capacity)
        verify_volume(volume)
        yield volume
        completed = True
    finally:
        try:
            code = library.DetachVirtualDisk(handle, 0, 0) if attached else 0
            if code:
                raise OSError(f"Owned disk detachment failed ({code}); retained scratch: {owned}")
            detached = True
        finally:
            native._kernel().CloseHandle(handle)
            if detached and image_info is not None:
                # A failed hook may have retained an attachment; never delete its image as a fallback.
                if completed and after_detach is not None:
                    identities = ((initial.st_dev, initial.st_ino), (image_info.st_dev, image_info.st_ino))
                    _after_detach(owned, image, identities, volume, after_detach)
                _cleanup(owned, image, (initial.st_dev, initial.st_ino), (image_info.st_dev, image_info.st_ino))
