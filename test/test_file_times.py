"""Optional dates preserve stable snapshots and never turn missing/stale access dates into old files."""

from contextlib import nullcontext
import csv
import os
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import file_times, snapshot
from je_file_tree.core.export import export_files_csv
from je_file_tree.core.file_times import AccessPolicy, access_policy, files_older_than
from je_file_tree.core.live_compare import Difference, verify_pair
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.snapshot import pack_snapshot, snapshot_times, stable_snapshot, unpack_snapshot


def _info(path, *, accessed=1000, created=2000):
    original = path.stat()
    fields = {key: getattr(original, key) for key in ("st_mode", "st_dev", "st_ino", "st_size", "st_nlink",
                                                    "st_mtime_ns", "st_ctime_ns", "st_ctime")}
    fields.update(st_atime=accessed, st_file_attributes=getattr(original, "st_file_attributes", 0))
    if created is not None:
        fields["st_birthtime"] = created
    return SimpleNamespace(**fields)


def test_packed_file_times_retain_stable_identity_without_node_fields_or_directory_dates(tmp_path):
    file = tmp_path / "file"
    file.write_bytes(b"owned")
    info = _info(file)
    basic, extended = pack_snapshot(info), pack_snapshot(info, file_times=True)
    assert len(extended) == len(basic) + 16
    assert unpack_snapshot(extended) == unpack_snapshot(basic) and stable_snapshot(extended) == basic
    assert snapshot_times(extended) == (1000, 2000) and snapshot_times(basic) == (None, None)
    assert len(pack_snapshot(_info(tmp_path), file_times=True)) == len(basic)
    with pytest.raises(ValueError, match="length"):
        unpack_snapshot(b"invalid")


def test_posix_ctime_is_never_birthtime_and_invalid_times_stay_unknown(tmp_path, monkeypatch):
    file = tmp_path / "file"
    file.write_bytes(b"owned")
    monkeypatch.setattr(snapshot, "sys", SimpleNamespace(platform="linux"))
    assert snapshot_times(pack_snapshot(_info(file, created=None), file_times=True)) == (1000, None)
    invalid = pack_snapshot(_info(file, accessed=float("nan"), created=-1), file_times=True)
    assert snapshot_times(invalid) == (None, None)
    monkeypatch.setattr(snapshot, "sys", SimpleNamespace(platform="win32"))
    info = _info(file, created=None)
    assert snapshot_times(pack_snapshot(info, file_times=True))[1] == info.st_ctime


def test_optional_scan_dates_reuse_stat_and_csv_has_unknown_empty_fields(tmp_path, monkeypatch):
    file = tmp_path / "file"
    file.write_bytes(b"owned")
    original, calls = snapshot.pack_snapshot, []

    def packing(info, **kwargs):
        calls.append(kwargs.get("file_times", False))
        return original(info, **kwargs)

    monkeypatch.setattr("je_file_tree.core.scanner.pack_snapshot", packing)
    root = scan(tmp_path, options=ScanOptions(file_times=True)).root
    node = root.children[0]
    assert node.accessed is not None and root.accessed is None and calls == [True]
    target = tmp_path / "dates.csv"
    export_files_csv([node, Node("unknown", False)], target)
    with target.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["accessed"] and rows[1]["accessed"] == rows[1]["created"] == ""
    assert not ScanOptions().file_times


@pytest.mark.parametrize("raw, expected", [(0, "enabled"), (1, "disabled"), (2, "enabled"), (3, "disabled"),
                                          (0x80000002, "enabled"), (0x80000003, "disabled"),
                                          (True, "unknown"), (-1, "unknown"), (4, "unknown"), ("1", "unknown")])
def test_ntfs_registry_bits_are_read_only_and_invalid_values_stay_unknown(monkeypatch, raw, expected):
    queried = []

    def key(hive, path, reserved, flags):
        queried.append((hive, path, reserved, flags))
        return nullcontext(object())

    def value(_key, name):
        assert name == "NtfsDisableLastAccessUpdate"
        return raw, 4

    fake = SimpleNamespace(HKEY_LOCAL_MACHINE=1, KEY_READ=2, REG_DWORD=4, OpenKey=key, QueryValueEx=value)
    monkeypatch.setattr(file_times, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(file_times, "winreg", fake, raising=False)
    assert access_policy().state == expected
    assert queried == [(1, r"SYSTEM\CurrentControlSet\Control\FileSystem", 0, 2)]


def test_unknown_registry_does_not_enable_access_grouping_and_nonwindows_does_not_read_it(monkeypatch):
    def denied(*_args):
        raise PermissionError("owned simulated policy error")

    monkeypatch.setattr(file_times, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(file_times, "winreg", SimpleNamespace(HKEY_LOCAL_MACHINE=1, KEY_READ=2, OpenKey=denied),
                        raising=False)
    assert access_policy().state == "unknown"
    monkeypatch.setattr(file_times, "sys", SimpleNamespace(platform="linux"))
    assert access_policy().state == "platform"


def test_bounded_age_inventory_keeps_full_counts_refuses_disabled_access_and_is_cancellable(tmp_path, monkeypatch):
    file = tmp_path / "sample"
    file.write_bytes(b"x")
    root = Node("owned", True, children=[])
    packed = pack_snapshot(_info(file), file_times=True)
    for number in range(1002):
        root.children.append(Node(str(number), False, size=number, snapshot=packed, parent=root))
    root.children.append(Node("future", False, size=99,
                              snapshot=pack_snapshot(_info(file, accessed=10**12), file_times=True), parent=root))
    root.children.append(Node("missing", False, size=99, parent=root))
    monkeypatch.setattr(file_times, "access_policy", lambda: AccessPolicy("platform"))
    monkeypatch.setattr(os, "scandir", lambda *_args: pytest.fail("Age queries must use recorded nodes only"))
    result = files_older_than(root, 1, now=100000)
    assert result.count == 1002 and result.size == sum(range(1002)) and len(result.rows) == 1000
    assert result.rows[0].size == 1001 and result.total == 1004 and result.unknown == 2
    disabled = files_older_than(root, 1, now=100000, policy=AccessPolicy("disabled"))
    assert disabled.rows == [] and disabled.unknown == disabled.total
    assert files_older_than(root, 1, clock="created", now=100000,
                            policy=AccessPolicy("disabled")).count == 1003
    root.error = "owned partial"
    assert files_older_than(root, 1, now=100000).incomplete
    cancel = threading.Event()
    monkeypatch.setattr(file_times, "give_way", cancel.set)
    assert files_older_than(root, 1, now=100000, cancel=cancel) is None


def test_content_verification_ignores_optional_access_dates_and_missing_snapshots_are_unavailable(tmp_path):
    roots = []
    for name in ("a", "b"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "file").write_bytes(b"identical")
        roots.append(scan(folder, options=ScanOptions(file_times=True)).root)
    row = Difference("file", roots[0].children[0], roots[1].children[0], "metadata")
    assert verify_pair(row).state == "identical"
    row.left.snapshot = None
    assert verify_pair(row).state == "unavailable"
