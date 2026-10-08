"""Scan/review/replacement races are skipped rather than moving new content at an old name."""

from __future__ import annotations

import os
import sys
import threading
from types import SimpleNamespace
from pathlib import Path

import pytest

from je_file_tree.core.node import Node
from je_file_tree.core import operations
from je_file_tree.core.operations import move_batch, revalidate
from je_file_tree.core.protected import PROGRAMS, Protection
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.snapshot import pack_snapshot, unpack_snapshot


def test_replaced_same_size_same_timestamp_file_is_skipped(tmp_path: Path) -> None:
    file = tmp_path / "selected.txt"
    file.write_bytes(b"old")
    root = scan(tmp_path).root
    node = root.children[0]
    info = file.stat()
    file.rename(tmp_path / "old.txt")
    file.write_bytes(b"new")
    os.utime(file, ns=(info.st_atime_ns, info.st_mtime_ns))
    moved = []
    result = move_batch(root, [node], lambda path: moved.append(path) or True)
    assert result.skipped == [(node, "identity")]
    assert moved == [] and file.read_bytes() == b"new"


def test_optional_boundary_veto_cannot_replace_source_revalidation(tmp_path: Path) -> None:
    file = tmp_path / "owned.bin"
    file.write_bytes(b"owned")
    root = scan(tmp_path).root
    node = root.children[0]
    moved = []
    result = move_batch(root, [node], lambda path: moved.append(path) or True,
                        before_move=lambda _node: "recycle_capacity")
    assert result.skipped == [(node, "recycle_capacity")] and not moved and file.read_bytes() == b"owned"
    def changed(_node):
        file.write_bytes(b"changed after source validation")
    result = move_batch(root, [node], lambda path: moved.append(path) or True, before_move=changed)
    assert result.skipped == [(node, "changed")] and not moved


def test_cancel_during_boundary_veto_skips_unstarted_mover(tmp_path: Path) -> None:
    file = tmp_path / "owned.bin"
    file.write_bytes(b"owned")
    root = scan(tmp_path).root
    cancel = threading.Event()
    def boundary(_node):
        cancel.set()
    moved = []
    result = move_batch(root, root.children, lambda path: moved.append(path) or True,
                        before_move=boundary, cancel=cancel)
    assert result.skipped == [(root.children[0], "cancelled")] and not moved
    assert file.read_bytes() == b"owned"


@pytest.mark.parametrize("change,reason", [("resize", "changed"), ("missing", "missing"), ("folder", "kind")])
def test_changed_kind_size_and_missing_files(tmp_path: Path, change: str, reason: str) -> None:
    file = tmp_path / "selected.txt"
    file.write_bytes(b"old")
    root = scan(tmp_path).root
    node = root.children[0]
    if change == "resize":
        file.write_bytes(b"much longer")
    else:
        file.unlink()
        if change == "folder":
            file.mkdir()
    assert revalidate(node, root) == reason


def test_directory_validation_checks_deep_content_and_new_names(tmp_path: Path) -> None:
    folder = tmp_path / "selected"
    nested = folder / "nested"
    nested.mkdir(parents=True)
    file = nested / "file"
    file.write_bytes(b"old")
    root = scan(tmp_path).root
    node = root.children[0]
    assert revalidate(node, root) is None
    file.write_bytes(b"changed")
    assert revalidate(node, root) == "changed"
    root = scan(tmp_path).root
    (nested / "new").write_bytes(b"unreviewed")
    assert revalidate(root.children[0], root) == "changed"


def test_partial_folder_and_unverified_nodes_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "cache" / "skipped").mkdir(parents=True)
    root = scan(tmp_path, options=ScanOptions(exclude=("skipped",))).root
    assert revalidate(root.children[0], root) == "incomplete"
    node = Node("unknown", False, parent=root)
    assert revalidate(node, root) == "unverified"
    assert revalidate(root, root) == "outside"


def test_mixed_batch_keeps_failed_and_newly_protected_entries(tmp_path: Path) -> None:
    for name in ("safe", "failed", "guarded"):
        (tmp_path / name).write_bytes(b"data")
    root = scan(tmp_path).root
    by_name = {node.name: node for node in root.children}
    guard = Protection(str(tmp_path / "guarded"), PROGRAMS)
    result = move_batch(root, list(by_name.values()), lambda path: not path.endswith("failed"), places=[guard])
    assert result.moved == [by_name["safe"]]
    assert result.failed == [by_name["failed"]]
    assert result.skipped == [(by_name["guarded"], "protected")]
    assert by_name["failed"].is_in(root)
    assert revalidate(by_name["guarded"], root, places=[guard], approved=guard) is None


def test_cancellation_and_unreadable_entries_are_skipped(tmp_path: Path, monkeypatch) -> None:
    file = tmp_path / "file"
    file.write_bytes(b"data")
    root = scan(tmp_path).root
    node = root.children[0]
    cancel = threading.Event()
    cancel.set()
    assert revalidate(node, root, cancel=cancel) == "cancelled"
    real = os.lstat

    def denied(path):
        if path == node.path:
            raise PermissionError("locked")
        return real(path)

    monkeypatch.setattr(os, "lstat", denied)
    assert revalidate(node, root) == "unreadable"


def test_snapshot_keeps_real_identity_and_link_count(tmp_path: Path) -> None:
    file = tmp_path / "file"
    file.write_bytes(b"data")
    os.link(file, tmp_path / "second")
    root = scan(tmp_path).root
    first, second = [unpack_snapshot(node.snapshot) for node in root.children]
    assert first.identity == second.identity
    assert first.inode != 0 and first.links == 2


@pytest.mark.parametrize("field", ["attributes", "links"])
def test_new_cloud_state_or_link_count_invalidates_unchanged_content_metadata(tmp_path, monkeypatch, field):
    file = tmp_path / "file"
    file.write_bytes(b"data")
    root = scan(tmp_path).root
    node = root.children[0]
    before = unpack_snapshot(node.snapshot)
    current = SimpleNamespace(st_dev=before.device, st_ino=before.inode, st_size=before.size,
                              st_mode=before.mode, st_mtime_ns=before.modified_ns, st_ctime_ns=before.changed_ns,
                              st_file_attributes=before.attributes, st_nlink=before.links)
    if field == "attributes":
        current.st_file_attributes |= 0x1000
    else:
        current.st_nlink += 1
    original = operations.stat_snapshot
    monkeypatch.setattr(operations, "stat_snapshot",
                        lambda path: pack_snapshot(current) if path == node.path else original(path))
    assert revalidate(node, root) == "changed"


def test_snapshot_supports_filetime_epochs_and_128_bit_file_ids() -> None:
    info = SimpleNamespace(st_dev=1, st_ino=(1 << 127) + 1, st_size=0, st_mode=0o100644,
                           st_mtime_ns=-11_644_473_600 * 1_000_000_000,
                           st_ctime_ns=20_000_000_000 * 1_000_000_000, st_nlink=1)
    snapshot = unpack_snapshot(pack_snapshot(info))
    assert snapshot.inode == info.st_ino
    assert snapshot.modified_ns == info.st_mtime_ns
    assert snapshot.changed_ns == info.st_ctime_ns


def test_a_parent_replaced_by_a_link_is_never_followed(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "file").write_bytes(b"old")
    root = scan(tmp_path).root
    node = root.children[0].children[0]
    parent.rename(tmp_path / "original")
    other = tmp_path / "other"
    other.mkdir()
    (other / "file").write_bytes(b"new")
    try:
        if sys.platform == "win32":
            import _winapi

            _winapi.CreateJunction(str(other), str(parent))
        else:
            parent.symlink_to(other, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {error}")
    assert revalidate(node, root) == "link"
    assert (other / "file").read_bytes() == b"new"


def test_cancelling_after_one_move_skips_the_rest(tmp_path: Path) -> None:
    for name in ("first", "second"):
        (tmp_path / name).write_bytes(b"content")
    root = scan(tmp_path).root
    cancel = threading.Event()

    def moved(_path):
        cancel.set()
        return True

    result = move_batch(root, root.children, moved, cancel=cancel)
    assert len(result.moved) == 1
    assert result.skipped == [(root.children[1], "cancelled")]


def test_move_boundary_rechecks_after_the_potentially_long_validation_walk(tmp_path: Path, monkeypatch) -> None:
    file = tmp_path / "file"
    file.write_bytes(b"old")
    root = scan(tmp_path).root
    node = root.children[0]
    original = operations._check_subtree

    def replace_after_walk(entry, cancel, overrides=None):
        reason = original(entry, cancel, overrides)
        file.rename(tmp_path / "old")
        file.write_bytes(b"new")
        return reason

    monkeypatch.setattr(operations, "_check_subtree", replace_after_walk)
    moved = []
    result = move_batch(root, [node], lambda path: moved.append(path) or True)
    assert result.skipped == [(node, "identity")]
    assert moved == [] and file.read_bytes() == b"new"
