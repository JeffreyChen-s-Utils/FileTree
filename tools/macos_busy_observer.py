"""Read-only, fenced observations after the last owned APFS busy refusal."""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import time

from tools.macos_detach_identity import VolumeBinding, registration, volume_binding

_SUPPORTED = sys.platform == "darwin"
_CLOCK = time.monotonic
_BUDGET = 10.0
_COMMAND_TIMEOUT = 2.0
_METADATA_LIMIT = 1024 * 1024
_OUTPUT_LIMIT = 65536
_IMAGE_LIMIT = 128
_PID_MAX = (1 << 31) - 1
_PROGRAMS = {"/usr/bin/hdiutil", "/usr/sbin/diskutil", "/usr/sbin/lsof"}


@dataclass(frozen=True)
class _Output:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool

    def summary(self) -> dict:
        return {"returncode": self.returncode, "timed_out": self.timed_out,
                "stdout_captured_sha256": hashlib.sha256(self.stdout).hexdigest(),
                "stdout_truncated": self.stdout_truncated, "stderr_truncated": self.stderr_truncated,
                "stderr_base64": base64.b64encode(self.stderr).decode("ascii")}


def _run(arguments: list[str], deadline: float, limit: int) -> _Output:
    remaining = deadline - _CLOCK()
    if remaining <= 0:
        raise TimeoutError("Owned-image observation budget exhausted")
    if arguments[0] not in _PROGRAMS:
        raise ValueError("Unsupported observation program")
    # Fixed read-only callers; anonymous owned files bound RAM even if native output is excessive.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            result = subprocess.run(arguments, check=False, stdin=subprocess.DEVNULL, stdout=stdout,  # noqa: S603
                                    stderr=stderr, timeout=min(_COMMAND_TIMEOUT, remaining))
        except subprocess.TimeoutExpired:
            code, timed_out = None, True
        else:
            code, timed_out = result.returncode, False
        stdout.seek(0)
        stderr.seek(0)
        output, errors = stdout.read(limit + 1), stderr.read(_OUTPUT_LIMIT + 1)
    return _Output(code, output[:limit], errors[:_OUTPUT_LIMIT], timed_out,
                   len(output) > limit, len(errors) > _OUTPUT_LIMIT)


def _plist(arguments: list[str], deadline: float, observations: list[dict]) -> dict:
    output = _run(arguments, deadline, _METADATA_LIMIT)
    observations.append({"program": arguments[0], "operation": arguments[1], **output.summary()})
    if output.returncode != 0 or output.timed_out or output.stdout_truncated:
        raise ValueError("Incomplete owned-image observation metadata")
    value = plistlib.loads(output.stdout)
    if not isinstance(value, dict):
        raise ValueError("Invalid owned-image observation metadata")
    return value


def _scope(image: Path, device: str, binding: VolumeBinding, mountpoints: set[Path],
           deadline: float, observations: list[dict]) -> dict:
    info = _plist(["/usr/bin/hdiutil", "info", "-plist"], deadline, observations)
    images = info.get("images")
    if not isinstance(images, list) or len(images) > _IMAGE_LIMIT:
        raise ValueError("Incomplete image registration inventory")
    matches = [item for item in images if isinstance(item, dict) and item.get("image-path") == str(image)]
    if len(matches) != 1:
        raise ValueError("Owned image registration missing or ambiguous")
    attachment = matches[0]
    entries = attachment.get("system-entities")
    if (not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries)
            or registration(entries) is None or registration(entries) != binding.registration):
        raise ValueError("Owned image registration changed")
    whole = [entry.get("dev-entry") for entry in entries
             if entry.get("content-hint") in ("GUID_partition_scheme", "Apple_partition_scheme")]
    if whole != [device] or binding.volume not in {entry[0] for entry in binding.registration}:
        raise ValueError("Owned image primary device is not registered")
    allowed = {str(point) for point in mountpoints}
    if any(item.get("mount-point") not in (None, "") and
           (not isinstance(item["mount-point"], str) or item["mount-point"] not in allowed) for item in entries):
        raise ValueError("Owned image mountpoint changed")
    volume = _plist(["/usr/sbin/diskutil", "info", "-plist", binding.volume], deadline, observations)
    if volume_binding(volume, binding.registration, binding.name, device) != binding:
        raise ValueError("Owned image complete volume binding changed")
    helper = attachment.get("process-id")
    return {"registration": [list(item) for item in binding.registration], "volume_uuid": binding.uuid,
            "volume": binding.volume, "container": binding.container, "stores": list(binding.stores),
            "helper_pid": helper if type(helper) is int and 0 < helper <= _PID_MAX else None,
            "helper_pid_invalid": "process-id" in attachment and not (type(helper) is int and 0 < helper <= _PID_MAX)}


def observe_busy_image(image: Path | None, device: str, binding: VolumeBinding | None, mountpoints: set[Path],
                       check_image: Callable[[], None]) -> dict:
    """Observe literal registered files only; failures never permit another detach or cleanup.

    A ten-second native-command budget starts after the final exit 16. Recheck the owned file,
    full registration and complete volume binding on both sides. Unelevated lsof is incomplete
    even with no output; neither PIDs nor associations establish the reason for native busy.
    """
    record: dict = {"status": "not-eligible", "incomplete": True, "scope_rechecked": False,
                    "cause_established": False, "native_budget_seconds": _BUDGET, "metadata": []}
    if not _SUPPORTED:
        record["status"] = "unsupported"
        return record
    if not isinstance(binding, VolumeBinding) or not isinstance(image, Path) or not mountpoints:
        return record
    deadline = _CLOCK() + _BUDGET
    stage = "scope-before"
    try:
        check_image()
        record["before"] = _scope(image, device, binding, mountpoints, deadline, record["metadata"])
        check_image()
        stage = "lsof"
        arguments = ["/usr/sbin/lsof", "-nP", "-F0pcftn", "-f", "--", str(image),
                     *(entry[0] for entry in binding.registration)]
        output = _run(arguments, deadline, _OUTPUT_LIMIT)
        record["lsof"] = {**output.summary(), "stdout_base64": base64.b64encode(output.stdout).decode("ascii"),
                          "literal_files": arguments[5:], "field_format": "NUL-separated p,c,f,t,n fields"}
        stage = "scope-after"
        check_image()
        record["after"] = _scope(image, device, binding, mountpoints, deadline, record["metadata"])
        check_image()
        record.update(status="observed", scope_rechecked=True)
    except (OSError, ValueError, RuntimeError, TypeError, OverflowError, subprocess.SubprocessError) as error:
        record.update(status="observation-refused", failed_stage=stage,
                      exception_type=type(error).__name__, error=str(error)[:2048])
    return record
