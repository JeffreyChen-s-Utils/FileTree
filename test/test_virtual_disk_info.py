"""Read-only VHD inspection verifies native ABI, guarded identities and complete native failures."""

from contextlib import nullcontext
import ctypes
from dataclasses import replace
import hashlib
import os
import threading
from types import SimpleNamespace
import uuid

import pytest

from je_file_tree.core import virtual_disk_info as native
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import stat_snapshot
from je_file_tree.core.virtual_disks import find_virtual_disks


def _disk(tmp_path):
    (tmp_path / "owned.vhd").write_bytes(b"Owned test bytes, not a valid virtual disk")
    return find_virtual_disks(scan(tmp_path).root, registrations=[]).rows[0]


def _provider(tmp_path, monkeypatch):
    disk = _disk(tmp_path)
    calls, closed = [], []
    values = {1: native._Size(64 * 1024 * 1024, 8192, 2 * 1024 * 1024, 512),
              2: native._Guid.from_buffer_copy(uuid.uuid4().bytes_le),
              6: native._Storage(2, native._Guid.from_buffer_copy(native._MICROSOFT)), 7: 3, 13: 0}

    def opened(storage, path, access, flags, parameters, handle):
        assert storage._obj.device == 2 and bytes(storage._obj.vendor) == native._MICROSOFT
        assert path == disk.path and access == 0 and flags == 1
        assert parameters._obj.version == 2
        assert parameters._obj.get_info_only == parameters._obj.read_only == 1
        assert not any(bytes(parameters._obj.resiliency))
        handle._obj.value = 123
        calls.append("open")
        return 0

    def query(_handle, size, info, used):
        version = info._obj.version
        calls.append(version)
        field = {1: "size", 2: "guid", 6: "storage", 7: "subtype", 13: "loaded"}[version]
        setattr(info._obj.value, field, values[version])
        size._obj.value = used._obj.value = native._MINIMUMS[version]
        return 0

    library = SimpleNamespace(OpenVirtualDisk=opened, GetVirtualDiskInformation=query)
    monkeypatch.setattr(native, "os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr(native, "_library", lambda: library)
    monkeypatch.setattr(native, "_kernel", lambda: SimpleNamespace(CloseHandle=lambda h: closed.append(h.value)))
    monkeypatch.setattr(native, "_pinned_file", lambda _path: nullcontext())
    monkeypatch.setattr(native.ctypes, "WinError", lambda code: OSError(code, "native failure"), raising=False)
    return disk, library, values, calls, closed


def test_fixed_windows_abi_offsets_and_sizes():
    assert ctypes.sizeof(native._Guid) == 16 and ctypes.sizeof(native._Storage) == 20
    assert ctypes.sizeof(native._Open) == 28 and native._Open.resiliency.offset == 12
    assert ctypes.sizeof(native._Size) == 24 and native._Size.physical.offset == 8
    assert ctypes.sizeof(native._Info) == 32 and native._Info.value.offset == 8


@pytest.mark.parametrize("subtype,loaded", [(2, 0), (3, 0), (4, 1)])
def test_valid_native_metadata_including_noncompactable_states(tmp_path, monkeypatch, subtype, loaded):
    disk, _lib, values, calls, closed = _provider(tmp_path, monkeypatch)
    before = stat_snapshot(disk.path)
    values[7], values[13] = subtype, loaded
    info = native.inspect_virtual_disk(disk)
    assert info.disk is disk and info.parents
    assert info.virtual_size == 64 * 1024 * 1024 and info.physical_size == 8192
    assert info.loaded == bool(loaded) and info.dynamic == (subtype == 3)
    assert info.identifier == bytes(values[2]) and stat_snapshot(disk.path) == before
    assert calls == ["open", 6, 1, 7, 13, 2] and closed == [123]


@pytest.mark.parametrize("change", ["issue", "format", "snapshot", "contents", "hardlink", "cancel"])
def test_refused_records_never_open_a_native_header(tmp_path, monkeypatch, change):
    disk, _lib, _values, calls, closed = _provider(tmp_path, monkeypatch)
    cancel = threading.Event()
    if change == "issue":
        disk = replace(disk, issue="unavailable")
    elif change == "format":
        disk = replace(disk, kind="qcow2")
    elif change == "snapshot":
        disk = replace(disk, snapshot=None)
    elif change == "contents":
        with open(disk.path, "ab") as file:
            file.write(b"changed")
    elif change == "hardlink":
        os.link(disk.path, tmp_path / "alias")
    else:
        cancel.set()
    with pytest.raises((ValueError, InterruptedError)):
        native.inspect_virtual_disk(disk, cancel=cancel)
    assert not calls and not closed


@pytest.mark.parametrize("query_version", [6, 1, 7, 13, 2])
def test_native_query_failure_closes_handle_and_preserves_original(tmp_path, monkeypatch, query_version):
    disk, lib, _values, _calls, closed = _provider(tmp_path, monkeypatch)
    before = stat_snapshot(disk.path)
    query = lib.GetVirtualDiskInformation
    lib.GetVirtualDiskInformation = lambda *args: 5 if args[2]._obj.version == query_version else query(*args)
    with pytest.raises(OSError):
        native.inspect_virtual_disk(disk)
    assert closed == [123] and stat_snapshot(disk.path) == before


@pytest.mark.parametrize("change", ["vendor", "format", "subtype", "loaded", "zero_size", "short", "long"])
def test_unknown_native_payload_is_refused_and_handle_closed(tmp_path, monkeypatch, change):
    disk, lib, values, _calls, closed = _provider(tmp_path, monkeypatch)
    if change == "vendor":
        values[6].vendor = native._Guid()
    elif change == "format":
        values[6].device = 3
    elif change == "subtype":
        values[7] = 0
    elif change == "loaded":
        values[13] = 9
    elif change == "zero_size":
        values[1].virtual = 0
    else:
        query = lib.GetVirtualDiskInformation
        def altered(*args):
            code = query(*args)
            args[3]._obj.value = 0 if change == "short" else 999
            return code
        lib.GetVirtualDiskInformation = altered
    with pytest.raises(ValueError):
        native.inspect_virtual_disk(disk)
    assert closed == [123]


def test_late_cancellation_and_changed_source_publish_no_native_observation(tmp_path, monkeypatch):
    disk, lib, _values, _calls, closed = _provider(tmp_path, monkeypatch)
    cancel, query = threading.Event(), lib.GetVirtualDiskInformation
    def finish(*args):
        code = query(*args)
        if args[2]._obj.version == 2:
            cancel.set()
        return code
    lib.GetVirtualDiskInformation = finish
    with pytest.raises(InterruptedError):
        native.inspect_virtual_disk(disk, cancel=cancel)
    assert closed == [123]
    cancel.clear()
    def changed(*args):
        code = query(*args)
        if args[2]._obj.version == 2:
            with open(disk.path, "ab") as source:
                source.write(b"changed")
        return code
    lib.GetVirtualDiskInformation = changed
    with pytest.raises(ValueError):
        native.inspect_virtual_disk(disk)
    assert closed == [123, 123]


def test_nonwindows_never_loads_native_library(tmp_path, monkeypatch):
    disk = _disk(tmp_path)
    monkeypatch.setattr(native, "os", SimpleNamespace(name="posix", path=os.path))
    monkeypatch.setattr(native, "_library", lambda: pytest.fail("Non-Windows must not load the native provider"))
    with pytest.raises(ValueError):
        native.inspect_virtual_disk(disk)


class _Create(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("padding", ctypes.c_uint32), ("guid", native._Guid),
               ("maximum", ctypes.c_uint64), ("block", ctypes.c_uint32), ("sector", ctypes.c_uint32),
               ("parent", ctypes.c_wchar_p), ("source", ctypes.c_wchar_p)]


class _Create2(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("padding", ctypes.c_uint32), ("guid", native._Guid),
               ("maximum", ctypes.c_uint64), ("block", ctypes.c_uint32), ("sector", ctypes.c_uint32),
               ("physical", ctypes.c_uint32), ("parent", ctypes.c_wchar_p), ("source", ctypes.c_wchar_p),
               ("flags", ctypes.c_uint32), ("parent_type", native._Storage), ("source_type", native._Storage),
               ("resiliency", native._Guid)]


@pytest.mark.skipif(os.name != "nt", reason="Native Windows VHD provider required")
@pytest.mark.parametrize("fixed", [False, True])
@pytest.mark.parametrize("kind", ["vhd", "vhdx"])
def test_native_fresh_owned_vhd_header_and_identity_without_attachment(tmp_path, fixed, kind):
    path = tmp_path / ("owned fixture 測試." + kind)
    identity = uuid.uuid4().bytes_le
    library = native._library()
    structure = _Create if kind == "vhd" else _Create2
    library.CreateVirtualDisk.argtypes = [ctypes.POINTER(native._Storage), ctypes.c_wchar_p, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(structure), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p)]
    library.CreateVirtualDisk.restype = ctypes.c_uint32
    storage = native._Storage(native._DEVICES[kind], native._Guid.from_buffer_copy(native._MICROSOFT))
    parameters = structure()
    parameters.version, parameters.guid = (1 if kind == "vhd" else 2), native._Guid.from_buffer_copy(identity)
    parameters.maximum, parameters.sector = 64 * 1024 * 1024, 512
    handle = ctypes.c_void_p()
    code = library.CreateVirtualDisk(ctypes.byref(storage), str(path), 0x100000 if kind == "vhd" else 0,
                                    None, int(fixed), 0,
                                    ctypes.byref(parameters), None, ctypes.byref(handle))
    if code:
        raise ctypes.WinError(code)
    native._kernel().CloseHandle(handle)
    before = hashlib.sha256(path.read_bytes()).digest()
    disk = find_virtual_disks(scan(tmp_path).root, registrations=[]).rows[0]
    info = native.inspect_virtual_disk(disk)
    assert info.virtual_size == 64 * 1024 * 1024 and info.physical_size > 0
    assert info.subtype == (2 if fixed else 3) and not info.loaded and info.identifier == identity
    assert not info.disk.issue and info.disk.guest_used is None
    assert hashlib.sha256(path.read_bytes()).digest() == before
