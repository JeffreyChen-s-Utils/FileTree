"""Freedesktop approval/deletion uses only freshly owned fixture bins, never real user Trash."""

from __future__ import annotations

import os
import stat
import sys
import threading
from pathlib import Path

import pytest

from je_file_tree.core import bin_empty

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux descriptor APIs required")


@pytest.fixture
def owned_bin(tmp_path, monkeypatch):
    # Treat this disposable directory as a fixture mount; all derived Trash candidates stay inside it.
    root = tmp_path / "volume"
    root.mkdir()
    monkeypatch.setattr(bin_empty, "mount_points", lambda: frozenset({str(root)}))
    data = root / "data"
    data.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    scope = data / "Trash"
    scope.mkdir(mode=0o700)
    files, info = scope / "files", scope / "info"
    files.mkdir()
    info.mkdir()
    (files / "payload").write_bytes(b"fixture payload")
    (info / "payload.trashinfo").write_text(
        "[Trash Info]\nPath=/original-not-touched\nDeletionDate=2026-10-08T00:00:00\n", encoding="utf-8")
    return root, scope, files, info


def _receipt(info: Path, name: str) -> None:
    (info / f"{name}.trashinfo").write_text("[Trash Info]\nPath=/not-used\n", encoding="utf-8")


def test_complete_plan_removes_only_captured_payloads_and_receipts(owned_bin):
    root, scope, files, info = owned_bin
    folder = files / "nested"
    folder.mkdir()
    (folder / "child").write_bytes(b"inside")
    _receipt(info, "nested")
    external = root / "outside"
    external.write_bytes(b"preserved")
    os.symlink(external, files / "link")
    _receipt(info, "link")
    plan = bin_empty.prepare_bin_empty(str(root))
    assert plan.usage.complete and plan.usage.count == 3
    assert plan.usage.size == len(b"fixture payload") + len(b"inside") + len(str(external))
    result = bin_empty.empty_posix_bin(plan)
    assert result.removed == 3 and not result.failures
    assert list(files.iterdir()) == list(info.iterdir()) == []
    assert scope.is_dir() and files.is_dir() and info.is_dir()
    assert external.read_bytes() == b"preserved"


def test_changed_approval_performs_no_deletion(owned_bin):
    root, _scope, files, info = owned_bin
    plan = bin_empty.prepare_bin_empty(str(root))
    (files / "payload").write_bytes(b"changed contents")
    with pytest.raises(ValueError, match="changed"):
        bin_empty.empty_posix_bin(plan)
    assert (files / "payload").read_bytes() == b"changed contents"
    assert (info / "payload.trashinfo").is_file()


def test_unknown_receipts_special_files_and_linked_scope_are_incomplete(owned_bin):
    root, scope, files, info = owned_bin
    (info / "orphan.trashinfo").write_text("[Trash Info]\nPath=/orphan\n", encoding="utf-8")
    plan = bin_empty.prepare_bin_empty(str(root))
    assert not plan.usage.complete
    with pytest.raises(ValueError, match="complete"):
        bin_empty.empty_posix_bin(plan)
    (info / "orphan.trashinfo").unlink()  # fixture-owned metadata only
    os.mkfifo(files / "special")
    _receipt(info, "special")
    assert not bin_empty.prepare_bin_empty(str(root)).usage.complete
    (files / "special").unlink()
    (info / "special.trashinfo").unlink()
    scope.rename(scope.with_name("other"))
    os.symlink(scope.with_name("other"), scope, target_is_directory=True)
    assert not bin_empty.prepare_bin_empty(str(root)).usage.complete
    assert (scope.with_name("other") / "files" / "payload").is_file()


def test_owner_permissions_and_cancellation_refuse_approval(owned_bin):
    root, scope, _files, _info = owned_bin
    scope.chmod(stat.S_IRWXU | stat.S_IRGRP)
    assert not bin_empty.prepare_bin_empty(str(root)).usage.complete
    cancel = threading.Event()
    cancel.set()
    assert bin_empty.prepare_bin_empty(str(root), cancel=cancel) is None


def test_partial_failure_retains_payload_receipt_and_counts_success(owned_bin, monkeypatch):
    root, _scope, files, info = owned_bin
    (files / "other").write_bytes(b"other fixture")
    _receipt(info, "other")
    plan = bin_empty.prepare_bin_empty(str(root))
    original = bin_empty._remove_entry
    def fail_payload(fd, mount, entry, identities=None):
        if entry.parts == ("payload",):
            raise PermissionError("fixture locked payload")
        return original(fd, mount, entry, identities)
    monkeypatch.setattr(bin_empty, "_remove_entry", fail_payload)
    result = bin_empty.empty_posix_bin(plan)
    assert result.removed == 1 and result.failures
    assert (files / "payload").is_file() and (info / "payload.trashinfo").is_file()
    assert not (files / "other").exists() and not (info / "other.trashinfo").exists()


def test_unknown_mount_identity_blocks_survey(owned_bin, monkeypatch):
    root, _scope, files, _info = owned_bin
    original = bin_empty.descriptor_mount
    def changed(fd):
        name = os.readlink(f"/proc/self/fd/{fd}")
        return original(fd) + int(name.endswith("/files"))
    monkeypatch.setattr(bin_empty, "descriptor_mount", changed)
    assert not bin_empty.prepare_bin_empty(str(root)).usage.complete
    assert (files / "payload").is_file()


def test_replaced_ancestor_during_empty_is_refused(owned_bin, monkeypatch):
    root, _scope, files, info = owned_bin
    folder = files / "nested"
    folder.mkdir()
    (folder / "child").write_bytes(b"original child")
    _receipt(info, "nested")
    plan = bin_empty.prepare_bin_empty(str(root))
    original = bin_empty._remove_entry
    def replace_ancestor(fd, mount, entry, identities=None):
        if entry.parts == ("nested", "child"):
            folder.rename(root / "moved-owned-fixture")
            folder.mkdir()
            (folder / "child").write_bytes(b"new child")
        return original(fd, mount, entry, identities)
    monkeypatch.setattr(bin_empty, "_remove_entry", replace_ancestor)
    result = bin_empty.empty_posix_bin(plan)
    assert result.failures and result.removed == 1
    assert (folder / "child").read_bytes() == b"new child"
    assert (root / "moved-owned-fixture" / "child").read_bytes() == b"original child"
    assert (info / "nested.trashinfo").is_file()


def test_bounded_listing_refuses_excess_without_removal(owned_bin, monkeypatch):
    root, _scope, files, info = owned_bin
    (files / "other").write_bytes(b"owned other")
    _receipt(info, "other")
    monkeypatch.setattr(bin_empty, "MAX_ENTRIES", 1)
    plan = bin_empty.prepare_bin_empty(str(root))
    assert not plan.usage.complete
    with pytest.raises(ValueError, match="complete"):
        bin_empty.empty_posix_bin(plan)
    assert (files / "payload").is_file() and (files / "other").is_file()
