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
import uuid

_PLIST_LIMIT = 8 * 1024 * 1024
_DEVICE = re.compile(r"/dev/disk[0-9]+\Z")


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

    def _attachment(self) -> dict:
        self._image_check()
        info = plist(["/usr/bin/hdiutil", "info", "-plist"])
        images = [entry for entry in info.get("images", []) if isinstance(entry, dict)
                  and entry.get("image-path") == str(self.image)]
        require(len(images) == 1, "Fresh image attachment is missing or ambiguous")
        entries = entities(images[0])
        require(image_device(images[0]) == self.device, "Owned image device changed")
        points = [entry["mount-point"] for entry in entries if entry.get("mount-point")]
        require(points and all(isinstance(point, str) and Path(point).resolve() in self._mountpoints
                               for point in points),
                "Image escaped the private fixture mountpoint")
        return images[0]

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
        self._attachment()
        info = plist(["/usr/sbin/diskutil", "info", "-plist", str(self.root)])
        require(info.get("FilesystemType") == "apfs" and info.get("VolumeName") == self.name
                and info.get("MountPoint") == str(self.root) and os.path.ismount(self.root)
                and isinstance(info.get("VolumeUUID"), str) and bool(info["VolumeUUID"]),
                "Private APFS volume identity is unavailable")
        require(not self.volume_uuid or info["VolumeUUID"] == self.volume_uuid, "Private APFS volume was replaced")
        return info

    def detach(self) -> None:
        """Recheck and detach only the exact owned image device; never force-unmount other sources."""
        self.check()
        command(["/usr/bin/hdiutil", "detach", self.device])
        info = plist(["/usr/bin/hdiutil", "info", "-plist"])
        require(not any(entry.get("image-path") == str(self.image) for entry in info.get("images", []))
                and not os.path.ismount(self.root), "Owned image detach was not verified")
        self.attached = False

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
