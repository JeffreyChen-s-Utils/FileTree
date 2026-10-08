"""Owned APFS tools refuse ambiguous/changed devices; uncertain detach retains disposable evidence."""

from pathlib import Path
import hashlib
import os

import pytest

from je_file_tree.core import savings
from je_file_tree.core.scanner import scan
from tools import macos_owned_image as owned
from tools import validate_macos_volume as probe


def test_wrong_platform_refuses_before_creating_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(owned.sys, "platform", "linux")
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--evidence", str(tmp_path / "evidence")])
    monkeypatch.setattr(owned.tempfile, "mkdtemp", lambda **_kw: pytest.fail("Wrong platform created a fixture"))
    with pytest.raises(ValueError, match="unelevated native macOS"):
        probe.main()
    assert not (tmp_path / "evidence").exists()


def test_image_device_uses_partition_map_not_synthesized_apfs_disk():
    metadata = {"system-entities": [{"dev-entry": "/dev/disk9", "content-hint": "GUID_partition_scheme"},
                                    {"dev-entry": "/dev/disk10", "content-hint": "Apple_APFS"},
                                    {"dev-entry": "/dev/disk10s1", "mount-point": "/private/owned/volume"}]}
    assert owned.image_device(metadata) == "/dev/disk9"
    metadata["system-entities"].append({"dev-entry": "/dev/disk11", "content-hint": "GUID_partition_scheme"})
    with pytest.raises(RuntimeError, match="ambiguous"):
        owned.image_device(metadata)


@pytest.mark.parametrize("metadata", [{}, {"system-entities": None}, {"system-entities": [None]},
                                      {"system-entities": [{"dev-entry": 1}]}])
def test_malformed_native_entities_never_select_a_device(metadata):
    with pytest.raises(RuntimeError):
        owned.image_device(metadata)


def test_uncertain_attachment_never_deletes_scratch(tmp_path):
    image = object.__new__(owned.OwnedImage)
    image.owned, image.attached, image.attach_attempted, image.device = tmp_path, False, True, ""
    payload = tmp_path / "retained"
    payload.write_bytes(b"disposable evidence")
    with pytest.raises(RuntimeError, match="Uncertain"):
        image.cleanup()
    assert payload.read_bytes() == b"disposable evidence"


def test_changed_scratch_refuses_cleanup_even_without_image(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.owned, image.attached, image.attach_attempted, image.device = tmp_path, False, False, ""
    image.identity, image.anchor = None, (-1, -1)
    monkeypatch.setattr(owned.os, "getuid", lambda: tmp_path.stat().st_uid, raising=False)
    with pytest.raises(RuntimeError, match="scratch directory changed"):
        image.cleanup()
    assert tmp_path.is_dir()


def test_macos_savings_marks_unknown_shared_extents_without_a_positive_lower_bound(tmp_path, monkeypatch):
    (tmp_path / "data").write_bytes(b"owned data")
    tree = scan(tmp_path).root
    monkeypatch.setattr(savings.sys, "platform", "darwin")
    value = savings.estimate_savings(tree.children, root=tree)
    assert value.uncertain and value.recoverable_min == 0
    assert value.recoverable_max == tree.children[0].allocated


def test_attachment_foreign_mount_refuses_before_diskutil(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.owned, image.root = tmp_path, tmp_path / "volume"
    image._mountpoints = {image.root}
    image.image, image.device = tmp_path / "owned.sparseimage", "/dev/disk9"
    monkeypatch.setattr(image, "_image_check", lambda: None)
    metadata = {"images": [{"image-path": str(image.image), "system-entities": [
        {"dev-entry": "/dev/disk9", "content-hint": "GUID_partition_scheme"},
        {"dev-entry": "/dev/disk10s1", "mount-point": str(Path(tmp_path).parent)}]}]}
    monkeypatch.setattr(owned, "plist", lambda args: metadata)
    with pytest.raises(RuntimeError, match="escaped"):
        image._attachment()


def test_detach_error_retains_attached_state_and_never_runs_cleanup(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.owned, image.device, image.attached, image.attach_attempted = tmp_path, "/dev/disk9", True, True
    monkeypatch.setattr(image, "check", lambda: {})

    def fail(_args):
        raise OSError("owned device busy")

    monkeypatch.setattr(owned, "command", fail)
    with pytest.raises(OSError, match="busy"):
        image.detach()
    with pytest.raises(RuntimeError, match="Uncertain"):
        image.cleanup()
    assert image.attached and tmp_path.exists()


def _portable_record(path):
    info = path.stat()
    return {"identity": [info.st_dev, info.st_ino], "links": info.st_nlink,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_owned_hard_link_batch_accounts_for_only_its_own_link_removals(tmp_path, monkeypatch):
    paths = {name: tmp_path / name for name in ("first", "second")}
    paths["first"].write_bytes(b"disposable owned data")
    os.link(paths["first"], paths["second"])
    monkeypatch.setattr(probe, "file_record", _portable_record)
    captured = {name: _portable_record(path) for name, path in paths.items()}
    probe.unlink_fixtures(paths, captured)
    assert not any(path.exists() for path in paths.values())


def test_changed_owned_payload_is_retained_even_when_identity_and_links_match(tmp_path, monkeypatch):
    paths = {"first": tmp_path / "first"}
    paths["first"].write_bytes(b"disposable owned data")
    monkeypatch.setattr(probe, "file_record", _portable_record)
    captured = {name: _portable_record(path) for name, path in paths.items()}
    paths["first"].write_bytes(b"changed disposable data")
    with pytest.raises(RuntimeError, match="fixture changed"):
        probe.unlink_fixtures(paths, captured)
    assert paths["first"].read_bytes() == b"changed disposable data"
