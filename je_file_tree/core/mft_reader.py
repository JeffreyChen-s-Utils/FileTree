"""Read-only local NTFS 3.1 metadata access; no privilege changes, journal writes or payload API."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterator
import ctypes
from dataclasses import dataclass
import functools
import ntpath
import os
import re
import stat
import struct
import sys
from typing import Any

from je_file_tree.core import mft
from je_file_tree.core.pacing import give_way

_VOLUME_DATA = struct.Struct("<QqqqqIIIIqqqqq")
_EXTENDED = struct.Struct("<IHH")
_VOLUME_CONTROL = 0x90064
_MAX_METADATA = 8 * 1024 * 1024
_BATCH = 1024 * 1024
_CACHE_RECORDS = 256
_MAX_EXTENSIONS = 4096
_MAX_UNIT = 65536
_MIN_UNIT = 512
_MIN_RECORDS = 16
_HEADER_SIZE = 48
_FIXED_DRIVE = 3
_GUID = re.compile(r"\\\\\?\\Volume\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}\\\Z")


@dataclass(frozen=True, slots=True)
class VolumeData:
    """Validated NTFS geometry and initialized MFT extent; all values come from one native reply."""

    serial: int
    sector: int
    cluster: int
    record_size: int
    mft_size: int
    mft_lcn: int
    clusters: int


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise mft.MFTParseError(detail)


def _parse_record(raw: bytes, ordinal: int) -> mft.FileRecord:
    try:
        return mft.parse_record(raw, ordinal)
    except mft.MFTParseError as error:
        detail = ""
        if len(raw) >= _HEADER_SIZE:
            sequence, links, first, flags, used, allocated, base = struct.unpack_from("<HHHHIIQ", raw, 16)
            number, = struct.unpack_from("<I", raw, 44)
            detail = (f"; sequence={sequence}, links={links}, first={first}, flags={flags}, "
                      f"used={used}, allocated={allocated}, base={base}, header_number={number}")
        raise mft.MFTParseError(f"MFT record {ordinal}: {error}{detail}") from error


def parse_volume_data(data: bytes) -> VolumeData:
    """Require a bounded complete extended NTFS 3.1 reply and safe power-of-two geometry."""
    _require(_VOLUME_DATA.size + _EXTENDED.size <= len(data) <= _MAX_UNIT, "Incomplete NTFS volume metadata")
    fields = _VOLUME_DATA.unpack_from(data)
    serial, sectors, clusters, free, reserved, sector, cluster, record, _per_cluster, size, lcn, *_rest = fields
    extended, major, minor = _EXTENDED.unpack_from(data, _VOLUME_DATA.size)
    _require(extended >= _EXTENDED.size and extended <= len(data) - _VOLUME_DATA.size
             and (major, minor) == (3, 1), "Unsupported NTFS version or extended volume metadata")
    for unit in (sector, cluster, record):
        _require(_MIN_UNIT <= unit <= _MAX_UNIT and unit & (unit - 1) == 0, "Invalid NTFS geometry")
    _require(cluster >= sector and cluster % sector == 0 and sectors > 0 and clusters > 0
             and clusters * cluster <= sectors * sector and 0 <= free <= clusters and 0 <= reserved <= clusters
             and 0 <= lcn < clusters and _MIN_RECORDS * record <= size <= clusters * cluster
             and size % record == 0, "Invalid NTFS volume/MFT bounds")
    return VolumeData(serial, sector, cluster, record, size, lcn, clusters)


@functools.cache
def _kernel() -> Any:
    if sys.platform != "win32":
        raise OSError("Native NTFS metadata is Windows-only")
    kernel = ctypes.WinDLL("kernel32.dll", winmode=0x800, use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                  ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [ctypes.c_void_p], ctypes.c_int
    kernel.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    kernel.DeviceIoControl.restype = ctypes.c_int
    kernel.GetVolumePathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetVolumePathNameW.restype = ctypes.c_int
    kernel.GetVolumeNameForVolumeMountPointW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetVolumeNameForVolumeMountPointW.restype = ctypes.c_int
    kernel.GetDriveTypeW.argtypes, kernel.GetDriveTypeW.restype = [ctypes.c_wchar_p], ctypes.c_uint32
    kernel.GetVolumeInformationW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32,
                                            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetVolumeInformationW.restype = ctypes.c_int
    kernel.SetFilePointerEx.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_uint32]
    kernel.SetFilePointerEx.restype = ctypes.c_int
    kernel.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                               ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    kernel.ReadFile.restype = ctypes.c_int
    return kernel


def _administrator() -> bool:
    if sys.platform != "win32":
        return False
    shell = ctypes.WinDLL("shell32.dll", winmode=0x800)
    shell.IsUserAnAdmin.argtypes, shell.IsUserAnAdmin.restype = [], ctypes.c_int
    return bool(shell.IsUserAnAdmin())


def _volume(path: str) -> tuple[str, str]:
    drive = ntpath.splitdrive(path)[0]
    _require(bool(drive) and not drive.startswith("\\"), "NTFS metadata requires a local drive path")
    kernel = _kernel()
    root, identifier, filesystem = (ctypes.create_unicode_buffer(1024) for _ in range(3))
    if not kernel.GetVolumePathNameW(path, root, len(root)):
        raise ctypes.WinError(ctypes.get_last_error())
    _require(kernel.GetDriveTypeW(root.value) == _FIXED_DRIVE, "NTFS metadata requires a fixed local volume")
    if not kernel.GetVolumeInformationW(root.value, None, 0, None, None, None, filesystem, len(filesystem)):
        raise ctypes.WinError(ctypes.get_last_error())
    _require(filesystem.value == "NTFS", "NTFS metadata is unavailable on this filesystem")
    if not kernel.GetVolumeNameForVolumeMountPointW(root.value, identifier, len(identifier)):
        raise ctypes.WinError(ctypes.get_last_error())
    _require(_GUID.fullmatch(identifier.value) is not None, "Invalid NTFS volume GUID mapping")
    return root.value, identifier.value


class NTFSReader:
    """Owned read-only handle for one checked local NTFS volume; close after metadata observations.

    Construction requires an existing administrator token; it never requests elevation or enables
    privileges. Records and attribute lists are metadata observations, not a transactional snapshot.
    This reader does not perform ACL-aware Node construction or replace the ordinary scanner yet.
    """

    def __init__(self, path: str) -> None:
        if not _administrator():
            raise PermissionError("Direct NTFS metadata requires an existing administrator token")
        self.path = os.path.abspath(path)
        self.root, self.volume = _volume(self.path)
        self.initial = os.lstat(self.path)
        _require(stat.S_ISDIR(self.initial.st_mode) and not self.initial.st_file_attributes & 0x400,
                 "NTFS metadata root must be an ordinary directory")
        self.kernel = _kernel()
        self.handle = self.kernel.CreateFileW(self.volume.rstrip("\\"), 0x80000000, 7, None, 3, 0x20000000, None)
        if self.handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self._cache: OrderedDict[int, mft.FileRecord] = OrderedDict()
        initialized = False
        try:
            self.geometry = self._geometry()
            _require(self.initial.st_dev in (self.geometry.serial, self.geometry.serial & 0xFFFFFFFF),
                     "NTFS root/volume serial changed")
            raw = self._read(self.geometry.mft_lcn * self.geometry.cluster, self.geometry.record_size)
            base = _parse_record(raw, 0)
            _require(base.in_use and not base.base_reference, "Invalid MFT base record")
            heads = [item for item in base.attributes if item.kind == mft.DATA and not item.name
                     and item.lowest_vcn == 0]
            _require(len(heads) == 1 and not heads[0].resident and not heads[0].flags
                     and heads[0].size is not None and heads[0].size >= self.geometry.mft_size,
                     "Unsupported MFT data stream")
            self.runs = heads[0].runs
            self._check_runs(self.runs)
            self._cache[0] = base
            self.runs = self._mft_runs(base)
            self.verify()
            initialized = True
        finally:
            if not initialized:
                self.close()

    def __enter__(self) -> NTFSReader:
        """Return the checked reader; the context always closes its own volume handle."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Close metadata handles and release bounded record caches on success or failure."""
        self.close()

    def close(self) -> None:
        """Close only this reader's handle; never detach, lock, dismount or mutate the volume."""
        if self.handle is not None:
            handle, self.handle = self.handle, None
            self._cache.clear()
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())

    def _geometry(self) -> VolumeData:
        buffer, returned = ctypes.create_string_buffer(4096), ctypes.c_uint32()
        if not self.kernel.DeviceIoControl(self.handle, _VOLUME_CONTROL, None, 0, buffer, len(buffer),
                                           ctypes.byref(returned), None):
            raise ctypes.WinError(ctypes.get_last_error())
        _require(returned.value <= len(buffer), "Oversized NTFS geometry reply")
        return parse_volume_data(buffer.raw[:returned.value])

    def _read(self, offset: int, size: int) -> bytes:
        _require(self.handle is not None and offset >= 0 and 0 < size <= _MAX_METADATA
                 and offset + size <= self.geometry.clusters * self.geometry.cluster, "Invalid metadata read bounds")
        sector = self.geometry.sector
        start, end = offset // sector * sector, -(-(offset + size) // sector) * sector
        count = end - start
        storage = ctypes.create_string_buffer(count + sector)
        address = -(-ctypes.addressof(storage) // sector) * sector
        returned = ctypes.c_uint32()
        if (not self.kernel.SetFilePointerEx(self.handle, start, None, 0)
                or not self.kernel.ReadFile(self.handle, ctypes.c_void_p(address), count,
                                            ctypes.byref(returned), None)):
            raise ctypes.WinError(ctypes.get_last_error())
        _require(returned.value == count, "Truncated raw NTFS metadata read")
        return ctypes.string_at(address + offset - start, size)

    def _check_runs(self, runs: tuple[mft.Run, ...]) -> None:
        for run in runs:
            _require(run.lcn is not None and 0 <= run.lcn < self.geometry.clusters
                     and run.lcn + run.length <= self.geometry.clusters, "Invalid/sparse metadata extents")

    def _stream(self, runs: tuple[mft.Run, ...], offset: int, size: int) -> bytes:
        _require(offset >= 0 and 0 < size <= _MAX_METADATA, "Invalid metadata stream read")
        self._check_runs(runs)
        result = bytearray()
        cluster, end = self.geometry.cluster, offset + size
        for run in runs:
            start, stop = run.vcn * cluster, (run.vcn + run.length) * cluster
            if start <= offset < stop:
                count = min(stop, end) - offset
                result.extend(self._read(run.lcn * cluster + offset - start, count))
                offset += count
                if offset == end:
                    return bytes(result)
        raise mft.MFTParseError("Missing or noncontiguous metadata extents")

    def record(self, ordinal: int) -> mft.FileRecord:
        """Read one raw MFT ordinal from checked extents, with a bounded per-reader metadata cache."""
        _require(self.handle is not None and 0 <= ordinal < self.geometry.mft_size // self.geometry.record_size,
                 "Closed reader or MFT ordinal out of bounds")
        if ordinal not in self._cache:
            raw = self._stream(self.runs, ordinal * self.geometry.record_size, self.geometry.record_size)
            self._cache[ordinal] = _parse_record(raw, ordinal)
            if len(self._cache) > _CACHE_RECORDS:
                self._cache.popitem(last=False)
        self._cache.move_to_end(ordinal)
        return self._cache[ordinal]

    def _list(self, base: mft.FileRecord) -> tuple[mft.AttributeListEntry, ...]:
        lists = [attribute for attribute in base.attributes if attribute.kind == mft.ATTRIBUTE_LIST]
        if not lists:
            return ()
        _require(len(lists) == 1 and lists[0].lowest_vcn == 0, "Unsupported split attribute-list stream")
        attribute = lists[0]
        _require(attribute.size is not None and 0 < attribute.size <= _MAX_METADATA, "Excessive attribute list")
        data = (attribute.value if attribute.resident else self._stream(attribute.runs, 0, attribute.size))
        _require(data is not None, "Missing attribute-list metadata")
        return mft.parse_attribute_list(data)

    def attributes(self, base: mft.FileRecord) -> tuple[mft.Attribute, ...]:
        """Resolve only checked sequence/base-owned extensions; cycles and nested list streams refuse."""
        _require(base.in_use and not base.base_reference, "Attribute owner is not a live base record")
        result = list(base.attributes)
        identities = {(base.reference, item.instance) for item in result}
        references = {base.reference}
        for entry in self._list(base):
            _require(len(references) < _MAX_EXTENSIONS, "Excessive MFT extension records")
            extension = base if entry.reference == base.reference else self.record(entry.reference & ((1 << 48) - 1))
            _require(extension.in_use and extension.reference == entry.reference
                     and (extension is base or extension.base_reference == base.reference),
                     "Stale or foreign MFT extension")
            if extension is not base:
                _require(not any(item.kind == mft.ATTRIBUTE_LIST for item in extension.attributes),
                         "Nested/cyclic attribute-list extension")
            matches = [item for item in extension.attributes if (item.kind, item.name, item.lowest_vcn, item.instance)
                       == (entry.kind, entry.name, entry.lowest_vcn, entry.instance)]
            _require(len(matches) == 1, "Missing or ambiguous MFT extension attribute")
            references.add(entry.reference)
            identity = entry.reference, entry.instance
            if identity not in identities:
                result.append(matches[0])
                identities.add(identity)
        return tuple(result)

    def _mft_runs(self, base: mft.FileRecord) -> tuple[mft.Run, ...]:
        segments = sorted((item for item in self.attributes(base) if item.kind == mft.DATA and not item.name),
                          key=lambda item: item.lowest_vcn)
        runs, next_vcn = [], 0
        for segment in segments:
            _require(not segment.resident and not segment.flags and segment.lowest_vcn == next_vcn,
                     "Invalid or overlapping MFT data segments")
            for run in segment.runs:
                _require(run.vcn == next_vcn, "Noncontiguous MFT mapping")
                runs.append(run)
                next_vcn += run.length
        self._check_runs(tuple(runs))
        _require(next_vcn * self.geometry.cluster >= self.geometry.mft_size, "Incomplete MFT data mapping")
        return tuple(runs)

    def records(self, check: Callable[[], None] | None = None, *,
                directories_only: bool = False) -> Iterator[mft.FileRecord]:
        """Stream initialized MFT batches; never retain all records or silently ignore an in-use corrupt segment."""
        size = self.geometry.record_size
        empty = bytes(size)
        for offset in range(0, self.geometry.mft_size, _BATCH):
            if check is not None:
                check()
            raw = self._stream(self.runs, offset, min(_BATCH, self.geometry.mft_size - offset))
            for start in range(0, len(raw), size):
                value = raw[start:start + size]
                if value == empty:
                    continue  # Unformatted unused initialized slots have no FILE metadata.
                _require(value[:4] == b"FILE", "Invalid MFT record signature")
                flags, = struct.unpack_from("<H", value, 22)
                if flags & 1 and (not directories_only or flags & 2):
                    record = _parse_record(value, (offset + start) // size)
                    if record.is_dir:
                        give_way()
                    yield record

    def verify(self) -> None:
        """Refuse changed selected roots, volume mapping or initialized MFT geometry before publication."""
        current = os.lstat(self.path)
        _require((current.st_dev, current.st_ino) == (self.initial.st_dev, self.initial.st_ino)
                 and not current.st_file_attributes & 0x400 and _volume(self.path) == (self.root, self.volume)
                 and self._geometry() == self.geometry, "NTFS root/volume/MFT changed")
