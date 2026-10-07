"""Verified exclusive folder copies preserve originals and expose partial destinations."""

from pathlib import Path
import os
import threading
import sys

import pytest

from je_file_tree.core import verified_copy as copies
from je_file_tree.core import copy_io
from je_file_tree.core.scanner import scan


def _fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(copies, "protected_places", lambda: ())
    source, target = tmp_path.resolve() / "source", tmp_path.resolve() / "target"
    (source / "folder" / "nested").mkdir(parents=True)
    (source / "folder" / "empty").mkdir()
    target.mkdir()
    (source / "folder" / "one").write_bytes(b"one")
    (source / "folder" / "nested" / "two").write_bytes(b"two")
    root = scan(source).root
    plan = copies.prepare_copy(root, root.children, str(target))
    assert all(not item.reason for item in plan.items)
    return plan, source, target


def test_native_copy_verification_preserves_original_and_empty_folders(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    progress = []
    result = copies.copy_folders(plan, progress=lambda *args: progress.append(args))
    assert not result.failed and len(result.verified) == 1
    assert result.verified[0].files == 2 and result.verified[0].bytes == 6
    assert (target / "folder" / "empty").is_dir() and len(progress) == 2
    assert (source / "folder" / "one").read_bytes() == (target / "folder" / "one").read_bytes() == b"one"
    copies.verify_copy(result.verified[0])


def test_existing_or_arriving_destination_is_never_overwritten(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    (target / "folder").mkdir()
    (target / "folder" / "existing").write_bytes(b"retained")
    result = copies.copy_folders(plan)
    assert len(result.failed) == 1 and not result.verified and not result.partial
    assert (target / "folder" / "existing").read_bytes() == b"retained"
    assert (source / "folder" / "one").read_bytes() == b"one"
    preview = copies.prepare_copy(plan.root, plan.root.children, str(target))
    assert preview.items[0].reason == "collision"
    renamed = copies.prepare_copy(plan.root, plan.root.children, str(target), collision="rename")
    assert renamed.items[0].destination.endswith("folder (2)") and not renamed.items[0].reason


def test_partial_failure_retains_copy_and_stops_batch_without_original_mutation(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    original = copies.copy_file
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(args[0])
        if len(calls) == 2:
            raise PermissionError("owned file held open")
        original(*args, **kwargs)

    monkeypatch.setattr(copies, "copy_file", fail_second)
    result = copies.copy_folders(plan)
    assert len(result.failed) == 1 and result.partial == [str(target / "folder")]
    assert not result.verified
    assert (source / "folder" / "nested" / "two").read_bytes() == b"two"
    assert (source / "folder" / "one").read_bytes() == b"one"


def test_cancel_retains_partial_destination_and_no_verified_proof(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    cancel = threading.Event()
    result = copies.copy_folders(plan, cancel=cancel, progress=lambda *_args: cancel.set())
    assert result.canceled and not result.verified and result.partial == [str(target / "folder")]
    assert len(list((source / "folder").rglob("*"))) == 4
    assert copies.prepare_copy(plan.root, plan.root.children, str(target), cancel=cancel) is None


@pytest.mark.parametrize("change", ["source", "destination", "extra", "missing"])
def test_final_verification_refuses_changed_source_or_copy(tmp_path, monkeypatch, change):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    proof = copies.copy_folders(plan).verified[0]
    if change == "source":
        (source / "folder" / "one").write_bytes(b"new")
    elif change == "destination":
        (target / "folder" / "one").write_bytes(b"new")
    elif change == "extra":
        (target / "folder" / "extra").write_bytes(b"unreviewed")
    else:
        (target / "folder" / "one").unlink()
    with pytest.raises((OSError, ValueError)):
        copies.verify_copy(proof)
    assert (source / "folder" / "nested" / "two").read_bytes() == b"two"


def test_changed_parent_after_preview_and_after_copy_is_refused(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    target.rename(target.with_name("old-target"))
    target.mkdir()
    assert len(copies.copy_folders(plan).failed) == 1
    assert not list(target.iterdir()) and (source / "folder").is_dir()
    plan = copies.prepare_copy(plan.root, plan.root.children, str(target))
    proof = copies.copy_folders(plan).verified[0]
    (target / "folder").rename(target / "original-copy")
    (target / "folder").mkdir()
    with pytest.raises(ValueError, match="identity"):
        copies.verify_copy(proof)


def test_links_special_and_incomplete_sources_never_become_verified(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    linked = source / "folder" / "linked"
    try:
        linked.symlink_to(source / "folder" / "one")
    except OSError as exc:
        pytest.skip(f"owned symlink unavailable: {exc}")
    root = scan(source).root
    preview = copies.prepare_copy(root, root.children, str(target))
    assert preview.items[0].reason == "copy_unsupported" and not list(target.iterdir())
    with pytest.raises(ValueError):
        copies.prepare_copy(root, [], str(target))


def test_new_leaf_collision_at_exclusive_create_preserves_arrival(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    original = copies.copy_file
    arrivals = []

    def arrival(path, destination, snapshot, cancel, **kwargs):
        arrivals.append(destination)
        Path(destination).write_bytes(b"arrival")
        original(path, destination, snapshot, cancel, **kwargs)

    monkeypatch.setattr(copies, "copy_file", arrival)
    result = copies.copy_folders(plan)
    assert len(result.failed) == 1 and not result.verified
    assert Path(arrivals[0]).read_bytes() == b"arrival"
    assert (source / "folder" / "one").read_bytes() == b"one"


def test_large_file_threshold_is_explicit_length_only(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "copy"
    source.write_bytes(b"same-length")
    target.write_bytes(b"other-value")
    node = next(entry for entry in scan(tmp_path).root.children if entry.name == "source")
    monkeypatch.setattr(copy_io, "HASH_LIMIT", len(b"same-length"))
    copy_io.compare_file(str(source), str(target), node.snapshot, None)
    monkeypatch.setattr(copy_io, "HASH_LIMIT", len(b"same-length") + 1)
    with pytest.raises(ValueError, match="hash"):
        copy_io.compare_file(str(source), str(target), node.snapshot, None)


@pytest.mark.skipif(os.name != "nt", reason="native owned NTFS stream preservation")
def test_native_windows_alternate_stream_is_preserved_and_reverified(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    stream = str(source / "folder" / "one") + ":owned-secret"
    Path(stream).write_bytes(b"stream-payload")
    root = scan(source).root
    plan = copies.prepare_copy(root, root.children, str(target))
    result = copies.copy_folders(plan)
    assert len(result.verified) == 1 and not result.failed
    copied_stream = str(target / "folder" / "one") + ":owned-secret"
    assert Path(copied_stream).read_bytes() == b"stream-payload"
    Path(copied_stream).write_bytes(b"stream-changed")
    with pytest.raises(ValueError, match="stream"):
        copies.verify_copy(result.verified[0])


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux descriptor mount guard")
def test_destination_mount_identity_change_refuses_without_original_mutation(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    original = copy_io.descriptor_mount
    calls = []

    def changed(descriptor):
        actual = original(descriptor)
        calls.append(actual)
        return actual + 1 if len(calls) > 2 else actual

    monkeypatch.setattr(copy_io, "descriptor_mount", changed)
    result = copies.copy_folders(plan)
    assert not result.verified and len(result.failed) == 1 and "mount" in result.failed[0][1]
    assert (source / "folder" / "one").read_bytes() == b"one"
    assert (target / "folder").is_dir()


@pytest.mark.skipif(not hasattr(os, "setxattr"), reason="native POSIX extended attributes")
def test_native_extended_attributes_are_copied_and_later_changes_refused(tmp_path, monkeypatch):
    plan, source, target = _fixture(tmp_path, monkeypatch)
    try:
        os.setxattr(source / "folder" / "one", "user.owned-proof", b"metadata")
    except OSError as exc:
        pytest.skip(f"owned xattrs unavailable: {exc}")
    root = scan(source).root
    plan = copies.prepare_copy(root, root.children, str(target))
    result = copies.copy_folders(plan)
    assert len(result.verified) == 1 and not result.failed
    assert os.getxattr(target / "folder" / "one", "user.owned-proof") == b"metadata"
    os.setxattr(target / "folder" / "one", "user.owned-proof", b"tampered")
    with pytest.raises(ValueError, match="attribute"):
        copies.verify_copy(result.verified[0])
