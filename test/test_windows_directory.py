"""Native directory replies preserve identities and refuse bounds, permission and boundary failures."""

from contextlib import nullcontext
import ctypes
import errno
import stat
import struct
import sys
from types import SimpleNamespace

import pytest

from je_file_tree.core import windows_directory as native
from je_file_tree.core.snapshot import Snapshot
from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot


def _row(name="卷 空白.dat", *, attributes=32, tag=0, identifier=24 | (7 << 48), following=0):
    encoded = name.encode("utf-16-le", errors="surrogatepass")
    raw = bytearray(-(-(native._HEADER.size + len(encoded)) // 8) * 8)
    native._HEADER.pack_into(raw, 0, following, 0, *(native._EPOCH + index for index in range(1, 5)),
                             7, 8, attributes, len(encoded), 0, tag, identifier.to_bytes(16, "little"))
    raw[native._HEADER.size:native._HEADER.size + len(encoded)] = encoded
    return bytes(raw)


def test_native_layout_preserves_names_full_identity_dates_and_meaningful_tags():
    value, = native._entries(_row(identifier=2**90 + 24, tag=999))
    assert native._HEADER.size == 88
    assert value == native.WindowsEntry("卷 空白.dat", 2**90 + 24, 7, 8, 32, 0, (100, 200, 300, 400))
    linked, = native._entries(_row(attributes=0x400, tag=0xA000000C))
    assert linked.reparse_tag == 0xA000000C


def test_directory_chain_skips_dot_entries_without_using_their_missing_identity():
    dot = _row(".", identifier=0)
    first = _row(".", identifier=0, following=len(dot))
    values = list(native._entries(first + _row("next.dat")))
    assert [value.name for value in values] == ["next.dat"]
    assert list(native._entries(_row("..", identifier=0))) == []


@pytest.mark.parametrize("name", ["", "a/b", "a\\b", "a:b", "a\0b", "a" * 256])
def test_unsafe_or_unbounded_native_names_refuse(name):
    with pytest.raises(ValueError):
        list(native._entries(_row(name)))


@pytest.mark.parametrize("offset,format_code,value", [(0, "I", 4), (0, "I", 65536), (0, "I", 88),
                                                    (60, "I", 0), (60, "I", 511), (40, "q", -1),
                                                    (48, "q", -1), (8, "q", -1), (72, "16s", bytes(16))])
def test_corrupt_native_offsets_and_metadata_refuse(offset, format_code, value):
    raw = bytearray(_row())
    struct.pack_into("<" + format_code, raw, offset, value)
    with pytest.raises(ValueError):
        list(native._entries(bytes(raw)))


@pytest.mark.parametrize("data", [b"", bytes(87), bytes(65537), _row()[:-20]],
                         ids=["empty", "short", "oversized", "partial"])
def test_truncated_or_oversized_native_reply_refuses(data):
    with pytest.raises(ValueError):
        list(native._entries(data))


def _api(monkeypatch, *, changed=False, attributes=16, fail=""):
    expected = Snapshot(2**60 + 1, 2**90 + 2, 0, 0, 0, stat.S_IFDIR, 16, 1)
    info = SimpleNamespace(st_dev=expected.device, st_ino=expected.inode, st_mode=stat.S_IFDIR,
                           st_file_attributes=16)
    opened, closed, queries = [], [], []
    def create(*arguments):
        opened.append(arguments)
        return ctypes.c_void_p(-1).value if fail == "open" else 123
    def query(_handle, kind, buffer, _size):
        queries.append(kind)
        if kind == 18:
            buffer.raw = struct.pack("<Q16s", expected.device, (expected.inode + changed).to_bytes(16, "little"))
        elif kind == 9:
            buffer.raw = struct.pack("<II", attributes, 0)
        elif kind == 20:
            ctypes.memmove(buffer, _row(), len(_row()))
        else:
            return False
        return fail != "query"
    def close(handle):
        closed.append(handle)
        return fail != "close"
    api = SimpleNamespace(CreateFileW=create, GetFileInformationByHandleEx=query, CloseHandle=close)
    monkeypatch.setattr(native, "_kernel", lambda: api)
    monkeypatch.setattr(native, "os", SimpleNamespace(lstat=lambda _path: info,
                                                      scandir=lambda _path: nullcontext(iter(()))))
    monkeypatch.setattr(native.ctypes, "get_last_error", lambda: 18, raising=False)
    monkeypatch.setattr(native.ctypes, "WinError", lambda number: OSError(errno.EIO, f"native failure {number}"),
                        raising=False)
    return expected, opened, closed, queries, info


def test_native_iteration_uses_metadata_only_no_follow_handle_and_owned_close(monkeypatch):
    expected, opened, closed, queries, _info = _api(monkeypatch)
    assert [entry.name for entry in native.directory_entries("owned", expected)] == ["卷 空白.dat"]
    assert opened == [("owned", 0x81, 3, None, 3, 0x02200000, None)]
    assert queries == [18, 9, 20, 19] and closed == [123]


@pytest.mark.parametrize("attributes", [0, 0x410, 0x1010, 0x40010, 0x400010])
def test_changed_or_linked_cloud_handle_scope_refuses_and_closes(monkeypatch, attributes):
    expected, _opened, closed, _queries, _info = _api(monkeypatch, attributes=attributes)
    with pytest.raises(ValueError):
        list(native.directory_entries("owned", expected))
    assert closed == [123]


def test_full_identity_change_refuses_and_closes(monkeypatch):
    expected, _opened, closed, _queries, _info = _api(monkeypatch, changed=True)
    with pytest.raises(ValueError):
        list(native.directory_entries("owned", expected))
    assert closed == [123]


@pytest.mark.parametrize("fail", ["open", "query", "close"])
def test_native_failures_stay_visible_and_only_created_handles_close(monkeypatch, fail):
    expected, _opened, closed, _queries, _info = _api(monkeypatch, fail=fail)
    with pytest.raises(OSError):
        list(native.directory_entries("owned", expected))
    assert closed == ([] if fail == "open" else [123])


def test_denied_ordinary_listing_prevents_native_handle_and_raw_authority(monkeypatch):
    expected, opened, closed, _queries, _info = _api(monkeypatch)
    def denied(_path):
        raise PermissionError("ordinary directory access denied")
    monkeypatch.setattr(native.os, "scandir", denied)
    with pytest.raises(PermissionError):
        list(native.directory_entries("owned", expected))
    assert opened == closed == []


def test_cancellation_and_explicit_iterator_close_close_only_owned_handle(monkeypatch):
    expected, _opened, closed, _queries, _info = _api(monkeypatch)
    iterator = native.directory_entries("owned", expected)
    next(iterator)
    iterator.close()
    assert closed == [123]
    checks = []
    def cancelled():
        checks.append(True)
        if len(checks) == 3:
            raise InterruptedError("cancelled")
    with pytest.raises(InterruptedError):
        list(native.directory_entries("owned", expected, check=cancelled))
    assert closed == [123, 123]


def test_changed_directory_after_native_listing_is_visible(monkeypatch):
    expected, _opened, closed, _queries, info = _api(monkeypatch)
    iterator = native.directory_entries("owned", expected)
    next(iterator)
    info.st_ino += 1
    with pytest.raises(ValueError):
        next(iterator)
    assert closed == [123]


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows directory identity validation")
def test_native_multiple_batches_match_owned_names_identifiers_sizes_and_dates(tmp_path, monkeypatch):
    expected = {}
    for index in range(600):
        path = tmp_path / f"卷 空白-{index:03}.dat"
        path.write_bytes(b"owned metadata fixture")
        expected[path.name] = path.lstat()
    kernel = native._kernel()
    queries = []
    def query(*arguments):
        queries.append(arguments[1])
        return kernel.GetFileInformationByHandleEx(*arguments)
    proxy = SimpleNamespace(CreateFileW=kernel.CreateFileW, CloseHandle=kernel.CloseHandle,
                            GetFileInformationByHandleEx=query)
    monkeypatch.setattr(native, "_kernel", lambda: proxy)
    entries = list(native.directory_entries(str(tmp_path), unpack_snapshot(stat_snapshot(str(tmp_path)))))
    assert {entry.name for entry in entries} == set(expected) and len(entries) == len(expected)
    assert queries.count(native._DIRECTORY_INFO) >= 2
    for entry in entries:
        info = expected[entry.name]
        assert (entry.file_id, entry.size, entry.times[0], entry.times[2]) == (
            info.st_ino, info.st_size, getattr(info, "st_birthtime_ns", info.st_ctime_ns), info.st_mtime_ns)
