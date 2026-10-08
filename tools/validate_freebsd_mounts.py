"""Owned nullfs fixtures only in the explicitly disposable FreeBSD CI guest; never a desktop host."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core import freebsd_mounts as native  # noqa: E402
from je_file_tree.core.capacity import capacity_ledger  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.core.mounts import MOUNT_BOUNDARY, MountChangedError, MountSurvey, mount_points  # noqa: E402
from je_file_tree.core.scanner import ScanOptions, scan  # noqa: E402
from je_file_tree.core.snapshot import stat_snapshot  # noqa: E402


def require(condition: bool, detail: str) -> None:
    """Retain the fresh fixture on unknown ownership or native mount metadata."""
    if not condition:
        raise RuntimeError(detail)


def native_info(path: Path) -> native._StatFS:
    """Query a no-follow directory descriptor, not an untrusted device selector."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = native._StatFS()
        require(native._function("fstatfs")(fd, ctypes.byref(info)) == 0, "Native mount metadata unavailable")
        native._check(info)
        return info
    finally:
        os.close(fd)


class OwnedNullFS:
    """Fresh directories only; failed/ambiguous unmount retains all owned fixtures."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="filetree-nullfs-owned-")).resolve(strict=True)
        self.anchor = self.root.stat().st_dev, self.root.stat().st_ino
        self.source, self.target = self.root / "source", self.root / "卷 空白"
        self.source.mkdir(mode=0o700)
        self.target.mkdir(mode=0o700)
        self.source_anchor = self.source.stat().st_dev, self.source.stat().st_ino
        self.target_anchor = self.target.stat().st_dev, self.target.stat().st_ino
        self.payload = self.source / "foreign"
        self.payload.write_bytes(b"new disposable nullfs payload")
        self.payload_anchor = self.payload.stat().st_dev, self.payload.stat().st_ino
        self.original = self.target / "original"
        self.original.write_bytes(b"new disposable underlying payload")
        self.original_anchor = self.original.stat().st_dev, self.original.stat().st_ino
        self.original_digest = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.digest = hashlib.sha256(self.payload.read_bytes()).hexdigest()
        self.mounted, self.attempted = False, False

    def check(self) -> None:
        """Refuse a replaced/linked scratch or changed source before each native operation."""
        info = self.root.lstat()
        require(self.root.is_dir() and not self.root.is_symlink() and not info.st_mode & 0o077
                and (info.st_dev, info.st_ino) == self.anchor, "Owned scratch changed")
        source, payload = self.source.lstat(), self.payload.lstat()
        require(stat.S_ISDIR(source.st_mode) and (source.st_dev, source.st_ino) == self.source_anchor
                and stat.S_ISREG(payload.st_mode) and (payload.st_dev, payload.st_ino) == self.payload_anchor
                and hashlib.sha256(self.payload.read_bytes()).hexdigest() == self.digest, "Owned source changed")

    def mount(self) -> None:
        """Mount only the owned source over its new sibling; no existing mountpoint is accepted."""
        self.check()
        require(not self.attempted and str(self.target) not in mount_points() and not self.target.is_symlink(),
                "Repeated or existing mount refused")
        info = self.target.lstat()
        require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == self.target_anchor,
                "Owned target changed")
        self.attempted = True
        subprocess.run(["/sbin/mount_nullfs", "-o", "ro", str(self.source), str(self.target)],  # noqa: S603 # nosec B603
                       check=True, timeout=30, capture_output=True)
        self.verify_mount()
        self.mounted = True

    def verify_mount(self) -> None:
        """Verify exact native nullfs source, target and distinct mount identity before unmount."""
        self.check()
        info, source = native_info(self.target), native_info(self.source)
        require(info.fs_type == b"nullfs" and os.fsdecode(info.mounted_on) == str(self.target)
                and os.fsdecode(info.mounted_from) == str(self.source)
                and tuple(info.fsid) != tuple(source.fsid), "Owned nullfs identity unavailable")

    def unmount(self) -> None:
        """Never force unmount; the exact native-owned target is the only permitted argument."""
        self.verify_mount()
        subprocess.run(["/sbin/umount", str(self.target)], check=True, timeout=30,  # noqa: S603 # nosec B603
                       capture_output=True)
        require(str(self.target) not in mount_points(), "Owned nullfs is still mounted")
        self.mounted, self.attempted = False, False

    def cleanup(self) -> None:
        """Remove only fresh scratch after native-confirmed unmount and captured identity checks."""
        self.check()
        require(not self.mounted and not self.attempted
                and not any(point.startswith(str(self.root) + "/") or point == str(self.root)
                            for point in mount_points()), "Uncertain mount retained")
        require(not any(path.is_symlink() for path in self.root.rglob("*")), "Linked fixture retained")
        expected = {self.source, self.target, self.payload, self.target / "original"}
        require(set(self.root.rglob("*")) == expected, "Unexpected fixture arrival retained")
        target, original = self.target.lstat(), self.original.lstat()
        require(stat.S_ISDIR(target.st_mode) and (target.st_dev, target.st_ino) == self.target_anchor
                and stat.S_ISREG(original.st_mode) and (original.st_dev, original.st_ino) == self.original_anchor
                and hashlib.sha256(self.original.read_bytes()).hexdigest() == self.original_digest,
                "Underlying owned fixture changed")
        shutil.rmtree(self.root)  # only this tool's identity-checked fresh unmounted scratch


def static_proof(owned: OwnedNullFS) -> dict:
    """Compare one/four workers on real nullfs; retain actual device IDs instead of assuming equality."""
    owned.mount()
    try:
        source_device, target_device = owned.source.stat().st_dev, owned.target.stat().st_dev
        for workers in (1, 4):
            result = scan(owned.root, options=ScanOptions(workers=workers))
            node = next(child for child in result.root.children if child.name == owned.target.name)
            ledger = capacity_ledger(result.root)
            require(node.is_link and node.error == MOUNT_BOUNDARY and not node.children,
                    "Native nullfs traversed")
            require((str(owned.target), MOUNT_BOUNDARY) in result.errors
                    and not ledger.coverage.complete and ledger.unaccounted is None, "False complete mount coverage")
        return {"same_device": source_device == target_device, "source_device": source_device,
                "target_device": target_device, "not_traversed": True, "incomplete": True, "workers": [1, 4]}
    finally:
        if owned.mounted:
            owned.unmount()


def live_proof(owned: OwnedNullFS, *, after_open: bool) -> dict:
    """Mount after survey: refuse before open, or retain original descriptor reads and reject completion."""
    survey = MountSurvey(str(owned.root), stat_snapshot(str(owned.root)), mount_points())
    captured = stat_snapshot(str(owned.target))
    try:
        if after_open:
            with survey.listing(str(owned.target), captured) as entries:
                owned.mount()
                require({entry.name for entry in entries} == {"original"}, "Pinned read followed a new mount")
        else:
            owned.mount()
            try:
                with survey.listing(str(owned.target), captured):
                    raise RuntimeError("Queued read crossed a new mount")
            except MountChangedError:
                pass  # Required refusal, independently of a fresh pathname mount-table survey.
        try:
            survey.verify(mount_points())
            raise RuntimeError("Changed mount namespace published as complete")
        except MountChangedError:
            return {"same_device": owned.source.stat().st_dev == owned.target.stat().st_dev,
                    "completion_refused": True, "original_descriptor_kept": after_open}
    finally:
        if owned.mounted:
            owned.unmount()


def main() -> int:
    """Record every phase atomically; mount failures retain the fresh fixture and fail CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable-vm", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args(sys.argv[1:])
    require(options.disposable_vm and sys.platform.startswith("freebsd") and os.getuid() == 0
            and os.environ.get("FILETREE_DISPOSABLE_FREEBSD_VM") == "1"
            and os.environ.get("GITHUB_ACTIONS") == "true", "Only the explicitly disposable native CI guest is allowed")
    proof: dict = {"phase": "started", "platform": sys.platform, "cleanup_verified": False}
    owned = OwnedNullFS()
    proof["owned_scratch"] = str(owned.root)

    def save() -> None:
        with _atomic_file(options.output) as stream:
            json.dump(proof, stream, ensure_ascii=False, indent=2)

    save()
    try:
        proof["static"] = static_proof(owned)
        proof["phase"] = "static"
        save()
        proof["before_open"] = live_proof(owned, after_open=False)
        proof["phase"] = "before_open"
        save()
        proof["after_open"] = live_proof(owned, after_open=True)
        proof["phase"] = "validated"
        save()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        proof["phase"], proof["error"] = "failed", str(error)
    finally:
        try:
            owned.cleanup()
            proof["cleanup_verified"] = True
            proof["source_preserved"], proof["underlying_preserved"] = True, True
        except (OSError, RuntimeError) as error:
            proof["cleanup_error"] = str(error)
        save()
    if proof["phase"] == "validated" and proof["cleanup_verified"]:
        proof["phase"] = "complete"
        save()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
