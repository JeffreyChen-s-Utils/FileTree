"""Undo captures and receipts stay bounded; native restoration touches only freshly owned bins."""

import sys
import json
import threading
from urllib.parse import quote

import pytest

from je_file_tree.core import bin_empty, trash_restore
from je_file_tree.core.snapshot import stat_snapshot


def test_strict_receipt_paths_decode_cjk_spaces_and_relative_mount_paths():
    contents = "[Trash Info]\nPath=%2Fhome%2F%E6%AA%94%E6%A1%88%20%23.txt\nDeletionDate=2026-10-08T00:00:00\n"
    assert trash_restore.receipt_destination(contents) == "/home/檔案 #.txt"
    relative = "[Trash Info]\nPath=folder/file\nDeletionDate=2026-10-08T00:00:00\n"
    assert trash_restore.receipt_destination(relative, topdir="/mnt/volume") == "/mnt/volume/folder/file"
    with pytest.raises(ValueError, match="topdir"):
        trash_restore.receipt_destination(relative)


@pytest.mark.parametrize("path", ["%2Fhome%2F..%2Foutside", "%00", "/home//entry", "bad%escape", "../outside"])
def test_invalid_receipt_paths_never_become_restore_targets(path):
    with pytest.raises(ValueError):
        trash_restore.receipt_destination(f"[Trash Info]\nPath={path}\nDeletionDate=2026-10-08T00:00:00\n",
                                          topdir="/owned")


def test_missing_date_duplicate_keys_and_oversized_receipts_are_refused():
    for text in ("[Trash Info]\nPath=/entry\n", "[Trash Info]\nPath=/entry\nPath=/other\n",
                 "x" * (bin_empty.MAX_RECEIPT_BYTES + 1)):
        with pytest.raises(ValueError):
            trash_restore.receipt_destination(text)


def test_origin_is_captured_before_move_and_changed_scanned_metadata_is_refused(tmp_path):
    path = tmp_path.resolve() / "original"
    path.write_bytes(b"original")
    snapshot = stat_snapshot(str(path))
    origin = trash_restore.capture_origin(str(path), snapshot)
    assert origin.path == str(path) and origin.snapshot == snapshot
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        trash_restore.capture_origin(str(path), snapshot)


def test_native_probe_writes_atomic_evidence_and_restores_process_environment(tmp_path, monkeypatch):
    from tools import validate_linux_restore as probe
    output = tmp_path / "proof.json"
    monkeypatch.setattr(sys, "argv", ["validate_linux_restore", "--output", str(output)])
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "original-setting")

    def native(case):
        monkeypatch.setenv("XDG_DATA_HOME", "owned-fixture-setting")
        return {"passed": True, "case": case}

    monkeypatch.setattr(probe, "native_case", native)
    probe.main()
    assert len(json.loads(output.read_text(encoding="utf-8"))) == 4
    import os
    assert os.environ["XDG_DATA_HOME"] == "original-setting"


def test_empty_cancellation_exception_has_visible_error_and_preserves_receipt(tmp_path, monkeypatch):
    source = tmp_path.resolve() / "original"
    source.write_bytes(b"preserved")
    origin = trash_restore.capture_origin(str(source), stat_snapshot(str(source)))
    receipt = bin_empty.BinEntry(("payload.trashinfo",), origin.snapshot, False)
    plan = trash_restore.RestorePlan(origin, str(tmp_path / "payload"), str(tmp_path), 0, 0, (), (), receipt, ())

    def canceled(_root):
        raise bin_empty.BinSurveyCancelledError

    monkeypatch.setattr(bin_empty, "_volume", canceled)
    result = trash_restore.restore(plan)
    assert not result.restored and result.receipt_retained and "canceled" in result.error
    assert source.read_bytes() == b"preserved" and not (tmp_path / "payload").exists()


@pytest.fixture
def owned_bin(tmp_path, monkeypatch):
    if not sys.platform.startswith("linux"):
        pytest.skip("native Linux descriptor and mount APIs required")
    root = tmp_path.resolve() / "volume"
    root.mkdir()
    monkeypatch.setattr(bin_empty, "mount_points", lambda: frozenset({str(root)}))
    data = root / "data"
    data.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    scope = data / "Trash"
    scope.mkdir(mode=0o700)
    files, info = scope / "files", scope / "info"
    files.mkdir(mode=0o700)
    info.mkdir(mode=0o700)
    original = root / "original"
    (original / "empty").mkdir(parents=True)
    (original / "file").write_bytes(b"original bytes")
    origin = trash_restore.capture_origin(str(original), stat_snapshot(str(original)))
    trashed = files / "payload"
    original.rename(trashed)
    receipt = info / "payload.trashinfo"
    receipt.write_text(f"[Trash Info]\nPath={quote(str(original))}\nDeletionDate=2026-10-08T00:00:00\n",
                       encoding="utf-8")
    return root, original, trashed, receipt, origin


def _prepare(fixture):
    root, _original, trashed, _receipt, origin = fixture
    return trash_restore.prepare_restore(origin, str(trashed), str(root))


def test_native_exclusive_restore_removes_only_its_receipt_and_preserves_containers(owned_bin):
    _root, original, trashed, receipt, _origin = owned_bin
    plan = _prepare(owned_bin)
    result = trash_restore.restore(plan)
    assert result.restored and not result.error and not result.receipt_retained
    assert (original / "file").read_bytes() == b"original bytes" and (original / "empty").is_dir()
    assert not trashed.exists() and not receipt.exists()
    assert receipt.parent.is_dir() and trashed.parent.is_dir()


@pytest.mark.parametrize("change", ["payload", "receipt", "destination", "parent", "mount", "cancel"])
def test_changes_and_cancel_refuse_restore_without_mutations(owned_bin, monkeypatch, change):
    _root, original, trashed, receipt, _origin = owned_bin
    plan = _prepare(owned_bin)
    cancel = threading.Event()
    if change == "payload":
        (trashed / "file").write_bytes(b"changed bytes")
    elif change == "receipt":
        receipt.write_text("[Trash Info]\nPath=/wrong\nDeletionDate=2026-10-08T00:00:00\n", encoding="utf-8")
    elif change == "destination":
        original.mkdir()
        (original / "arrival").write_bytes(b"retain")
    elif change == "parent":
        trashed.parent.rename(trashed.parent.with_name("old-files"))
        trashed.parent.mkdir()
    elif change == "mount":
        monkeypatch.setattr(trash_restore, "descriptor_mount", lambda _fd: plan.mount + 1)
    else:
        cancel.set()
    result = trash_restore.restore(plan, cancel=cancel)
    assert not result.restored and result.error and result.receipt_retained and receipt.exists()
    if change != "destination":
        assert not original.exists()
    else:
        assert (original / "arrival").read_bytes() == b"retain"


def test_arrival_at_native_rename_is_never_overwritten(owned_bin, monkeypatch):
    _root, original, trashed, receipt, _origin = owned_bin
    plan = _prepare(owned_bin)
    native = trash_restore.rename_no_replace

    def arrival(*args):
        original.mkdir()
        (original / "arrival").write_bytes(b"preserved")
        native(*args)

    monkeypatch.setattr(trash_restore, "rename_no_replace", arrival)
    result = trash_restore.restore(plan)
    assert not result.restored and result.error and receipt.exists()
    assert (original / "arrival").read_bytes() == b"preserved" and (trashed / "file").read_bytes() == b"original bytes"


def test_receipt_cleanup_failure_retains_truthful_success_and_metadata(owned_bin, monkeypatch):
    _root, original, trashed, receipt, _origin = owned_bin
    plan = _prepare(owned_bin)

    def refused(*_args, **_kwargs):
        raise PermissionError("owned receipt cleanup refused")

    monkeypatch.setattr(bin_empty, "_remove_entry", refused)
    result = trash_restore.restore(plan)
    assert result.restored and result.receipt_retained and "cleanup refused" in result.error
    assert (original / "file").read_bytes() == b"original bytes" and not trashed.exists() and receipt.exists()


def test_changed_receipt_cannot_redirect_original_outside_approval(owned_bin):
    root, original, trashed, receipt, origin = owned_bin
    receipt.write_text("[Trash Info]\nPath=/unowned-target\nDeletionDate=2026-10-08T00:00:00\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        trash_restore.prepare_restore(origin, str(trashed), str(root))
    assert not original.exists() and (trashed / "file").read_bytes() == b"original bytes"


def test_post_restore_change_rolls_back_exclusively_and_preserves_receipt(owned_bin, monkeypatch):
    _root, original, trashed, receipt, _origin = owned_bin
    plan = _prepare(owned_bin)
    native = trash_restore.rename_no_replace
    calls = []

    def changed(*args):
        native(*args)
        calls.append(args)
        if len(calls) == 1:
            (original / "file").write_bytes(b"changed after restore")

    monkeypatch.setattr(trash_restore, "rename_no_replace", changed)
    result = trash_restore.restore(plan)
    assert not result.restored and "rolled back" in result.error and len(calls) == 2
    assert not original.exists() and (trashed / "file").read_bytes() == b"changed after restore" and receipt.exists()
