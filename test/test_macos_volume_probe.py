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


@pytest.mark.parametrize("mounted", [True, False])
def test_attachment_refusal_records_observed_and_allowed_mounts_before_diskutil(tmp_path, monkeypatch, mounted):
    image = object.__new__(owned.OwnedImage)
    image.owned, image.root = tmp_path, tmp_path / "volume"
    image._mountpoints = {image.root}
    image.image, image.device = tmp_path / "owned.sparseimage", "/dev/disk9"
    monkeypatch.setattr(image, "_image_check", lambda: None)
    metadata = {"images": [{"image-path": str(image.image), "system-entities": [
        {"dev-entry": "/dev/disk9", "content-hint": "GUID_partition_scheme"},
        {"dev-entry": "/dev/disk10s1", "mount-point": str(Path(tmp_path).parent)}]}]}
    if not mounted:
        del metadata["images"][0]["system-entities"][1]["mount-point"]
    calls = []

    def information(args):
        assert args == ["/usr/bin/hdiutil", "info", "-plist"]
        calls.append(args)
        return metadata

    monkeypatch.setattr(owned, "plist", information)
    with pytest.raises(RuntimeError, match="escaped") as error:
        image._attachment()
    assert (str(tmp_path.parent) if mounted else "<unmounted>") in str(error.value)
    assert str(image.root) in str(error.value)
    assert "/dev/disk10s1" in str(error.value)
    assert len(calls) == 1


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
    assert image.detach_attempts[0]["native_error"]["returncode"] == 16
    assert image.detach_attempts[1]["phase"] == "verified"
    assert image.detach_attempts[1]["native_succeeded"] is True


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
    assert len(image.detach_attempts) == calls.count("detach")
    assert all(attempt["native_error"]["returncode"] == code for attempt in image.detach_attempts)


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


def test_busy_detach_preserves_native_failure_when_retry_loses_mountpoints(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.image, image.root = tmp_path / "owned.sparseimage", tmp_path / "volume"
    image.name, image.volume_uuid = "FileTree-owned", "owned-volume-uuid"
    image.device, image.attached = "/dev/disk9", True
    image._mountpoints = {image.root}
    monkeypatch.setattr(image, "_image_check", lambda: None)
    monkeypatch.setattr(owned.time, "sleep", lambda _delay: None)
    entries = [{"dev-entry": image.device, "content-hint": "GUID_partition_scheme"},
               {"dev-entry": "/dev/disk10s1", "mount-point": str(image.root)}]
    calls = []

    def information(args):
        calls.append(args)
        if args == ["/usr/bin/hdiutil", "info", "-plist"]:
            return {"images": [{"image-path": str(image.image), "system-entities": entries}]}
        if args == ["/usr/sbin/diskutil", "info", "-plist", "/dev/disk10s1"]:
            return {"DeviceIdentifier": "disk10s1", "VolumeUUID": image.volume_uuid,
                    "VolumeName": image.name, "FilesystemType": "apfs", "Mounted": False,
                    "APFSPhysicalStores": [{"APFSPhysicalStore": "disk9s1"}]}
        assert args == ["/usr/sbin/diskutil", "info", "-plist", str(image.root)]
        return {"FilesystemType": "apfs", "VolumeName": image.name, "VolumeUUID": image.volume_uuid,
                "MountPoint": str(image.root), "DeviceIdentifier": "disk10s1"}

    def detach(args):
        calls.append(args)
        assert args == ["/usr/bin/hdiutil", "detach", image.device]
        del entries[1]["mount-point"]
        raise subprocess.CalledProcessError(16, args, output=b"disk10s1 unmounted",
                                            stderr=b"hdiutil: couldn't eject disk9 - Resource busy")

    monkeypatch.setattr(owned, "plist", information)
    monkeypatch.setattr(owned, "command", detach)
    monkeypatch.setattr(owned.os.path, "ismount", lambda _path: "mount-point" in entries[1])
    with pytest.raises(RuntimeError, match="<unmounted>"):
        image.detach()
    assert image.attached
    assert calls == [["/usr/bin/hdiutil", "info", "-plist"],
                     ["/usr/sbin/diskutil", "info", "-plist", str(image.root)],
                     ["/usr/bin/hdiutil", "detach", image.device],
                     ["/usr/bin/hdiutil", "info", "-plist"],
                     ["/usr/sbin/diskutil", "info", "-plist", "/dev/disk10s1"]]
    assert image.detach_attempts[0]["native_error"] == {
        "returncode": 16, "stdout": "disk10s1 unmounted",
        "stderr": "hdiutil: couldn't eject disk9 - Resource busy"}
    assert image.detach_attempts[1]["phase"] == "ownership-refused"
    assert "<unmounted>" in image.detach_attempts[1]["error"]
    assert image.detach_attempts[0]["attachment"]["entities"][1]["mount-point"] == str(image.root)
    assert "mount-point" not in image.detach_attempts[1]["attachment"]["entities"][1]
    assert image.detach_attempts[0]["checked_volume"]["VolumeUUID"] == image.volume_uuid
    observed = image.detach_attempts[1]["post_busy_volume"]
    assert observed["status"] == "read" and observed["uuid_matches"] is True
    assert observed["device"] == "/dev/disk10s1" and observed["info"]["Mounted"] is False
    assert observed["info"]["APFSPhysicalStores"] == [{"APFSPhysicalStore": "disk9s1"}]


def test_native_ownership_query_error_never_becomes_a_detach_retry(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.device, image.attached = "/dev/disk9", True

    def refuse():
        raise subprocess.CalledProcessError(16, ["/usr/bin/hdiutil", "info", "-plist"], stderr=b"metadata busy")

    monkeypatch.setattr(image, "check", refuse)
    monkeypatch.setattr(owned, "command", lambda _args: pytest.fail("An ownership refusal reached detach"))
    with pytest.raises(subprocess.CalledProcessError):
        image.detach()
    assert image.attached and len(image.detach_attempts) == 1
    assert image.detach_attempts[0]["phase"] == "ownership-refused"
    assert image.detach_attempts[0]["native_error"]["stderr"] == "metadata busy"


def test_failed_post_detach_verification_retains_native_success_but_never_grants_cleanup(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.image, image.root = tmp_path / "owned.sparseimage", tmp_path / "volume"
    image.device, image.attached = "/dev/disk9", True
    monkeypatch.setattr(image, "check", lambda: None)
    monkeypatch.setattr(owned, "command", lambda _args: b"")
    monkeypatch.setattr(owned, "plist", lambda _args: {"images": [{"image-path": str(image.image)}]})
    with pytest.raises(RuntimeError, match="not verified"):
        image.detach()
    assert image.attached
    assert image.detach_attempts[0]["phase"] == "verification-refused"
    assert image.detach_attempts[0]["native_succeeded"] is True


def test_native_failure_output_is_capped_and_invalid_utf8_keeps_the_actual_code():
    error = subprocess.CalledProcessError(16, ["/usr/bin/hdiutil", "detach", "/dev/disk9"],
                                          output=b"\xff" * 70000, stderr=b"busy" * 20000)
    record = owned.native_failure(error)
    assert record["returncode"] == 16
    assert len(record["stdout"]) == 65536 and record["stdout"].startswith("\ufffd")
    assert record["stderr"] == "busy" * 16384


@pytest.mark.parametrize("refused", [False, True])
def test_phase_json_retains_attempt_history_on_both_verified_and_refused_cleanup(tmp_path, monkeypatch, refused):
    import json
    from tools import macos_apfs_peer

    attempts = [{"attempt": 1, "phase": "ownership-refused" if refused else "verified"}]
    image = SimpleNamespace(owned=tmp_path / "owned", device="/dev/disk9", volume_uuid="owned-uuid",
                            attached=True, detach_attempts=attempts, create=lambda: None, attach=lambda: None)
    image.owned.mkdir()

    def detach():
        if refused:
            raise RuntimeError("private ownership refused")
        image.attached = False

    image.detach = detach
    image.cleanup = lambda: not refused or pytest.fail("Uncertain attachment reached fixture cleanup")
    monkeypatch.setattr(probe, "OwnedImage", lambda: image)
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--evidence", str(tmp_path / "evidence")])
    monkeypatch.setattr(probe, "fixtures", lambda _image: {})
    monkeypatch.setattr(probe, "ledger_proof", lambda *_args: {})
    monkeypatch.setattr(probe, "recovery_proof", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(probe, "cross_volume_proof", lambda _image: {})
    monkeypatch.setattr(macos_apfs_peer, "reservation_proof", lambda _image: {})
    if refused:
        with pytest.raises(RuntimeError, match="fixture retained"):
            probe.main()
    else:
        assert probe.main() == 0
    proof = json.loads((tmp_path / "evidence" / "proof.json").read_text(encoding="utf-8"))
    assert proof["detach_attempts"] == attempts
    assert proof["cleanup_verified"] is not refused
    assert proof["phase"] == ("validated" if refused else "complete")
    if refused:
        assert proof["cleanup_error"] == "private ownership refused" and image.owned.is_dir()


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
