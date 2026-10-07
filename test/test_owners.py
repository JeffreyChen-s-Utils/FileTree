"""Recorded file owners never imply descendant ownership or replace unavailable identities."""

import ctypes
import os
import stat
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import owner_id, owners
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.snapshot import pack_snapshot

_SID = b"\x01\x02\x00\x00\x00\x00\x00\x05" + (32).to_bytes(4, "little") + (544).to_bytes(4, "little")


def test_posix_capture_uses_existing_stat_and_shares_keys_without_metadata_queries(monkeypatch):
    monkeypatch.setattr(owner_id, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(owner_id.os, "lstat", lambda _path: pytest.fail("unexpected additional owner stat"))
    info = SimpleNamespace(st_mode=stat.S_IFREG, st_uid=int("12345"))
    first = owner_id.file_owner("/unused", info)
    info.st_uid = int("12345")
    assert first == 12345 and owner_id.file_owner("/unused", info) is first
    for uid in (None, True, -1):
        info.st_uid = uid
        assert owner_id.file_owner("/unused", info) is None


def test_native_posix_scan_records_uid_and_windows_default_is_unknown(sample_tree):
    root = scan(sample_tree).root
    expected = sample_tree.stat().st_uid if os.name != "nt" else None
    assert all(node.owner == expected for node in root.iter_files())
    assert all(node.owner is None for node in root.iter_nodes() if node.is_dir)


def test_windows_option_and_cloud_link_special_guards_skip_queries(monkeypatch):
    monkeypatch.setattr(owner_id, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(owner_id, "_named_owner", lambda _path: pytest.fail("ineligible owner query"))
    info = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0, st_reparse_tag=0)
    assert owner_id.file_owner("unused", info) is None
    for bit in (0x1000, 0x40000, 0x400000):
        info.st_file_attributes = bit
        assert owner_id.file_owner("unused", info, windows=True) is None
    info.st_file_attributes, info.st_reparse_tag = 0, 0xA000000C
    assert owner_id.file_owner("unused", info, windows=True) is None
    info.st_reparse_tag = 0
    for mode in (stat.S_IFDIR, stat.S_IFLNK, stat.S_IFIFO):
        info.st_mode = mode
        assert owner_id.file_owner("unused", info, windows=True) is None


def test_windows_query_rechecks_snapshot_and_denied_changed_paths_stay_unknown(sample_tree, monkeypatch):
    monkeypatch.setattr(owner_id, "sys", SimpleNamespace(platform="win32"))
    path = sample_tree / "notes.txt"
    info = path.lstat()
    monkeypatch.setattr(owner_id, "_named_owner", lambda _path: _SID)
    assert owner_id.file_owner(str(path), info, windows=True) == _SID
    path.write_bytes(b"changed")
    assert owner_id.file_owner(str(path), info, windows=True) is None
    def denied(_path):
        raise PermissionError("owner unavailable")
    monkeypatch.setattr(owner_id, "_named_owner", denied)
    assert owner_id.file_owner(str(path), info, windows=True) is None


@pytest.mark.parametrize("code,valid,length,known", [(0, True, 16, True), (5, True, 16, False),
                                                   (0, False, 16, False), (0, True, 1000, False)])
def test_native_security_descriptor_freed_on_success_and_failure(monkeypatch, code, valid, length, known):
    buffer = ctypes.create_string_buffer(_SID)
    freed, calls = [], []
    def query(path, kind, fields, sid, *outputs):
        group, dacl, sacl, descriptor = outputs
        calls.append((path, kind, fields, group, dacl, sacl))
        sid._obj.value = ctypes.addressof(buffer)
        descriptor._obj.value = 123
        return code
    api = SimpleNamespace(GetNamedSecurityInfoW=query, IsValidSid=lambda _sid: valid,
                          GetLengthSid=lambda _sid: length)
    kernel = SimpleNamespace(LocalFree=lambda pointer: freed.append(pointer.value))
    monkeypatch.setattr(owner_id, "_windows_api", lambda: (api, kernel))
    assert owner_id._named_owner("owned-fixture") == (_SID if known else None)
    assert freed == [123] and calls == [("owned-fixture", 1, 1, None, None, None)]


def test_identity_and_unresolvable_account_fallback_preserve_sid(monkeypatch):
    assert owner_id.owner_identifier(_SID) == "S-1-5-32-544"
    assert owner_id.owner_identifier(b"\x01\x00\x01\x02\x03\x04\x05\x06") == "S-1-0x010203040506"
    assert owner_id.owner_identifier(12345) == "uid:12345"
    assert owner_id.owner_identifier(None) == "" and owner_id.owner_name(None) == ""
    monkeypatch.setattr(owner_id, "sys", SimpleNamespace(platform="win32"))
    api = SimpleNamespace(LookupAccountSidW=lambda *_args: False)
    monkeypatch.setattr(owner_id, "_windows_api", lambda: (api, None))
    assert owner_id.owner_name(_SID) == "S-1-5-32-544"
    for key in (b"", b"bad", _SID[:-1], b"\x02" + _SID[1:]):
        with pytest.raises(ValueError, match="SID"):
            owner_id.owner_identifier(key)


def test_scan_capture_setting_and_metadata_failure_do_not_change_readable_coverage(sample_tree, monkeypatch):
    calls = []
    from je_file_tree.core import scanner
    def capture(path, _info, *, windows):
        calls.append((path, windows))
        return _SID if windows else None
    monkeypatch.setattr(scanner, "file_owner", capture)
    result = scan(sample_tree, options=ScanOptions(windows_owners=True, file_times=True))
    assert len(calls) == 6 and all(enabled for _path, enabled in calls)
    assert all(node.owner == _SID and node.accessed is not None for node in result.root.iter_files())
    assert result.errors == []
    result = scan(sample_tree)
    assert all(node.owner is None for node in result.root.iter_files()) and result.errors == []


def test_owner_totals_do_not_assign_directory_owner_to_children_and_include_unknown(monkeypatch):
    root = Node("root", True, owner=999, children=[])
    folder = Node("folder", True, parent=root, owner=999, children=[], error="incomplete")
    root.children.extend([folder, Node("link", False, is_link=True, size=100, owner=999)])
    folder.children.extend([Node("a", False, size=10, allocated=4096, owner=1),
                            Node("b", False, size=20, allocated=4096, owner=1),
                            Node("c", False, size=30, allocated=512, owner=2),
                            Node("d", False, size=40, allocated=8192)])
    looked_up = []
    monkeypatch.setattr(owners, "owner_name", lambda key: looked_up.append(key) or (f"owner{key}" if key else ""))
    result = owners.owner_stats(root)
    assert result.files == 4 and result.size == 100 and result.count == 3 and result.incomplete
    assert result.unknown_files == 1 and result.unknown_size == 40
    assert set(looked_up) == {None, 1, 2}
    assert sum(row.share for row in result.rows) == pytest.approx(1)
    one = next(row for row in result.rows if row.owner == 1)
    assert (one.size, one.allocated, one.files) == (30, 8192, 2)


def test_bounded_owner_rows_keep_full_counts_and_cancel_during_final_name_lookup(monkeypatch):
    root = Node("root", True, children=[Node(str(number), False, owner=number, size=number)
                                       for number in range(1002)])
    monkeypatch.setattr(owners, "owner_name", lambda key: f"owner{key}")
    result = owners.owner_stats(root)
    assert len(result.rows) == 1000 and result.count == 1002 and result.files == 1002
    assert result.size == sum(range(1002)) and result.rows[0].owner == 1001
    event = threading.Event()
    event.set()
    assert owners.owner_stats(root, cancel=event) is None
    event.clear()
    def cancel_after_name(_key):
        event.set()
        return "canceled"
    monkeypatch.setattr(owners, "owner_name", cancel_after_name)
    assert owners.owner_stats(Node("root", True, children=[Node("file", False, owner=1)]), cancel=event) is None


def test_optional_owner_slot_does_not_change_operation_snapshot(sample_tree):
    result = scan(sample_tree, options=ScanOptions(windows_owners=True)).root
    node = next(result.iter_files())
    assert node.snapshot == pack_snapshot(os.lstat(node.path))
