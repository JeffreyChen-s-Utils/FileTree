"""Fresh UUID APFS image ownership; never attach, format or detach an existing selected volume."""

from __future__ import annotations

import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid

from tools.macos_detach_identity import VolumeBinding, registration, volume_binding
from tools.macos_busy_observer import observe_busy_image, refusal_log

_PLIST_LIMIT = 8 * 1024 * 1024
_DEVICE = re.compile(r"/dev/disk[0-9]+\Z")
_DETACH_ATTEMPTS = 3
_DEVICE_BUSY = 16
_NATIVE_ERROR_LIMIT = 65536
_VOLUME_DEVICE = re.compile(r"/dev/disk[0-9]+(?:s[0-9]+)+\Z")
_EVIDENCE_STRING_LIMIT = 512
_EVIDENCE_ENTITIES = 64
_EVIDENCE_STORES = 8
_DEVICE_NAME_LIMIT = 128
_EVIDENCE_INT_BITS = 128
_IDENTITY_PARTS = 2
_VOLUME_FIELDS = ("DeviceIdentifier", "DeviceNode", "VolumeUUID", "DiskUUID", "VolumeName", "FilesystemType",
                  "MountPoint", "Mounted", "ParentWholeDisk", "APFSContainerReference")


def entities(value: dict) -> list[dict]:
    """Reject malformed native entity lists rather than selecting a guessed device."""
    result = value.get("system-entities")
    require(isinstance(result, list) and all(isinstance(entry, dict) for entry in result),
            "Invalid image device metadata")
    return result


def image_device(value: dict) -> str:
    """Select the partition-map image device, never its separate synthesized APFS container."""
    devices = [entry["dev-entry"] for entry in entities(value)
               if isinstance(entry.get("dev-entry"), str) and _DEVICE.fullmatch(entry["dev-entry"])
               and entry.get("content-hint") in ("GUID_partition_scheme", "Apple_partition_scheme")]
    require(len(devices) == 1, "Image whole-device ownership is ambiguous")
    return devices[0]


def require(condition: bool, detail: str) -> None:
    """Refuse uncertain ownership and retain the fresh fixture rather than targeting another device."""
    if not condition:
        raise RuntimeError(detail)


def command(arguments: list[str]) -> bytes:
    """Fixed native programs only, no shell, with bounded accepted output and a joined timeout."""
    require(arguments[0] in ("/usr/bin/hdiutil", "/usr/sbin/diskutil", "/usr/bin/ditto", "/bin/sync"),
            "Unsupported owned-image program")
    result = subprocess.run(arguments, check=True, timeout=60, capture_output=True)  # noqa: S603 # nosec B603
    require(len(result.stdout) <= _PLIST_LIMIT and len(result.stderr) <= _PLIST_LIMIT, "Oversized native metadata")
    return result.stdout


def plist(arguments: list[str]) -> dict:
    """Decode native structured metadata; human-readable command text is never device authority."""
    value = plistlib.loads(command(arguments))
    require(isinstance(value, dict), "Invalid native image metadata")
    return value


def native_failure(error: subprocess.CalledProcessError) -> dict[str, object]:
    """Retain bounded native failure output even when a later ownership check refuses cleanup."""
    return {"returncode": error.returncode,
            "stdout": (error.stdout or b"")[:_NATIVE_ERROR_LIMIT].decode("utf-8", errors="replace"),
            "stderr": (error.stderr or b"")[:_NATIVE_ERROR_LIMIT].decode("utf-8", errors="replace")}


def _detach_failure(record: dict[str, object], phase: str, error: Exception) -> None:
    record.update(phase=phase, error=str(error)[:2048])
    if isinstance(error, subprocess.CalledProcessError):
        record["native_error"] = native_failure(error)


def _mountpoint_diagnostic(entries: list[dict], allowed: set[Path]) -> str:
    observed = "; ".join(str(entry.get("dev-entry", "<missing>"))[:128] + " -> "
                         + str(entry.get("mount-point", "<unmounted>"))[:512] for entry in entries[:8])
    expected = "; ".join(str(path)[:512] for path in sorted(allowed)[:8])
    return (f"Image escaped the private fixture mountpoint; observed [{observed}] "
            f"({len(entries)} entities); allowed [{expected}] ({len(allowed)} paths)")


def _evidence_fields(value: dict, names: tuple[str, ...]) -> dict:
    result, truncated = {}, []
    for name in names:
        if name not in value:
            continue
        item = value[name]
        if isinstance(item, str):
            result[name] = item[:_EVIDENCE_STRING_LIMIT]
            if len(item) > _EVIDENCE_STRING_LIMIT:
                truncated.append(name)
        elif item is None or type(item) is bool or type(item) is int and item.bit_length() <= _EVIDENCE_INT_BITS:
            result[name] = item
        else:
            result[name] = {"invalid_type": type(item).__name__}
    if truncated:
        result["truncated_fields"] = truncated
    return result


def _attachment_evidence(value: dict) -> dict:
    entries = entities(value)
    return {"image": _evidence_fields(value, ("image-path",)), "entity_count": len(entries),
            "entities_truncated": len(entries) > _EVIDENCE_ENTITIES,
            "entities": [_evidence_fields(entry, ("dev-entry", "content-hint", "mount-point"))
                         for entry in entries[:_EVIDENCE_ENTITIES]]}


def _identity_evidence(value: object) -> list[int] | None:
    if (isinstance(value, tuple) and len(value) == _IDENTITY_PARTS
            and all(type(item) is int and item >= 0 and item.bit_length() <= _EVIDENCE_INT_BITS for item in value)):
        return list(value)
    return None


def _volume_evidence(value: dict) -> dict:
    result = _evidence_fields(value, _VOLUME_FIELDS)
    if "APFSPhysicalStores" in value:
        stores = value["APFSPhysicalStores"]
        if isinstance(stores, list):
            result.update(physical_store_count=len(stores), physical_stores_truncated=len(stores) > _EVIDENCE_STORES,
                          APFSPhysicalStores=[_evidence_fields(item, ("APFSPhysicalStore",)) if isinstance(item, dict)
                                              else {"invalid_type": type(item).__name__}
                                              for item in stores[:_EVIDENCE_STORES]])
        else:
            result["APFSPhysicalStores"] = {"invalid_type": type(stores).__name__}
    return result


class OwnedImage:
    """Only one freshly created private image/device; uncertain detach leaves the scratch directory intact."""

    def __init__(self) -> None:
        if sys.platform != "darwin" or not os.getuid() or os.geteuid() != os.getuid():
            raise ValueError("Owned APFS validation requires unelevated native macOS")
        self.owned = Path(tempfile.mkdtemp(prefix="filetree-apfs-owned-")).resolve(strict=True)
        self.anchor = self.owned.stat().st_dev, self.owned.stat().st_ino
        self.name = "FileTree-" + uuid.uuid4().hex
        self.image = self.owned / (self.name + ".sparseimage")
        self.root = self.owned / "volume"
        self.root.mkdir(mode=0o700)
        self._mountpoints = {self.root}
        self.identity: tuple[int, int] | None = None
        self.device, self.volume_uuid = "", ""
        self.attached = False
        self.attach_attempted = False
        self.detach_attempts: list[dict[str, object]] = []
        self._volume_device = ""
        self._attachment_evidence: dict | None = None
        self._checked_volume_evidence: dict | None = None
        self._unmounted_volume_device: str | None = None
        self._detach_binding: VolumeBinding | None = None
        self._unmounted_binding: VolumeBinding | None = None
        self._registered_entities: tuple[tuple[str, str], ...] | None = None
        self._wholly_unmounted = False

    def create(self) -> None:
        """Refuse overwrite: no -ov, existing image, mountpoint or block-device selector is accepted."""
        require(not self.image.exists() and not os.path.ismount(self.root), "Existing fixture target refused")
        command(["/usr/bin/hdiutil", "create", "-size", "1g", "-type", "SPARSE", "-fs", "APFS",
                 "-volname", self.name, str(self.image)])
        info = self.image.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1,
                "Created image is not an owned ordinary file")
        self.identity = info.st_dev, info.st_ino
        self.image.chmod(0o600)

    def _image_check(self) -> None:
        self._scratch_check()
        info = self.image.lstat()
        require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o077 and info.st_uid == os.getuid()
                and info.st_nlink == 1 and (info.st_dev, info.st_ino) == self.identity,
                "Owned image identity/permissions changed")
    def _scratch_check(self) -> None:
        anchor = self.owned.lstat()
        require(stat.S_ISDIR(anchor.st_mode) and not anchor.st_mode & 0o077 and anchor.st_uid == os.getuid()
                and (anchor.st_dev, anchor.st_ino) == self.anchor, "Owned scratch directory changed")

    def attach(self) -> None:
        """Mount only this freshly created image at its exclusive private mountpoint."""
        self._image_check()
        require(not self.attach_attempted and not os.path.ismount(self.root), "Repeated or existing attach refused")
        self.attach_attempted = True
        result = plist(["/usr/bin/hdiutil", "attach", "-plist", "-nobrowse", "-noautoopen", "-owners", "on",
                        "-mountpoint", str(self.root), str(self.image)])
        self.device, self.attached = image_device(result), True
        info = self.check()
        self.volume_uuid = info["VolumeUUID"]

    def _registered_attachment(self) -> dict:
        self._attachment_evidence = None
        self._unmounted_volume_device = None
        self._registered_entities = None
        self._unmounted_binding = None
        self._wholly_unmounted = False
        self._image_check()
        info = plist(["/usr/bin/hdiutil", "info", "-plist"])
        images = [entry for entry in info.get("images", []) if isinstance(entry, dict)
                  and entry.get("image-path") == str(self.image)]
        require(len(images) == 1, "Fresh image attachment is missing or ambiguous")
        entries = entities(images[0])
        self._attachment_evidence = _attachment_evidence(images[0])
        self._attachment_evidence.update(captured_image_identity=_identity_evidence(getattr(self, "identity", None)),
                                         captured_scratch_identity=_identity_evidence(getattr(self, "anchor", None)))
        require(image_device(images[0]) == self.device, "Owned image device changed")
        self._registered_entities = registration(entries)
        self._wholly_unmounted = all(entry.get("mount-point") is None
                                    or type(entry.get("mount-point")) is str and entry["mount-point"] == ""
                                    for entry in entries)
        return images[0]

    def _attachment(self) -> dict:
        image = self._registered_attachment()
        entries = entities(image)
        points = [entry["mount-point"] for entry in entries if entry.get("mount-point")]
        captured = getattr(self, "_volume_device", "")
        if (not points and isinstance(captured, str) and len(captured) <= _DEVICE_NAME_LIMIT
                and _VOLUME_DEVICE.fullmatch(captured)
                and sum(entry.get("dev-entry") == captured for entry in entries) == 1):
            self._unmounted_volume_device = captured
        if not points or not all(isinstance(point, str) and Path(point).resolve() in self._mountpoints
                                 for point in points):
            raise RuntimeError(_mountpoint_diagnostic(entries, self._mountpoints))
        return image

    def new_mountpoint(self) -> Path:
        """Register only a fresh private sibling for this image's additional owned APFS volume."""
        self.check()
        path = self.owned / ("peer-" + uuid.uuid4().hex)
        path.mkdir(mode=0o700)
        self._mountpoints.add(path)
        return path

    def check(self) -> dict:
        """Check image/device mapping, APFS identity and the exact private volume name/mountpoint."""
        require(self.attached, "Owned image is not attached")
        attachment = self._attachment()
        info = plist(["/usr/sbin/diskutil", "info", "-plist", str(self.root)])
        require(info.get("FilesystemType") == "apfs" and info.get("VolumeName") == self.name
                and info.get("MountPoint") == str(self.root) and os.path.ismount(self.root)
                and isinstance(info.get("VolumeUUID"), str) and bool(info["VolumeUUID"]),
                "Private APFS volume identity is unavailable")
        require(not self.volume_uuid or info["VolumeUUID"] == self.volume_uuid, "Private APFS volume was replaced")
        self._checked_volume_evidence = _volume_evidence(info)
        self._detach_binding = volume_binding(info, self._registered_entities, self.name, self.device)
        identifier = info.get("DeviceIdentifier")
        candidate = "/dev/" + identifier if isinstance(identifier, str) else ""
        if (not getattr(self, "_volume_device", "") and len(candidate) <= _DEVICE_NAME_LIMIT
                and _VOLUME_DEVICE.fullmatch(candidate)
                and sum(entry.get("dev-entry") == candidate for entry in entities(attachment)) == 1
                and any(entry.get("dev-entry") == candidate and entry.get("mount-point") == str(self.root)
                        for entry in entities(attachment))):
            self._volume_device = candidate
        return info

    def _post_busy_volume_evidence(self) -> dict:
        """Observe only the captured volume still uniquely registered in the checked unmounted image."""
        device = self._unmounted_volume_device
        captured = getattr(self, "_volume_device", None)
        expected = getattr(self, "volume_uuid", "")
        result = {"status": "not-eligible",
                  "device": device[:_DEVICE_NAME_LIMIT] if isinstance(device, str) else None,
                  "device_truncated": isinstance(device, str) and len(device) > _DEVICE_NAME_LIMIT,
                  "captured_device": captured[:_DEVICE_NAME_LIMIT] if isinstance(captured, str) else None,
                  "captured_device_truncated": isinstance(captured, str) and len(captured) > _DEVICE_NAME_LIMIT,
                  "expected_uuid": expected[:_EVIDENCE_STRING_LIMIT] if isinstance(expected, str) else None,
                  "expected_uuid_truncated": isinstance(expected, str) and len(expected) > _EVIDENCE_STRING_LIMIT,
                  "uuid_matches": None}
        if (not isinstance(device, str) or len(device) > _DEVICE_NAME_LIMIT or not _VOLUME_DEVICE.fullmatch(device)
                or device != captured or not isinstance(expected, str) or not expected):
            return result
        try:
            info = plist(["/usr/sbin/diskutil", "info", "-plist", device])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            result.update(status="read-failed", error=str(error)[:2048], exception_type=type(error).__name__)
            if isinstance(error, subprocess.CalledProcessError):
                result["native_error"] = native_failure(error)
            elif isinstance(error, subprocess.TimeoutExpired):
                result["timeout_seconds"] = error.timeout
                result["outputs"] = {key: (getattr(error, key, None) or b"")[:_NATIVE_ERROR_LIMIT]
                                     .decode("utf-8", errors="replace") for key in ("stdout", "stderr")}
        else:
            observed = info.get("VolumeUUID")
            matches = observed == expected if isinstance(observed, str) and observed else None
            result.update(status="read", info=_volume_evidence(info), uuid_matches=matches)
            if (getattr(self, "_wholly_unmounted", False)
                    and info.get("MountPoint") in (None, "")
                    and (info.get("Mounted") is None or info.get("Mounted") is False)):
                self._unmounted_binding = volume_binding(info, self._registered_entities, self.name, self.device)
        return result

    def _record_detach_observations(self, record: dict, *, post_busy: bool = False) -> None:
        record["attachment"] = self._attachment_evidence
        record["checked_volume"] = self._checked_volume_evidence
        if post_busy:
            record["post_busy_volume"] = self._post_busy_volume_evidence()

    def _check_detach(self, record: dict, previous_busy: bool) -> None:
        expected = getattr(self, "_detach_binding", None)
        try:
            self.check()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            self._record_detach_observations(record, post_busy=previous_busy)
            if (not previous_busy or expected is None or self._unmounted_binding != expected
                    or self._unmounted_volume_device != expected.volume):
                raise
            self._registered_attachment()
            require(self._wholly_unmounted and self._registered_entities == expected.registration,
                    "Owned image registration changed during detach recovery")
            self._image_check()
            require(not any(os.path.ismount(point) for point in self._mountpoints),
                    "Owned mountpoint became mounted during detach recovery")
            record.update(mounted_check_error=str(error)[:2048], unmounted_identity_rechecked=True,
                          rechecked_attachment=self._attachment_evidence)
        else:
            self._record_detach_observations(record)

    def detach(self) -> None:
        """Bound checked verbose detach attempts; retain native output and any later refusal."""
        self.detach_attempts = []
        self._first_busy = None
        for attempt in range(_DETACH_ATTEMPTS):
            record: dict[str, object] = {"attempt": attempt + 1, "device": self.device, "phase": "checking"}
            self.detach_attempts.append(record)
            self._attachment_evidence = self._checked_volume_evidence = self._unmounted_volume_device = None
            self._unmounted_binding = None
            previous_busy = bool(attempt and self.detach_attempts[-2].get("native_error", {})
                                 .get("returncode") == _DEVICE_BUSY)
            try:
                self._check_detach(record, previous_busy)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                _detach_failure(record, "ownership-refused", error)
                self._record_refusal_log(record)
                raise
            try:
                output = command(["/usr/bin/hdiutil", "detach", "-verbose", self.device])
                record["native_stdout"] = output[:_NATIVE_ERROR_LIMIT].decode("utf-8", errors="replace")
                record["native_stdout_truncated"] = len(output) > _NATIVE_ERROR_LIMIT
            except subprocess.CalledProcessError as error:
                _detach_failure(record, "native-refused", error)
                if error.returncode == _DEVICE_BUSY and self._first_busy is None:
                    self._first_busy = time.time()
                if error.returncode != _DEVICE_BUSY or attempt == _DETACH_ATTEMPTS - 1:
                    if error.returncode == _DEVICE_BUSY:
                        record["busy_observation"] = observe_busy_image(
                            getattr(self, "image", None), self.device, getattr(self, "_detach_binding", None),
                            getattr(self, "_mountpoints", set()), self._image_check)
                    self._record_refusal_log(record)
                    raise
                delay = .5 * (attempt + 1)
                record["retry_delay_seconds"] = delay
                time.sleep(delay)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                _detach_failure(record, "native-refused", error)
                raise
            else:
                record["phase"] = "native-succeeded"
                record["native_succeeded"] = True
                break
        try:
            info = plist(["/usr/bin/hdiutil", "info", "-plist"])
            require(not any(entry.get("image-path") == str(self.image) for entry in info.get("images", []))
                    and not os.path.ismount(self.root), "Owned image detach was not verified")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            _detach_failure(record, "verification-refused", error)
            raise
        record["phase"] = "verified"
        self.attached = False
        self._record_refusal_log(record)

    def _record_refusal_log(self, record: dict) -> None:
        """After the attempts end, keep DiskArbitration's account of any busy refusal in this detach."""
        if getattr(self, "_first_busy", None) is not None:
            record["refusal_log"] = refusal_log(self.device, self._first_busy, time.time())

    def cleanup(self) -> None:
        """Remove disposable fixture metadata only after verified detach; uncertain attachments are retained."""
        require(not self.attached and (not self.attach_attempted or bool(self.device)),
                "Uncertain image attachment retained")
        self._scratch_check()
        if self.identity is not None:
            self._image_check()
        for folder, directories, _files in os.walk(self.owned, followlinks=False):
            require(not os.path.ismount(folder), "Mounted fixture directory retained")
            for name in directories:
                require(not os.path.islink(os.path.join(folder, name)), "Linked fixture directory retained")
        shutil.rmtree(self.owned)
