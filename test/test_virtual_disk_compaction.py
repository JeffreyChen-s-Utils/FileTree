"""Compaction refuses stale reviews and preserves actual native success/unknown observations."""

from contextlib import contextmanager, nullcontext
import ctypes
from dataclasses import replace
import os
import threading
from types import SimpleNamespace
import uuid

import pytest

from je_file_tree.core import virtual_disk_compaction as compact
from je_file_tree.core import virtual_disk_info as native
from je_file_tree.core import virtual_disk_runtime as runtime
from je_file_tree.core.no_replace import directory_stamps
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import stat_snapshot
from je_file_tree.core.virtual_disk_sources import DiskRegistration, DiskRegistrations
from je_file_tree.core.virtual_disks import find_virtual_disks


def _plan(tmp_path, monkeypatch):
    (tmp_path / "owned.vhd").write_bytes(b"Owned fixture, never a real user disk")
    disk = find_virtual_disks(scan(tmp_path).root, registrations=[]).rows[0]
    info = native.VirtualDiskInfo(disk, directory_stamps(str(tmp_path)), 67108864, 8192, 3, False,
                                  uuid.uuid4().bytes_le)
    stopped = runtime.DiskRuntime(())
    monkeypatch.setattr(compact, "os", SimpleNamespace(name="nt", path=os.path, lstat=os.lstat))
    monkeypatch.setattr(compact, "file_system", lambda _path: "NTFS")
    monkeypatch.setattr(compact, "protected_places", lambda: [])
    monkeypatch.setattr(compact, "system_file", lambda _path: None)
    monkeypatch.setattr(compact, "_pinned_path", lambda _path: nullcontext())
    monkeypatch.setattr(compact, "anchored_directory", lambda _parents: nullcontext())
    monkeypatch.setattr(compact, "stopped_runtime", lambda *_args, **_kwargs: stopped)
    monkeypatch.setattr(compact, "inspect_virtual_disk", lambda *_args, **_kwargs: info)
    monkeypatch.setattr(compact, "file_allocation", lambda *_args: 8192)
    monkeypatch.setattr(compact.ctypes, "WinError", lambda code: OSError(code, "native compact failure"),
                        raising=False)
    calls = []
    def execute(handle, flags, parameters, overlapped):
        assert handle.value == 123 and flags == 0 and overlapped is None
        assert parameters._obj.version == 1 and parameters._obj.reserved == 0
        calls.append("compact")
        return 0
    library = SimpleNamespace(CompactVirtualDisk=execute)
    @contextmanager
    def opened(_disk):
        calls.append("write_open")
        try:
            yield library, ctypes.c_void_p(123)
        finally:
            calls.append("closed")
    monkeypatch.setattr(compact, "_writable", opened)
    monkeypatch.setattr(compact, "_same_header", lambda *_args: calls.append("verified"))
    return compact.prepare_compaction(disk), calls, library


def test_fixed_compact_and_process_abi():
    assert ctypes.sizeof(compact._Compact) == 8 and compact._Compact.reserved.offset == 4
    assert runtime._Process.name.offset == (44 if ctypes.sizeof(ctypes.c_void_p) == 8 else 36)
    assert ctypes.sizeof(runtime._Process) == (568 if ctypes.sizeof(ctypes.c_void_p) == 8 else 556)


def test_zero_saving_is_success_and_no_attachment_or_shell(tmp_path, monkeypatch):
    plan, calls, _library = _plan(tmp_path, monkeypatch)
    before = stat_snapshot(plan.info.disk.path)
    result = compact.execute_compaction(plan, machine_stopped=True)
    assert result == compact.CompactionOutcome(True, True, 8192, 8192)
    assert calls == ["write_open", "verified", "compact", "verified", "closed"]
    assert stat_snapshot(plan.info.disk.path) == before


@pytest.mark.parametrize("change", ["confirmation", "cancel", "file", "header", "runtime", "fixed",
                                   "differencing", "loaded", "uuid", "unsupported", "unknown", "hardlink"])
def test_refusal_never_opens_writable_handle(tmp_path, monkeypatch, change):
    plan, calls, _library = _plan(tmp_path, monkeypatch)
    cancel = threading.Event()
    approved = True
    if change == "confirmation":
        approved = False
    elif change == "cancel":
        cancel.set()
    elif change == "file":
        with open(plan.info.disk.path, "ab") as stream:
            stream.write(b"changed")
    elif change == "header":
        monkeypatch.setattr(compact, "inspect_virtual_disk", lambda *_args, **_kwargs:
                            replace(plan.info, physical_size=999))
    elif change == "runtime":
        monkeypatch.setattr(compact, "stopped_runtime", lambda *_args, **_kwargs:
                            runtime.DiskRuntime((("wsl", "changed", "changed"),)))
    elif change in ("fixed", "differencing"):
        plan = replace(plan, info=replace(plan.info, subtype=2 if change == "fixed" else 4))
    elif change == "loaded":
        plan = replace(plan, info=replace(plan.info, loaded=True))
    elif change == "uuid":
        plan = replace(plan, info=replace(plan.info, identifier=None))
    elif change in ("unsupported", "unknown"):
        disk = replace(plan.info.disk, kind="qcow2") if change == "unsupported" else replace(
            plan.info.disk, snapshot=None)
        plan = replace(plan, info=replace(plan.info, disk=disk))
    else:
        os.link(plan.info.disk.path, tmp_path / "arrived alias")
    result = compact.execute_compaction(plan, machine_stopped=approved, cancel=cancel)
    assert not result.attempted and not result.compacted and result.error and not calls


def test_native_failure_and_later_observation_failure_keep_actual_outcomes(tmp_path, monkeypatch):
    plan, calls, library = _plan(tmp_path, monkeypatch)
    library.CompactVirtualDisk = lambda *_args: 5
    result = compact.execute_compaction(plan, machine_stopped=True)
    assert result.attempted and not result.compacted and result.after is None and result.error
    assert calls[-1] == "closed"
    def succeed(*_args):
        monkeypatch.setattr(compact, "file_allocation", lambda *_args: None)
        return 0
    library.CompactVirtualDisk = succeed
    result = compact.execute_compaction(plan, machine_stopped=True)
    assert result.compacted and result.before == 8192 and result.after is None and result.error
    assert calls[-1] == "closed"


def test_active_call_cancellation_cannot_hide_completed_native_work(tmp_path, monkeypatch):
    plan, calls, library = _plan(tmp_path, monkeypatch)
    cancel = threading.Event()
    def complete(*_args):
        cancel.set()
        return 0
    library.CompactVirtualDisk = complete
    result = compact.execute_compaction(plan, machine_stopped=True, cancel=cancel)
    assert cancel.is_set() and result.compacted and result.after == 8192 and not result.error
    assert calls[-1] == "closed"


def test_same_writable_handle_rechecks_every_native_authority(tmp_path, monkeypatch):
    original = compact._same_header
    plan, _calls, _library = _plan(tmp_path, monkeypatch)
    values = {6: native._Storage(2, native._Guid.from_buffer_copy(native._MICROSOFT)),
              2: native._Guid.from_buffer_copy(plan.info.identifier), 7: 3, 13: 0,
              1: native._Size(plan.info.virtual_size, 8192, 2097152, 512)}
    def query(_library, _handle, version):
        field = {6: "storage", 2: "guid", 7: "subtype", 13: "loaded", 1: "size"}[version]
        return SimpleNamespace(value=SimpleNamespace(**{field: values[version]}))
    monkeypatch.setattr(compact, "_query", query)
    original(None, None, plan.info)
    for version, invalid in ((2, native._Guid()), (7, 4), (13, 1),
                             (1, native._Size(123, 8192, 2097152, 512))):
        prior = values[version]
        values[version] = invalid
        with pytest.raises(ValueError):
            original(None, None, plan.info)
        values[version] = prior


def test_wsl_decoding_limits_and_literal_names():
    assert runtime._decode_running("\ufeff測試 distro\r\n".encode("utf-16-le")) == ("測試 distro",)
    assert runtime._decode_running(b"name\n") == ("name",)
    assert runtime._decode_running(b"\r\n") == ()
    with pytest.raises(ValueError):
        runtime._decode_running(b"x" * 65537)
    with pytest.raises(ValueError):
        runtime._decode_running(b"bad\x01name")


@pytest.mark.parametrize("change", ["incomplete", "missing", "docker", "wsl", "changed", "cancel"])
def test_runtime_unknown_or_running_is_never_stopped_proof(tmp_path, monkeypatch, change):
    plan, _calls, _library = _plan(tmp_path, monkeypatch)
    disk = replace(plan.info.disk, source="wsl", name="owned", distro="owned")
    registration = DiskRegistration("owned", disk.path, "wsl", "owned")
    registrations = DiskRegistrations((registration,))
    monkeypatch.setattr(runtime, "os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr(runtime, "registered_disks", lambda **_kwargs: registrations)
    monkeypatch.setattr(runtime, "_process_names", lambda _cancel: set())
    monkeypatch.setattr(runtime, "_running_wsl", lambda *_args: ())
    cancel = threading.Event()
    if change == "incomplete":
        registrations = DiskRegistrations((registration,), 1)
    elif change == "missing":
        registrations = DiskRegistrations(())
    elif change == "changed":
        registrations = DiskRegistrations((replace(registration, distro="other"),))
    elif change == "docker":
        monkeypatch.setattr(runtime, "_process_names", lambda _cancel: {"com.docker.backend.exe"})
    elif change == "wsl":
        monkeypatch.setattr(runtime, "_running_wsl", lambda *_args: ("some other guest",))
    else:
        cancel.set()
    with pytest.raises((OSError, ValueError)):
        runtime.stopped_runtime(disk, cancel=cancel)


def test_stopped_runtime_records_exact_registration_without_starting_guest(tmp_path, monkeypatch):
    plan, _calls, _library = _plan(tmp_path, monkeypatch)
    disk = replace(plan.info.disk, source="wsl", name="owned", distro="owned")
    monkeypatch.setattr(runtime, "os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr(runtime, "registered_disks", lambda **_kwargs: DiskRegistrations((
        DiskRegistration("owned", disk.path, "wsl", "owned"),)))
    monkeypatch.setattr(runtime, "_process_names", lambda _cancel: set())
    monkeypatch.setattr(runtime, "_running_wsl", lambda required, _cancel: () if required else pytest.fail())
    assert runtime.stopped_runtime(disk).registration == (("wsl", "owned", "owned"),)


@pytest.mark.skipif(os.name != "nt", reason="Native Windows zero-block compaction required")
def test_native_owned_blank_dynamic_vhdx_has_valid_zero_saving_without_attachment(tmp_path, monkeypatch):
    from tools.windows_owned_volume import _Create
    path, identity = tmp_path / "owned native 測試.vhdx", uuid.uuid4().bytes_le
    library = native._library()
    library.CreateVirtualDisk.argtypes = [ctypes.POINTER(native._Storage), ctypes.c_wchar_p, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(_Create), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p)]
    library.CreateVirtualDisk.restype = ctypes.c_uint32
    parameters = _Create()
    parameters.version, parameters.guid = 2, native._Guid.from_buffer_copy(identity)
    parameters.maximum, parameters.sector = 67108864, 512
    storage = native._Storage(3, native._Guid.from_buffer_copy(native._MICROSOFT))
    handle = ctypes.c_void_p()
    code = library.CreateVirtualDisk(ctypes.byref(storage), str(path), 0, None, 0, 0,
                                    ctypes.byref(parameters), None, ctypes.byref(handle))
    if code:
        raise ctypes.WinError(code)
    native._kernel().CloseHandle(handle)
    # This disk was just created by this test and never attached/assigned to any machine. Isolate
    # unrelated host guests; runtime denial is tested separately without stopping user machines.
    monkeypatch.setattr(compact, "stopped_runtime", lambda *_args, **_kwargs: runtime.DiskRuntime(()))
    disk = find_virtual_disks(scan(tmp_path).root, registrations=[]).rows[0]
    before = stat_snapshot(path)
    plan = compact.prepare_compaction(disk)
    (tmp_path / "unrelated arrival.txt").write_bytes(b"must remain unchanged")
    result = compact.execute_compaction(plan, machine_stopped=True)
    assert result.compacted and not result.error and result.before == result.after
    fresh = find_virtual_disks(scan(tmp_path).root, registrations=[]).rows[0]
    info = native.inspect_virtual_disk(fresh)
    assert info.identifier == identity and info.dynamic and not info.loaded and info.virtual_size == 67108864
    assert (tmp_path / "unrelated arrival.txt").read_bytes() == b"must remain unchanged"
    from je_file_tree.core.snapshot import unpack_snapshot
    assert unpack_snapshot(before).identity == unpack_snapshot(stat_snapshot(path)).identity


def test_native_process_snapshot_detects_names_and_refuses_incomplete_listing(monkeypatch):
    closed, names, error = [], ["Python.exe", "com.docker.backend.exe"], [18]
    def entry(_handle, pointer):
        if not names:
            return 0
        raw = names.pop(0).encode("utf-16-le")
        ctypes.memmove(ctypes.addressof(pointer._obj) + runtime._Process.name.offset, raw + b"\0\0", len(raw) + 2)
        return 1
    kernel = SimpleNamespace(CreateToolhelp32Snapshot=lambda *_args: 123,
                             Process32FirstW=entry, Process32NextW=entry,
                             CloseHandle=closed.append)
    monkeypatch.setattr(runtime, "_kernel", lambda: kernel)
    monkeypatch.setattr(runtime.ctypes, "get_last_error", lambda: error[0], raising=False)
    monkeypatch.setattr(runtime.ctypes, "WinError", lambda code: OSError(code, "incomplete processes"), raising=False)
    assert runtime._process_names(None) == {"python.exe", "com.docker.backend.exe"}
    assert closed == [123]
    error[0] = 5
    with pytest.raises(OSError):
        runtime._process_names(None)
    assert closed == [123, 123]


def test_running_wsl_uses_only_fixed_metadata_arguments_and_refuses_failure(monkeypatch, tmp_path):
    program = tmp_path / "fixed wsl.exe"
    program.write_bytes(b"owned executable path fixture; never run")
    calls = []
    monkeypatch.setattr(runtime, "_wsl_program", lambda: str(program))
    monkeypatch.setattr(runtime.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    def run(arguments, **kwargs):
        calls.append(arguments)
        assert kwargs["timeout"] == 10 and kwargs["check"] is False
        kwargs["stdout"].write("測試 guest\r\n".encode("utf-16-le"))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runtime.subprocess, "run", run)
    assert runtime._running_wsl(True, None) == ("測試 guest",)
    assert calls == [[str(program), "--list", "--running", "--quiet"]]
    assert runtime._running_wsl(False, None) == () and len(calls) == 1
    monkeypatch.setattr(runtime.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1))
    with pytest.raises(ValueError, match="unknown"):
        runtime._running_wsl(True, None)
