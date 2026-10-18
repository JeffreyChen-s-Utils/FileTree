"""Final busy observations cannot change native detach outcomes or widen read scope."""

from __future__ import annotations

import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import plistlib
import subprocess

import pytest

from tools import macos_busy_observer as observer
from tools import macos_owned_image as owned
from tools import validate_macos_busy_observer as probe
from tools.macos_detach_identity import registration, volume_binding

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_host_refusal_log(monkeypatch):
    """Unit tests never read the host's unified log (macOS would run the real `log show`).

    Cases that check the refusal log install their own stub over this one.
    """
    monkeypatch.setattr(owned, "refusal_log", lambda *_args: {"status": "not-read-in-unit-tests"})


@pytest.fixture
def scope(tmp_path, monkeypatch):
    proof = json.loads((_ROOT / "docs/updates/apfs-20261017-repeated-busy.json").read_text(encoding="utf-8"))
    attempts = proof["samples"][0]["proof"]["detach_attempts"]
    mounted, unmounted = deepcopy(attempts[0]), deepcopy(attempts[-1])
    image = tmp_path / "owned.sparseimage"
    entries = unmounted["rechecked_attachment"]["entities"]
    volume = unmounted["post_busy_volume"]["info"]
    binding = volume_binding(volume, registration(entries), volume["VolumeName"], mounted["device"])
    assert binding is not None
    attachment = {"image-path": str(image), "system-entities": entries, "process-id": 123}
    state = {"calls": [], "checks": 0, "attachment": attachment, "volume": volume,
             "lsof_code": 0, "lsof_output": b"p123\0cdiskimages-help\0\nf4\0tREG\0nowned.sparseimage\0\n",
             "lsof_timeout": False, "change_after": False}

    def run(arguments, deadline, limit):
        assert deadline == 110 and limit in (65536, 1048576)
        state["calls"].append(arguments)
        if arguments[0] == "/usr/bin/hdiutil":
            data = {"images": [state["attachment"]]}
        elif arguments[0] == "/usr/sbin/diskutil":
            assert arguments[-1] == binding.volume
            data = state["volume"]
        else:
            assert arguments[:5] == ["/usr/sbin/lsof", "-nP", "-F0pcftn", "-f", "--"]
            assert arguments[5:] == [str(image), *(entry[0] for entry in binding.registration)]
            if state["change_after"]:
                state["volume"]["VolumeUUID"] = "00000000-0000-0000-0000-000000000001"
            return observer._Output(state["lsof_code"], state["lsof_output"], b"owned warning", state["lsof_timeout"],
                                    False, False)
        return observer._Output(0, plistlib.dumps(data), b"", False, False, False)

    def check():
        state["checks"] += 1

    monkeypatch.setattr(observer, "_SUPPORTED", True)
    monkeypatch.setattr(observer, "_CLOCK", lambda: 100)
    monkeypatch.setattr(observer, "_run", run)
    return image, mounted["device"], binding, {tmp_path / "volume"}, check, state


def test_exact_literal_files_and_full_binding_are_fenced_on_both_sides(scope):
    *arguments, state = scope
    result = observer.observe_busy_image(*arguments)
    assert result["status"] == "observed" and result["scope_rechecked"]
    assert result["incomplete"] and not result["cause_established"]
    assert result["before"] == result["after"] and result["before"]["helper_pid"] == 123
    assert state["checks"] == 4 and len(state["calls"]) == 5
    assert [entry[0] for entry in state["calls"]].count("/usr/sbin/lsof") == 1
    assert base64.b64decode(result["lsof"]["stdout_base64"]) == state["lsof_output"]
    assert base64.b64decode(result["lsof"]["stderr_base64"]) == b"owned warning"
    assert result["lsof"]["literal_files"][0] == str(arguments[0])


@pytest.mark.parametrize("code, timed_out", [(0, False), (1, False), (5, False), (None, True)])
def test_empty_or_failed_lsof_never_proves_no_holder(scope, code, timed_out):
    *arguments, state = scope
    state.update(lsof_output=b"", lsof_code=code, lsof_timeout=timed_out)
    result = observer.observe_busy_image(*arguments)
    assert result["incomplete"] and not result["cause_established"] and result["scope_rechecked"]
    assert result["lsof"]["returncode"] == code and result["lsof"]["timed_out"] == timed_out


@pytest.mark.parametrize("change", ["image", "registration", "uuid", "mountpoint", "missing-volume", "device"])
def test_changed_scope_skips_lsof_and_never_queries_guessed_volume(scope, change):
    image, device, binding, points, check, state = scope
    if change == "image":
        state["attachment"]["image-path"] += "-other"
    elif change == "registration":
        state["attachment"]["system-entities"].pop()
    elif change == "uuid":
        state["volume"]["VolumeUUID"] = "00000000-0000-0000-0000-000000000001"
    elif change == "mountpoint":
        state["attachment"]["system-entities"][-1]["mount-point"] = "/foreign"
    elif change == "missing-volume":
        from dataclasses import replace
        binding = replace(binding, volume="/dev/disk99s1")
    else:
        device = "/dev/disk99"
    result = observer.observe_busy_image(image, device, binding, points, check)
    assert result["status"] == "observation-refused" and not result["scope_rechecked"]
    assert not any(call[0] == "/usr/sbin/lsof" for call in state["calls"])
    if change in ("image", "registration", "mountpoint", "missing-volume", "device"):
        assert not any(call[0] == "/usr/sbin/diskutil" for call in state["calls"])


def test_changed_binding_after_lsof_keeps_raw_output_but_marks_uncertainty(scope):
    *arguments, state = scope
    state["change_after"] = True
    result = observer.observe_busy_image(*arguments)
    assert result["status"] == "observation-refused" and result["failed_stage"] == "scope-after"
    assert not result["scope_rechecked"] and result["incomplete"]
    assert base64.b64decode(result["lsof"]["stdout_base64"]) == state["lsof_output"]


@pytest.mark.parametrize("eligible", [False, True])
def test_unsupported_or_missing_binding_never_starts_native_commands(scope, monkeypatch, eligible):
    image, device, binding, points, check, state = scope
    monkeypatch.setattr(observer, "_SUPPORTED", eligible)
    result = observer.observe_busy_image(image, device, None if eligible else binding, points, check)
    assert result["status"] == ("not-eligible" if eligible else "unsupported")
    assert not state["calls"] and not state["checks"]


@pytest.mark.parametrize("timed_out", [False, True])
def test_command_output_caps_timeout_and_binary_fields_are_preserved(tmp_path, monkeypatch, timed_out):
    monkeypatch.setattr(observer, "_CLOCK", lambda: 99)

    def run(arguments, **kwargs):
        assert kwargs["timeout"] == 1 and kwargs["stdin"] == subprocess.DEVNULL
        assert not kwargs["check"] and "shell" not in kwargs
        kwargs["stdout"].write(b"\xff" * 70000)
        kwargs["stderr"].write(b"\xfe" * 70000)
        if timed_out:
            raise subprocess.TimeoutExpired(arguments, 1)
        return subprocess.CompletedProcess(arguments, 16)

    monkeypatch.setattr(observer.subprocess, "run", run)
    result = observer._run(["/usr/sbin/lsof", "-f", "--", str(tmp_path / "owned")], 100, 65536)
    assert len(result.stdout) == len(result.stderr) == 65536
    assert result.stdout_truncated and result.stderr_truncated and result.timed_out == timed_out
    assert result.returncode == (None if timed_out else 16)


def test_exhausted_budget_and_unknown_program_never_start_process(monkeypatch):
    monkeypatch.setattr(observer, "_CLOCK", lambda: 100)
    monkeypatch.setattr(observer.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("unexpected native call"))
    with pytest.raises(TimeoutError, match="budget"):
        observer._run(["/usr/sbin/lsof"], 100, 65536)
    with pytest.raises(ValueError, match="program"):
        observer._run(["/unknown"], 101, 65536)


def test_only_final_native_busy_invokes_observer_and_original_error_survives(monkeypatch, tmp_path):
    image = object.__new__(owned.OwnedImage)
    image.image, image.device = tmp_path / "owned", "/dev/disk9"
    image._mountpoints, image.attached = {tmp_path / "volume"}, True
    attempts, observations, delays = [], [], []
    failure = subprocess.CalledProcessError(16, ["/usr/bin/hdiutil", "detach", "-verbose", image.device])

    def detach(arguments):
        attempts.append(arguments)
        raise failure

    monkeypatch.setattr(image, "_check_detach", lambda *_args: None)
    monkeypatch.setattr(image, "_image_check", lambda: None)
    monkeypatch.setattr(owned, "command", detach)
    monkeypatch.setattr(owned.time, "sleep", delays.append)
    monkeypatch.setattr(owned, "observe_busy_image", lambda *args: observations.append(args) or {"incomplete": True})
    with pytest.raises(subprocess.CalledProcessError) as caught:
        image.detach()
    assert caught.value is failure and len(attempts) == 3 and delays == [.5, 1.0]
    assert len(observations) == 1 and image.attached
    assert "busy_observation" not in image.detach_attempts[0] and "busy_observation" not in image.detach_attempts[1]
    assert image.detach_attempts[2]["busy_observation"] == {"incomplete": True}


@pytest.mark.parametrize("kind", ["healthy", "missing-pid", "timeout", "backend-error"])
def test_native_literal_probe_retains_actual_output_source_and_cleanup(monkeypatch, tmp_path, kind):
    temporary = probe.tempfile.NamedTemporaryFile
    monkeypatch.setattr(probe.tempfile, "NamedTemporaryFile", lambda **kwargs: temporary(dir=tmp_path, **kwargs))
    monkeypatch.setattr(probe, "_native", lambda: None)

    def run(arguments, deadline, limit):
        assert arguments[:5] == ["/usr/sbin/lsof", "-nP", "-F0pcftn", "-f", "--"]
        assert Path(arguments[-1]).parent == tmp_path
        if kind == "backend-error":
            raise OSError("owned backend unavailable")
        data = ("p" + str(os.getpid()) + "\0cowned\0\nf3\0tREG\0n" + arguments[-1] + "\0\n").encode()
        return observer._Output(None if kind == "timeout" else 0, b"" if kind == "missing-pid" else data,
                                b"", kind == "timeout", False, False)

    monkeypatch.setattr(observer, "_run", run)
    output = tmp_path / "proof.json"
    if kind == "healthy":
        probe.validate(output)
    else:
        with pytest.raises((OSError, RuntimeError)):
            probe.validate(output)
    proof = json.loads(output.read_text(encoding="utf-8"))
    assert proof["phase"] == ("verified" if kind == "healthy" else "failed")
    assert proof["owned_fixture_cleanup"] and not Path(proof["owned_file"]).exists()
    assert not proof["mounts_created"] and not proof["busy_cause_established"]
    if kind != "backend-error":
        assert proof["source_preserved"]
        assert bool(base64.b64decode(proof["lsof"]["stdout_base64"])) == (kind != "missing-pid")


def test_existing_probe_evidence_is_not_overwritten(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "_native", lambda: None)
    output = tmp_path / "proof.json"
    output.write_text("retained", encoding="utf-8")
    with pytest.raises(ValueError, match="Existing"):
        probe.validate(output)
    assert output.read_text(encoding="utf-8") == "retained"


@pytest.mark.parametrize("codes", [(0,), (16, 0), (5,), (16, 5), (16, 16, 5)])
def test_success_and_other_native_failures_never_start_busy_observer(monkeypatch, tmp_path, codes):
    image = object.__new__(owned.OwnedImage)
    image.device, image.root, image.image = "/dev/disk9", tmp_path / "volume", tmp_path / "image"
    image._mountpoints, image.attached = {image.root}, True
    pending, commands = iter(codes), []

    def command(arguments):
        commands.append(arguments)
        code = next(pending)
        if code:
            raise subprocess.CalledProcessError(code, arguments)
        return b""

    monkeypatch.setattr(image, "_check_detach", lambda *_args: None)
    monkeypatch.setattr(owned, "command", command)
    monkeypatch.setattr(owned, "plist", lambda _args: {"images": []})
    monkeypatch.setattr(owned.os.path, "ismount", lambda _path: False)
    monkeypatch.setattr(owned.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(owned, "observe_busy_image", lambda *_args: pytest.fail("unexpected observer"))
    if codes[-1]:
        with pytest.raises(subprocess.CalledProcessError) as caught:
            image.detach()
        assert caught.value.returncode == codes[-1] and image.attached
    else:
        image.detach()
        assert not image.attached
    assert len(commands) == len(codes)


def test_native_probe_refuses_platform_before_creating_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(probe.sys, "platform", "not-native")
    output = tmp_path / "proof.json"
    with pytest.raises(ValueError, match="native macOS"):
        probe.validate(output)
    assert not output.exists()


def _log_output(lines, returncode=0):
    return observer._Output(returncode, b"\n".join(line.encode() for line in lines), b"", False, False, False)


def test_refusal_log_reads_bounded_diskarbitration_entries_without_claiming_a_cause(monkeypatch):
    calls = []
    entry = {"timestamp": "2026-10-17 12:00:01.5+0000", "processImagePath": "/usr/sbin/diskarbitrationd",
             "processID": 88, "subsystem": "com.apple.DiskArbitration.diskarbitrationd", "category": "default",
             "eventMessage": "disk5 eject dissented by PID 412 (/System/Library/mds) status 0x0000c010"}
    lines = [json.dumps(entry)] * 205 + ["not json", json.dumps({"no": "message"})]
    monkeypatch.setattr(observer, "_SUPPORTED", True)
    monkeypatch.setattr(observer, "_run", lambda arguments, _deadline, limit, timeout: calls.append(
        (arguments, limit, timeout)) or _log_output(lines))
    record = observer.refusal_log("/dev/disk5", 1000.0, 1002.5)
    [(arguments, limit, timeout)] = calls
    assert arguments[:4] == ["/usr/bin/log", "show", "--style", "ndjson"] and timeout == observer._LOG_TIMEOUT
    assert arguments[-1] == record["predicate"] and 'eventMessage CONTAINS "disk5"' in record["predicate"]
    assert record["window"] == [observer._log_time(998.0), observer._log_time(1004.5)]
    assert record["status"] == "observed" and record["cause_established"] is False
    assert record["entry_count"] == 205 and len(record["entries"]) == 200 and record["entries_truncated"]
    assert record["invalid_lines"] == 1 and limit == observer._LOG_LIMIT
    assert record["entries"][0] == {"time": entry["timestamp"], "process": "diskarbitrationd", "pid": 88,
                                    "subsystem": entry["subsystem"], "category": "default",
                                    "message": entry["eventMessage"]}


@pytest.mark.parametrize(("device", "first", "finished"), [("/dev/disk5s1", 1.0, 2.0), ("/dev/rdisk5", 1.0, 2.0),
                                                            ('/dev/disk5" OR 1', 1.0, 2.0), ("/dev/disk5", 3.0, 2.0)])
def test_refusal_log_refuses_unexpected_devices_or_windows_before_running(monkeypatch, device, first, finished):
    monkeypatch.setattr(observer, "_SUPPORTED", True)
    monkeypatch.setattr(observer, "_run", lambda *_args: pytest.fail("log read for an ineligible device"))
    assert observer.refusal_log(device, first, finished) == {"status": "not-eligible", "cause_established": False}


def test_refusal_log_failures_are_recorded_and_never_raised(monkeypatch):
    def timed_out(*_args):
        raise TimeoutError("Owned-image observation budget exhausted")
    monkeypatch.setattr(observer, "_SUPPORTED", True)
    monkeypatch.setattr(observer, "_run", timed_out)
    record = observer.refusal_log("/dev/disk5", 1000.0, 1002.0)
    assert record["status"] == "observation-refused" and record["exception_type"] == "TimeoutError"
    assert observer.refusal_log("/dev/disk5", 1e300, 1e300)["status"] == "observation-refused"  # unconvertible
    monkeypatch.setattr(observer, "_SUPPORTED", False)
    assert observer.refusal_log("/dev/disk5", 1.0, 2.0)["status"] == "unsupported"
