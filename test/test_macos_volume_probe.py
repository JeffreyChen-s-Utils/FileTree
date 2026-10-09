"""Owned APFS tools refuse ambiguous/changed devices; uncertain detach retains disposable evidence."""

from pathlib import Path
import hashlib
import os
import subprocess
from types import SimpleNamespace

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


def test_owned_busy_detach_rechecks_identity_before_retry_and_verifies_success(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.image, image.root = tmp_path / "owned.sparseimage", tmp_path / "volume"
    image.device, image.attached = "/dev/disk9", True
    calls = []
    monkeypatch.setattr(image, "check", lambda: calls.append("check"))
    monkeypatch.setattr(owned, "time", SimpleNamespace(sleep=lambda delay: calls.append(("sleep", delay))),
                        raising=False)

    def detach(args):
        assert args == ["/usr/bin/hdiutil", "detach", image.device]
        calls.append("detach")
        if calls.count("detach") == 1:
            raise subprocess.CalledProcessError(16, args, stderr=b"hdiutil: detach failed - Resource busy")

    monkeypatch.setattr(owned, "command", detach)
    monkeypatch.setattr(owned, "plist", lambda _args: {"images": []})
    monkeypatch.setattr(owned.os.path, "ismount", lambda _path: False)
    image.detach()
    assert not image.attached and calls[:2] == ["check", "detach"]
    assert calls[-2:] == ["check", "detach"] and calls.count("detach") == 2


@pytest.mark.parametrize("code", [16, 5])
def test_failed_owned_detach_is_bounded_and_never_forced(tmp_path, monkeypatch, code):
    image = object.__new__(owned.OwnedImage)
    image.device, image.attached = "/dev/disk9", True
    calls = []
    monkeypatch.setattr(image, "check", lambda: calls.append("check"))
    monkeypatch.setattr(owned.time, "sleep", lambda _delay: None)

    def detach(args):
        assert args == ["/usr/bin/hdiutil", "detach", image.device]
        calls.append("detach")
        raise subprocess.CalledProcessError(code, args, stderr=b"owned detach refusal")

    monkeypatch.setattr(owned, "command", detach)
    with pytest.raises(subprocess.CalledProcessError) as error:
        image.detach()
    assert error.value.stderr == b"owned detach refusal" and image.attached
    assert calls.count("detach") == (3 if code == 16 else 1)
    assert calls == ["check", "detach"] * calls.count("detach")


def test_owned_detach_retries_refuse_changed_device_before_another_native_call(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.device, image.attached = "/dev/disk9", True
    calls = []

    def check():
        calls.append("check")
        if calls.count("check") > 1:
            raise RuntimeError("Owned image device changed")

    def detach(args):
        calls.append("detach")
        raise subprocess.CalledProcessError(16, args)

    monkeypatch.setattr(image, "check", check)
    monkeypatch.setattr(owned, "command", detach)
    monkeypatch.setattr(owned.time, "sleep", lambda _delay: None)
    with pytest.raises(RuntimeError, match="device changed"):
        image.detach()
    assert calls == ["check", "detach", "check"] and image.attached


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
