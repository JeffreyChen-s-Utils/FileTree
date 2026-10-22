"""Post-busy identity observations are bounded read-only evidence and never detach authority."""

import json
import subprocess

import pytest

from tools import macos_owned_image as owned


@pytest.fixture(autouse=True)
def _no_host_refusal_log(monkeypatch):
    """Unit tests never read the host's unified log (macOS would run the real `log show`).

    Cases that check the refusal log install their own stub over this one.
    """
    monkeypatch.setattr(owned, "refusal_log", lambda *_args: {"status": "not-read-in-unit-tests"})


def _unmount(entries, variant, root):
    entries[1].pop("mount-point")
    if variant == "foreign-mount":
        entries[1]["mount-point"] = str(root.parent / "foreign")
    elif variant == "changed-device":
        entries[0]["dev-entry"] = "/dev/disk99"
    elif variant == "missing-volume":
        entries.pop(1)
    elif variant == "duplicate-volume":
        entries.append(dict(entries[1]))


@pytest.fixture
def busy_image(tmp_path, monkeypatch):
    image = object.__new__(owned.OwnedImage)
    image.owned, image.root, image.image = tmp_path, tmp_path / "volume", tmp_path / "owned.sparseimage"
    image.name, image.volume_uuid = "FileTree-owned", "owned-uuid"
    image.device, image.attached, image.attach_attempted = "/dev/disk9", True, True
    image._mountpoints = {image.root}
    image.identity, image.anchor = (1, 2), (1, 3)
    entries = [{"dev-entry": image.device, "content-hint": "GUID_partition_scheme"},
               {"dev-entry": "/dev/disk10s1", "mount-point": str(image.root)}]
    state = {"variant": "normal", "unmounted": False, "detaches": 0, "reads": 0, "error": None,
             "volume": {"DeviceIdentifier": "disk10s1", "VolumeUUID": image.volume_uuid, "Mounted": False}}

    def image_check():
        if state["unmounted"] and state["variant"] == "changed-image":
            raise RuntimeError("owned image identity changed")

    def information(args):
        if args == ["/usr/bin/hdiutil", "info", "-plist"]:
            if state["unmounted"] and state["variant"] == "missing-image":
                return {"images": []}
            if state["variant"] == "identifier-mismatch" and len(entries) == 2:
                entries.append({"dev-entry": "/dev/disk10s2"})
            return {"images": [{"image-path": str(image.image), "system-entities": entries}]}
        if args == ["/usr/sbin/diskutil", "info", "-plist", str(image.root)]:
            identifier = {"identifier-missing": None, "identifier-mismatch": "disk10s2"}.get(
                state["variant"], "disk10s1")
            return {"FilesystemType": "apfs", "VolumeName": image.name, "VolumeUUID": image.volume_uuid,
                    "MountPoint": str(image.root), "DeviceIdentifier": identifier}
        assert args == ["/usr/sbin/diskutil", "info", "-plist", "/dev/disk10s1"]
        state["reads"] += 1
        if state["error"] is not None:
            raise state["error"]
        return state["volume"]

    def detach(args):
        assert args == ["/usr/bin/hdiutil", "detach", "-verbose", image.device]
        state["detaches"] += 1
        state["unmounted"] = True
        _unmount(entries, state["variant"], image.root)
        raise subprocess.CalledProcessError(16, args, stderr=b"owned device busy")

    monkeypatch.setattr(image, "_image_check", image_check)
    monkeypatch.setattr(owned, "plist", information)
    monkeypatch.setattr(owned, "command", detach)
    monkeypatch.setattr(owned.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(owned.os.path, "ismount", lambda _path: not state["unmounted"])
    monkeypatch.setattr(owned.shutil, "rmtree", lambda *_args: pytest.fail("uncertain image reached cleanup"))
    return image, state


@pytest.mark.parametrize("variant", ["changed-image", "changed-device", "missing-image", "foreign-mount",
                                     "missing-volume", "duplicate-volume", "identifier-missing", "identifier-mismatch"])
def test_unavailable_or_changed_ownership_never_queries_a_guessed_volume(busy_image, variant):
    image, state = busy_image
    state["variant"] = variant
    with pytest.raises(RuntimeError):
        image.detach()
    record = image.detach_attempts[-1]
    assert record["phase"] == "ownership-refused" and record["post_busy_volume"]["status"] == "not-eligible"
    assert state["detaches"] == 1 and state["reads"] == 0 and image.attached
    assert image.detach_attempts[0]["attachment"]["entities"][1]["mount-point"] == str(image.root)
    with pytest.raises(RuntimeError, match="Uncertain"):
        image.cleanup()


@pytest.mark.parametrize("value, matches", [("owned-uuid", True), ("different-uuid", False), (None, None), ("", None)])
def test_uuid_match_mismatch_and_unknown_never_convert_refusal_to_cleanup(busy_image, value, matches):
    image, state = busy_image
    state["volume"]["VolumeUUID"] = value
    with pytest.raises(RuntimeError, match="<unmounted>"):
        image.detach()
    record = image.detach_attempts[-1]
    assert record["phase"] == "ownership-refused" and record["post_busy_volume"]["status"] == "read"
    assert record["post_busy_volume"]["uuid_matches"] is matches
    assert record["checked_volume"] is None and image.detach_attempts[0]["checked_volume"]["VolumeUUID"] == "owned-uuid"
    assert state["reads"] == state["detaches"] == 1 and image.attached
    with pytest.raises(RuntimeError, match="Uncertain"):
        image.cleanup()


@pytest.mark.parametrize("kind", ["native", "timeout", "start", "plist"])
def test_diagnostic_query_failure_keeps_original_refusal_and_native_busy(busy_image, kind):
    image, state = busy_image
    command = ["/usr/sbin/diskutil", "info", "-plist", "/dev/disk10s1"]
    errors = {"native": subprocess.CalledProcessError(5, command, output=b"x" * 70000, stderr=b"y" * 70000),
              "timeout": subprocess.TimeoutExpired(command, 60, output=b"x" * 70000, stderr=b"y" * 70000),
              "start": OSError("owned metadata unavailable"), "plist": ValueError("invalid owned plist")}
    state["error"] = errors[kind]
    with pytest.raises(RuntimeError, match="<unmounted>"):
        image.detach()
    record = image.detach_attempts[-1]
    assert record["phase"] == "ownership-refused" and "<unmounted>" in record["error"]
    observation = record["post_busy_volume"]
    assert observation["status"] == "read-failed" and observation["uuid_matches"] is None
    assert observation["exception_type"] == type(errors[kind]).__name__
    assert image.detach_attempts[0]["native_error"]["returncode"] == 16
    assert state["reads"] == state["detaches"] == 1 and image.attached
    if kind == "native":
        assert observation["native_error"]["returncode"] == 5
        assert len(observation["native_error"]["stdout"]) == len(observation["native_error"]["stderr"]) == 65536
    elif kind == "timeout":
        assert observation["timeout_seconds"] == 60
        assert len(observation["outputs"]["stdout"]) == len(observation["outputs"]["stderr"]) == 65536


def test_evidence_caps_fields_entities_and_stores_without_recursive_native_values():
    entry = {"dev-entry": "d" * 1000, "mount-point": "m" * 1000}
    frame = {"image-path": "p" * 1000, "system-entities": [entry] * 100}
    observation = owned._attachment_evidence(frame)
    entry.clear()
    assert observation["entity_count"] == 100 and observation["entities_truncated"]
    assert len(observation["entities"]) == 64 and len(observation["image"]["image-path"]) == 512
    assert observation["image"]["truncated_fields"] == ["image-path"]
    assert len(observation["entities"][0]["dev-entry"]) == 512
    metadata = owned._volume_evidence({"VolumeUUID": "u" * 1000, "DeviceNode": {"untrusted": []},
                                       "DiskUUID": 1 << 1000, "APFSPhysicalStores": [None] * 20})
    assert metadata["truncated_fields"] == ["VolumeUUID"] and len(metadata["VolumeUUID"]) == 512
    assert metadata["DeviceNode"] == {"invalid_type": "dict"} and metadata["DiskUUID"] == {"invalid_type": "int"}
    assert len(metadata["APFSPhysicalStores"]) == 8 and metadata["physical_stores_truncated"]
    assert metadata["physical_store_count"] == 20 and len(json.dumps(observation)) < 100000


def test_witness_retains_original_image_scratch_and_primary_volume_binding(busy_image):
    image, state = busy_image
    with pytest.raises(RuntimeError, match="<unmounted>"):
        image.detach()
    image.identity, image.anchor = (9, 9), (10, 10)
    for record in image.detach_attempts:
        assert record["attachment"]["captured_image_identity"] == [1, 2]
        assert record["attachment"]["captured_scratch_identity"] == [1, 3]
    observed = image.detach_attempts[-1]["post_busy_volume"]
    assert observed["captured_device"] == observed["device"] == "/dev/disk10s1"
    assert observed["expected_uuid"] == "owned-uuid" and not observed["device_truncated"]
    assert state["reads"] == state["detaches"] == 1 and image.attached


def test_oversize_expected_uuid_is_marked_without_unbounded_proof_or_changed_refusal(busy_image):
    image, state = busy_image
    image.volume_uuid = "u" * 10000
    with pytest.raises(RuntimeError, match="<unmounted>"):
        image.detach()
    observed = image.detach_attempts[-1]["post_busy_volume"]
    assert len(observed["expected_uuid"]) == 512 and observed["expected_uuid_truncated"]
    assert observed["uuid_matches"] is False
    assert "VolumeUUID" in image.detach_attempts[0]["checked_volume"]["truncated_fields"]
    assert len(json.dumps(image.detach_attempts)) < 10000 and image.attached
    assert state["reads"] == state["detaches"] == 1


@pytest.mark.parametrize("codes", [(0,), (16, 0), (16, 16, 16), (5,)])
def test_verbose_detach_keeps_same_target_attempts_errors_and_bounded_success_output(tmp_path, monkeypatch, codes):
    image = object.__new__(owned.OwnedImage)
    image.image, image.root, image.device = tmp_path / "owned", tmp_path / "volume", "/dev/disk9"
    image.attached, image._mountpoints = True, {image.root}
    checks, commands, delays, observations, failures = [], [], [], [], []
    pending = iter(codes)

    def native(arguments):
        assert len(checks) == len(commands)+1
        assert arguments == ["/usr/bin/hdiutil", "detach", "-verbose", image.device]
        commands.append(arguments)
        code = next(pending)
        if code:
            error = subprocess.CalledProcessError(code, arguments, output=b"native detail", stderr=b"owned refusal")
            failures.append(error)
            raise error
        return b"\xff" + b"x"*70000

    monkeypatch.setattr(image, "_check_detach", lambda record, previous: checks.append(previous))
    monkeypatch.setattr(image, "_image_check", lambda: None)
    monkeypatch.setattr(owned, "command", native)
    monkeypatch.setattr(owned, "plist", lambda _arguments: {"images": []})
    monkeypatch.setattr(owned.os.path, "ismount", lambda _path: False)
    monkeypatch.setattr(owned.time, "sleep", delays.append)
    monkeypatch.setattr(owned, "observe_busy_image", lambda *args: observations.append(args) or {"incomplete": True})
    if codes[-1]:
        with pytest.raises(subprocess.CalledProcessError) as caught:
            image.detach()
        assert caught.value is failures[-1] and image.attached
        assert image.detach_attempts[-1]["native_error"] == {
            "returncode": codes[-1], "stdout": "native detail", "stderr": "owned refusal"}
    else:
        image.detach()
        record = image.detach_attempts[-1]
        assert not image.attached and record["phase"] == "verified"
        assert record["native_stdout"] == "\ufffd" + "x"*65535 and record["native_stdout_truncated"]
    assert len(commands) == len(codes) and checks == [False]+[True]*(len(codes)-1)
    assert delays == [.5, 1.0][:len(codes)-1]
    assert len(observations) == (1 if codes[-1] == 16 else 0)
