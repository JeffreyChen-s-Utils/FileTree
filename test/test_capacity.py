"""Ledger reconciliation rejects incomplete coverage, missing identities and foreign allocation."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from je_file_tree.core import capacity, scanner
from je_file_tree.core.capacity import capacity_ledger
from je_file_tree.core.scanner import EXCLUDED, NOT_SCANNED, ScanOptions, scan
from je_file_tree.core.snapshot import pack_snapshot, unpack_snapshot


def _volume(monkeypatch: pytest.MonkeyPatch, used: int = 65536) -> None:
    monkeypatch.setattr(capacity.os.path, "ismount", lambda _path: True)
    monkeypatch.setattr(capacity.shutil, "disk_usage", lambda _path: SimpleNamespace(
        total=131072, used=used, free=32768))


def test_real_hard_links_and_folder_scope_use_os_capacity(tmp_path: Path) -> None:
    first = tmp_path / "first"
    first.write_bytes(b"data" * 4096)
    os.link(first, tmp_path / "second")
    root = scan(tmp_path).root
    ledger = capacity_ledger(root)
    assert ledger.status == "folder_only" and ledger.unaccounted is None
    assert ledger.named_allocated == root.allocated
    assert ledger.unique_allocated == root.children[0].allocated
    assert ledger.hard_link_overcount == root.children[0].allocated
    assert ledger.total is not None and ledger.free is not None
    assert ledger.metadata_bytes is None and ledger.omitted_bytes is None and ledger.other_volumes_bytes is None


def test_whole_volume_estimate_preserves_the_unaccounted_remainder(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "file").write_bytes(b"data" * 4096)
    root = scan(tmp_path).root
    _volume(monkeypatch)
    ledger = capacity_ledger(root)
    assert ledger.status == "estimated"
    assert ledger.unaccounted == ledger.used - ledger.unique_allocated
    assert ledger.unavailable_free == 32768
    assert ledger.unique_allocated + ledger.unaccounted == ledger.used


@pytest.mark.parametrize("error", [EXCLUDED, NOT_SCANNED, "access denied"])
def test_partial_branches_cannot_reconcile(tmp_path: Path, monkeypatch, error: str) -> None:
    (tmp_path / "unseen").mkdir()
    root = scan(tmp_path).root
    root.children[0].error = error
    _volume(monkeypatch)
    ledger = capacity_ledger(root)
    assert ledger.status == "incomplete" and ledger.unaccounted is None
    assert not ledger.coverage.complete and ledger.omitted_bytes is None


def test_missing_identity_stopped_scan_and_overestimate_are_explicit(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "file").write_bytes(b"data" * 4096)
    root = scan(tmp_path).root
    _volume(monkeypatch)
    assert capacity_ledger(root, partial=True).status == "incomplete"
    snapshot = root.children[0].snapshot
    root.children[0].snapshot = None
    unknown = capacity_ledger(root)
    assert unknown.status == "identity_unknown"
    assert unknown.unique_allocated is None and unknown.hard_link_overcount is None
    root.children[0].snapshot = snapshot
    _volume(monkeypatch, used=1)
    ledger = capacity_ledger(root)
    assert ledger.status == "allocation_exceeds_used" and ledger.unaccounted is None


def test_recycle_bin_is_an_included_subset_not_extra_used_space(tmp_path: Path, monkeypatch) -> None:
    name = "$Recycle.Bin" if os.name == "nt" else ".Trash-1000"
    bin_folder = tmp_path / name
    bin_folder.mkdir()
    first = bin_folder / "file"
    first.write_bytes(b"data" * 4096)
    os.link(first, tmp_path / "alias")
    (tmp_path / "Trash").mkdir()
    (tmp_path / "Trash" / "authored").write_bytes(b"x" * 4096)
    root = scan(tmp_path).root
    _volume(monkeypatch)
    ledger = capacity_ledger(root)
    bin_node = next(child for child in root.children if child.name == name)
    assert ledger.recycle_bin_seen == bin_node.allocated
    assert ledger.recycle_bin_complete
    assert ledger.unique_allocated == bin_node.allocated + 4096
    bin_node.error = EXCLUDED
    assert not capacity_ledger(root).recycle_bin_complete


def test_capacity_failure_or_replaced_root_never_produces_a_remainder(tmp_path: Path, monkeypatch) -> None:
    root = scan(tmp_path).root
    _volume(monkeypatch)
    replacement = tmp_path / "new"
    replacement.mkdir()
    monkeypatch.setattr(capacity, "stat_snapshot", lambda _path: pack_snapshot(replacement.stat()))
    assert capacity_ledger(root).status == "root_changed"

    def denied(_path):
        raise PermissionError("capacity denied")

    monkeypatch.setattr(capacity.shutil, "disk_usage", denied)
    ledger = capacity_ledger(root)
    assert ledger.status == "capacity_unavailable" and ledger.total is None and ledger.unaccounted is None


def test_different_device_mount_is_listed_without_reading_its_contents(tmp_path: Path, monkeypatch) -> None:
    mounted = tmp_path / "mounted"
    mounted.mkdir()
    (mounted / "foreign").write_bytes(b"data" * 4096)
    inode = mounted.stat().st_ino
    original = scanner.pack_snapshot

    def mounted_info(info):
        values = {name: getattr(info, name) for name in ("st_dev", "st_ino", "st_size", "st_mode", "st_mtime_ns",
                                                       "st_ctime_ns", "st_nlink")}
        if info.st_ino == inode:
            values["st_dev"] += 1
        return original(SimpleNamespace(**values))

    monkeypatch.setattr(scanner, "pack_snapshot", mounted_info)
    root = scan(tmp_path, options=ScanOptions(workers=1)).root
    mount = root.children[0]
    assert mount.is_dir and mount.is_link and not mount.children and root.file_count == 0
    assert unpack_snapshot(mount.snapshot).device != unpack_snapshot(root.snapshot).device
    ledger = capacity_ledger(root)
    assert ledger.mounted_folders == 1 and ledger.other_volumes_bytes is None
    assert ledger.unique_allocated == 0
