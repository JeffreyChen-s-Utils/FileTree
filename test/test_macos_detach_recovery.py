"""Replay the captured native busy/unmounted transition without targeting any host device."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from tools import macos_owned_image as owned


@pytest.fixture
def captured_image(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "docs/updates/apfs-20261017-uuid-refusal.json"
    attempts = json.loads(path.read_text(encoding="utf-8"))["raw"]["result"]["detach_attempts"]
    mounted, unmounted = deepcopy(attempts[0]), deepcopy(attempts[1])
    image = object.__new__(owned.OwnedImage)
    image.owned, image.root, image.image = tmp_path, tmp_path / "volume", tmp_path / "owned.sparseimage"
    image.name = mounted["checked_volume"]["VolumeName"]
    image.volume_uuid, image.device = mounted["checked_volume"]["VolumeUUID"], mounted["device"]
    image.attached, image.attach_attempted = True, True
    image.identity, image.anchor = (1, 2), (1, 3)
    image._mountpoints = {image.root}
    mounted["checked_volume"]["MountPoint"] = str(image.root)
    for entry in mounted["attachment"]["entities"]:
        if entry.get("mount-point"):
            entry["mount-point"] = str(image.root)
    state = {"phase": 0, "commands": [], "reads": [], "mounted": mounted, "unmounted": unmounted,
             "busy_observations": [], "refusal_logs": []}

    def information(args):
        state["reads"].append(args)
        if args == ["/usr/bin/hdiutil", "info", "-plist"]:
            if state["phase"] == 2:
                return {"images": []}
            frame = mounted if state["phase"] == 0 else unmounted
            return {"images": [{"image-path": str(image.image),
                                "system-entities": deepcopy(frame["attachment"]["entities"])}]}
        if args == ["/usr/sbin/diskutil", "info", "-plist", str(image.root)]:
            return deepcopy(mounted["checked_volume"])
        assert args == ["/usr/sbin/diskutil", "info", "-plist", unmounted["post_busy_volume"]["device"]]
        return deepcopy(unmounted["post_busy_volume"]["info"])

    def detach(args):
        assert args == ["/usr/bin/hdiutil", "detach", "-verbose", image.device]
        state["commands"].append(args)
        if state["phase"] == 0:
            state["phase"] = 1
            raise subprocess.CalledProcessError(16, args, stderr=b"hdiutil: resource busy")
        state["phase"] = 2
        return b""

    monkeypatch.setattr(image, "_image_check", lambda: None)
    monkeypatch.setattr(owned, "plist", information)
    monkeypatch.setattr(owned, "command", detach)
    monkeypatch.setattr(owned, "observe_busy_image", lambda *args:
                        state["busy_observations"].append(args) or {"status": "modeled", "incomplete": True})
    monkeypatch.setattr(owned, "refusal_log", lambda device, first, finished: state["refusal_logs"].append(
        (device, first, finished, len(state["commands"]))) or {"status": "modeled"})
    monkeypatch.setattr(owned.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(owned.os.path, "ismount", lambda _path: state["phase"] == 0)
    return image, state


def test_captured_native_busy_then_unmounted_binding_can_finish_normal_detach(captured_image):
    image, state = captured_image
    image.detach()
    assert state["phase"] == 2 and len(state["commands"]) == 2 and not image.attached
    assert image.detach_attempts[0]["native_error"]["returncode"] == 16
    assert image.detach_attempts[1]["unmounted_identity_rechecked"] is True
    assert image.detach_attempts[1]["native_succeeded"] and image.detach_attempts[1]["phase"] == "verified"
    [(device, first, finished, commands)] = state["refusal_logs"]  # once, after the last native attempt
    assert device == image.device and first <= finished and commands == 2
    assert image.detach_attempts[1]["refusal_log"] == {"status": "modeled"}
    assert "refusal_log" not in image.detach_attempts[0]


@pytest.mark.parametrize("field,value", [
    ("VolumeUUID", "00000000-0000-0000-0000-000000000000"), ("VolumeUUID", "different"),
    ("VolumeUUID", "u" * 10000), ("VolumeUUID", None), ("VolumeName", "different"),
    ("FilesystemType", "hfs"), ("DeviceIdentifier", "disk99s1"), ("DeviceNode", "/dev/disk99s1"),
    ("APFSContainerReference", "disk99"), ("ParentWholeDisk", "disk99"),
    ("APFSPhysicalStores", []), ("APFSPhysicalStores", [{"APFSPhysicalStore": "disk99s1"}]),
    ("APFSPhysicalStores", [None]), ("APFSPhysicalStores", "disk5s1"),
    ("Mounted", True), ("Mounted", 0), ("Mounted", "false"), ("MountPoint", "/foreign"),
])
def test_changed_or_incomplete_raw_volume_metadata_never_authorizes_retry(captured_image, field, value):
    image, state = captured_image
    state["unmounted"]["post_busy_volume"]["info"][field] = value
    with pytest.raises(RuntimeError):
        image.detach()
    assert image.attached and state["phase"] == 1 and len(state["commands"]) == 1
    assert image.detach_attempts[-1]["phase"] == "ownership-refused"
    with pytest.raises(RuntimeError, match="Uncertain"):
        image.cleanup()


@pytest.mark.parametrize("change", ["arrival", "missing", "hint", "duplicate", "false-mount", "missing-baseline"])
def test_entire_registration_and_complete_mounted_binding_are_required(captured_image, change):
    image, state = captured_image
    entries = state["unmounted"]["attachment"]["entities"]
    if change == "arrival":
        entries.append({"dev-entry": "/dev/disk6s99"})
    elif change == "missing":
        entries.pop()
    elif change == "hint":
        entries[1]["content-hint"] = "changed"
    elif change == "duplicate":
        entries.append(dict(entries[-1]))
    elif change == "false-mount":
        entries[-1]["mount-point"] = False
    else:
        state["mounted"]["checked_volume"].pop("APFSPhysicalStores")
    with pytest.raises(RuntimeError):
        image.detach()
    assert image.attached and len(state["commands"]) == 1


@pytest.mark.parametrize("change", ["image", "mount"])
def test_identity_or_mountpoint_changed_after_volume_read_still_refuses(captured_image, monkeypatch, change):
    image, state = captured_image
    original = owned.plist
    observed = []

    def information(args):
        result = original(args)
        if args[-1] == "/dev/disk6s1":
            observed.append(True)
        return result

    def image_check():
        if observed and change == "image":
            raise RuntimeError("image replaced after metadata read")

    monkeypatch.setattr(owned, "plist", information)
    monkeypatch.setattr(image, "_image_check", image_check)
    monkeypatch.setattr(owned.os.path, "ismount", lambda _path: state["phase"] == 0 or observed and change == "mount")
    with pytest.raises(RuntimeError):
        image.detach()
    assert observed == [True] and len(state["commands"]) == 1 and image.attached


def test_unexpected_unmounted_first_attempt_never_uses_a_captured_uuid_as_authority(captured_image):
    image, state = captured_image
    image.check()
    state["phase"] = 1
    with pytest.raises(RuntimeError):
        image.detach()
    assert not state["commands"] and image.attached
    assert not any(args[-1] == "/dev/disk6s1" for args in state["reads"])


@pytest.mark.parametrize("succeeds", [False, True])
def test_unmounted_retries_share_the_existing_three_attempt_limit(captured_image, monkeypatch, succeeds):
    image, state = captured_image
    original = owned.command

    def detach(args):
        if state["phase"] == 1 and (not succeeds or len(state["commands"]) < 2):
            state["commands"].append(args)
            raise subprocess.CalledProcessError(16, args, stderr=b"still busy")
        return original(args)

    monkeypatch.setattr(owned, "command", detach)
    if succeeds:
        image.detach()
        assert not image.attached
    else:
        with pytest.raises(subprocess.CalledProcessError):
            image.detach()
        assert image.attached
    assert len(state["commands"]) == 3 and len(image.detach_attempts) == 3
    assert len(state["busy_observations"]) == int(not succeeds)
    assert [entry[3] for entry in state["refusal_logs"]] == [3]  # after the third attempt, success or not
    assert image.detach_attempts[-1]["refusal_log"] == {"status": "modeled"}
    assert all(args == ["/usr/bin/hdiutil", "detach", "-verbose", image.device] for args in state["commands"])


def test_native_success_without_attachment_absence_does_not_grant_cleanup(captured_image, monkeypatch):
    image, state = captured_image
    original = owned.plist

    def information(args):
        if state["phase"] == 2 and args[0] == "/usr/bin/hdiutil":
            return {"images": [{"image-path": str(image.image)}]}
        return original(args)

    monkeypatch.setattr(owned, "plist", information)
    with pytest.raises(RuntimeError, match="not verified"):
        image.detach()
    record = image.detach_attempts[-1]
    assert record["native_succeeded"] and record["unmounted_identity_rechecked"]
    assert record["phase"] == "verification-refused" and image.attached


@pytest.mark.parametrize("change", ["hint", "remount", "missing", "foreign-image"])
def test_registration_is_rechecked_after_volume_identity_read(captured_image, monkeypatch, change):
    image, state = captured_image
    original = owned.plist

    def information(args):
        result = original(args)
        if args[-1] == "/dev/disk6s1":
            entries = state["unmounted"]["attachment"]["entities"]
            if change == "hint":
                entries[1]["content-hint"] = "changed-after-read"
            elif change == "remount":
                entries[-1]["mount-point"] = "/foreign"
            elif change == "missing":
                entries.pop()
            else:
                state["foreign"] = True
        elif state.get("foreign") and args[0] == "/usr/bin/hdiutil":
            return {"images": []}
        return result

    monkeypatch.setattr(owned, "plist", information)
    with pytest.raises(RuntimeError):
        image.detach()
    assert state["phase"] == 1 and image.attached and len(state["commands"]) == 1


@pytest.mark.parametrize("change", ["many-devices", "long-device", "long-hint", "invalid-device", "duplicate-store"])
def test_incomplete_or_oversized_topology_cannot_become_detach_authority(captured_image, change):
    image, state = captured_image
    frame = state["unmounted"]
    entries = frame["attachment"]["entities"]
    if change == "many-devices":
        entries.extend({"dev-entry": f"/dev/disk6s{number}"} for number in range(100, 164))
    elif change == "long-device":
        entries[-1]["dev-entry"] = "/dev/disk" + "6"*1000
    elif change == "long-hint":
        entries[-1]["content-hint"] = "h"*10000
    elif change == "invalid-device":
        entries[-1]["dev-entry"] = "not-a-native-device"
    else:
        stores = frame["post_busy_volume"]["info"]["APFSPhysicalStores"]
        stores.append(dict(stores[0]))
    with pytest.raises(RuntimeError):
        image.detach()
    assert image.attached and len(state["commands"]) == 1


def test_a_detach_without_busy_refusal_reads_no_refusal_log(captured_image, monkeypatch):
    image, state = captured_image
    original = owned.command

    def detach(args):
        state["commands"].append(args)
        state["phase"] = 2
        return b""
    monkeypatch.setattr(owned, "command", lambda args: detach(args) if state["phase"] == 0 else original(args))
    image.detach()
    assert not image.attached and not state["refusal_logs"]
    assert "refusal_log" not in image.detach_attempts[-1]
