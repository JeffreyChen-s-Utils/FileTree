"""Opted-in allocation uses a no-follow metadata handle with full Windows identity and close ownership."""

import ctypes
from types import SimpleNamespace

import pytest

from je_file_tree.core import allocation, windows_allocation as native
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.gui.scan_worker import ScanWorker
from test_gui import window as window  # noqa: PLC0414


def _api(monkeypatch, *, fail="", attributes=32, changed=False, allocated=4096, pending=False):
    expected = SimpleNamespace(st_dev=2**60 + 1, st_ino=2**90 + 2, st_size=5000, st_mtime_ns=1000)
    closed, opened = [], []
    def create(*args):
        opened.append(args)
        return ctypes.c_void_p(-1).value if fail == "open" else 123
    def identity(_handle, pointer):
        row = pointer._obj
        row.attributes, row.size_low = attributes, 5000
        ticks = native._UNIX_EPOCH + 10
        row.modified[0], row.modified[1] = ticks & 0xffffffff, ticks >> 32
        return fail != "metadata"
    def extended(_handle, kind, pointer, _size):
        row = pointer._obj
        if kind == 18:
            row.device = expected.st_dev
            row.inode[:] = (expected.st_ino + changed).to_bytes(16, "little")
            return fail != "id"
        assert kind == 1
        row.allocation, row.eof, row.pending = allocated, expected.st_size, pending
        return fail != "allocation"
    api = SimpleNamespace(CreateFileW=create, GetFileInformationByHandle=identity,
                          GetFileInformationByHandleEx=extended, CloseHandle=closed.append)
    monkeypatch.setattr(native, "_kernel", lambda: api)
    return expected, opened, closed


@pytest.mark.parametrize("fail", ("open", "metadata", "id", "allocation"))
def test_failures_remain_unknown_and_successful_handles_always_close(monkeypatch, fail):
    expected, opened, closed = _api(monkeypatch, fail=fail)
    assert native.file_allocation("owned-file", expected) is None
    assert closed == ([] if fail == "open" else [123])
    assert opened == [("owned-file", 0x80, 7, None, 3, 0x02200000, None)]


@pytest.mark.parametrize("fields", ({"changed": True}, {"attributes": 0x400}, {"attributes": 0x1000},
                                    {"attributes": 0x10}, {"allocated": -1}, {"pending": True}))
def test_changed_link_cloud_directory_or_invalid_results_are_unknown(monkeypatch, fields):
    expected, _opened, closed = _api(monkeypatch, **fields)
    assert native.file_allocation("owned-file", expected) is None and closed == [123]


def test_valid_full_identity_allocation_and_native_structure_layout(monkeypatch):
    expected, _opened, closed = _api(monkeypatch)
    assert native.file_allocation("owned-file", expected) == 4096 and closed == [123]
    assert ctypes.sizeof(native._Standard) == 24 and ctypes.sizeof(native._FileID) == 24
    assert ctypes.sizeof(native._Identity) == 52


def test_legacy_python_stat_identity_is_accepted_only_on_legacy_runtime(monkeypatch):
    info, file_id = native._Identity(), native._FileID()
    info.attributes, info.size_low, info.device, info.inode_low = 32, 5000, 1, 2
    ticks = native._UNIX_EPOCH + 10
    info.modified[0], info.modified[1] = ticks & 0xffffffff, ticks >> 32
    file_id.device, file_id.inode[:] = 2**60 + 1, (2**90 + 2).to_bytes(16, "little")
    expected = SimpleNamespace(st_dev=1, st_ino=2, st_size=5000, st_mtime_ns=1000)
    monkeypatch.setattr(native, "sys", SimpleNamespace(version_info=(3, 11)))
    assert native._matches(info, file_id, expected)
    monkeypatch.setattr(native, "sys", SimpleNamespace(version_info=(3, 12)))
    assert not native._matches(info, file_id, expected)


def test_exact_rule_measures_unflagged_wof_and_keeps_cloud_data_unqueried(monkeypatch):
    calls = []
    monkeypatch.setattr(allocation, "file_allocation", lambda path, _info: calls.append(path) or 73728)
    rule = allocation.windows_allocation(4096, exact=True)
    entry = SimpleNamespace(path="owned-wof")
    info = SimpleNamespace(st_size=2097152, st_file_attributes=32)
    assert rule(entry, info) == 73728 and calls == ["owned-wof"]
    info.st_file_attributes = 0x400000
    assert rule(entry, info) == 0 and calls == ["owned-wof"]
    info.st_file_attributes = 32
    monkeypatch.setattr(allocation, "file_allocation", lambda *_args: None)
    assert rule(entry, info) == 2097152


def test_scan_option_reaches_allocation_factory_and_running_worker_options_are_stable(
        window, sample_tree, monkeypatch):
    from je_file_tree.core import scanner
    calls = []
    def factory(_root, **kwargs):
        calls.append(kwargs)
        return lambda _entry, _info: 123
    monkeypatch.setattr(scanner, "allocation_for", factory)
    result = scan(sample_tree, options=ScanOptions(exact_windows_allocation=True))
    assert calls == [{"exact_windows": True}] and result.root.allocated == 123 * 6
    assert not window._scan_options().exact_windows_allocation
    original = window._scan_options()
    worker = ScanWorker("unstarted-owned", original, window)
    window._worker = worker
    try:
        window._actions["exact_allocation"].setChecked(True)
        assert window._scan_options().exact_windows_allocation and not worker._options.exact_windows_allocation
        assert str(window.settings.value("exact_allocation")).lower() == "true"
    finally:
        window._worker = None
        worker.deleteLater()
