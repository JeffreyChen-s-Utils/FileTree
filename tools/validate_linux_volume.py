"""Measure owned ext4 fixtures in a private mount namespace; never use an existing volume or bin."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import secrets
import statistics
import subprocess  # nosec B404 - fixed system programs in a disposable namespace
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.capacity import capacity_ledger  # noqa: E402
from je_file_tree.core.duplicates import estimate_duplicate_savings, find_duplicates  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.core import scanner  # noqa: E402
from je_file_tree.core.mounts import MOUNT_BOUNDARY, MountChangedError, MountSurvey  # noqa: E402
from je_file_tree.core.scanner import ScanOptions, scan  # noqa: E402
from je_file_tree.core.savings import estimate_savings  # noqa: E402
from je_file_tree.core.trash_size import trash_usage  # noqa: E402

_MIB = 1024 * 1024
_BLOCK = 4096
_BIN_SIZE = 65536
_RECOVERY_CASES = 4
_TIMING_FILES = 2000


def require(condition: bool, message: str) -> None:
    """Fail closed: a successful subprocess alone never counts as volume evidence."""
    if not condition:
        raise RuntimeError(message)


def command(arguments: list[str]) -> None:
    """Run a fixed probe program, keeping stdout reserved for the proof JSON."""
    subprocess.run(arguments, check=True, timeout=30, stdout=sys.stderr)  # noqa: S603 # nosec B603


def write_payload(path: Path, size: int, *, sparse: bool = False) -> None:
    """Create and flush a new owned fixture, refusing an existing name."""
    with path.open("xb") as stream:
        if sparse:
            stream.seek(size - _BLOCK)
            stream.write(b"s" * _BLOCK)
        else:
            stream.write(b"p" * size)
        stream.flush()
        os.fsync(stream.fileno())


def available(root: Path) -> int:
    """Flush the disposable filesystem before sampling available bytes."""
    command(["/usr/bin/sync", "-f", str(root)])
    info = os.statvfs(root)
    return info.f_bavail * info.f_frsize


def fixtures(root: Path) -> dict[str, Path]:
    """Create regular, hard-linked, sparse, duplicate and freedesktop-bin fixtures."""
    paths = {name: root / name for name in ("plain", "alias", "copy", "sparse")}
    write_payload(paths["plain"], _MIB)
    os.link(paths["plain"], paths["alias"])
    write_payload(paths["copy"], _MIB)
    write_payload(paths["sparse"], 16 * _MIB, sparse=True)
    payloads, receipts = root / ".Trash-0" / "files", root / ".Trash-0" / "info"
    payloads.mkdir(parents=True)
    receipts.mkdir()
    paths["bin"] = payloads / "owned-payload"
    write_payload(paths["bin"], _BIN_SIZE)
    receipt = receipts / "owned-payload.trashinfo"
    receipt.write_text("[Trash Info]\nPath=/owned-fixture\nDeletionDate=2026-10-07T00:00:00\n", encoding="utf-8")
    return paths


def ledger_proof(root: Path, paths: dict[str, Path]) -> dict[str, object]:
    """Compare allocation, reservations and bin scopes with actual ext4 stat values."""
    result = scan(root, options=ScanOptions(workers=1))
    require(not result.errors, "Unexpected scan errors on the isolated volume")
    ledger = capacity_ledger(result.root)
    info = os.statvfs(root)
    file_paths = [Path(node.path) for node in result.root.iter_files()]
    named = sum(path.stat().st_blocks * 512 for path in file_paths)
    unique = {}
    for path in file_paths:
        identity = path.stat()
        unique[(identity.st_dev, identity.st_ino)] = identity.st_blocks * 512
    require(ledger.status == "estimated", "Whole ext4 volume did not yield an estimated ledger")
    require(ledger.total == info.f_blocks * info.f_frsize, "OS total differs from statvfs")
    require(ledger.used == (info.f_blocks - info.f_bfree) * info.f_frsize, "OS used differs from statvfs")
    require(ledger.free == info.f_bavail * info.f_frsize, "OS available differs from statvfs")
    reserved = (info.f_bfree - info.f_bavail) * info.f_frsize
    require(ledger.unavailable_free == reserved and reserved > 0, "Reserved blocks were not distinguished")
    require(ledger.named_allocated == named and ledger.unique_allocated == sum(unique.values()),
            "File allocation differs from st_blocks or hard-link identities")
    require(ledger.hard_link_overcount == paths["plain"].stat().st_blocks * 512,
            "Hard-link overcount differs from the file allocation")
    bin_files = [path for path in file_paths if ".Trash-0" in path.parts]
    bin_allocated = sum(path.stat().st_blocks * 512 for path in bin_files)
    inventory = trash_usage(str(root))
    require(inventory is not None and inventory.complete and inventory.count == 1 and inventory.size == _BIN_SIZE,
            "Native freedesktop inventory did not match the owned logical payload")
    require(ledger.recycle_bin_complete and ledger.recycle_bin_seen == bin_allocated,
            "Ledger bin allocation did not include payload and receipt files exactly once")
    require(ledger.metadata_bytes is None and ledger.omitted_bytes is None and ledger.other_volumes_bytes is None,
            "Unmeasured filesystem buckets must remain unknown")
    recorded = asdict(ledger)
    recorded["coverage"]["unsafe_folders"] = len(recorded["coverage"].pop("unsafe"))
    return {"ledger": recorded, "statvfs_reserved": reserved, "bin_inventory": asdict(inventory),
            "bin_allocated_including_receipt": bin_allocated, "bin_scopes_differ": True}


def recovery_proof(root: Path, paths: dict[str, Path]) -> list[dict[str, object]]:
    """Unlink only fixtures just created by this probe and compare actual free-space changes."""
    evidence = []
    for label, names in (("duplicate_copy", ("copy",)), ("first_hard_link", ("alias",)),
                         ("last_hard_link", ("plain",)), ("sparse_file", ("sparse",))):
        tree = scan(root, options=ScanOptions(workers=1)).root
        nodes = {node.name: node for node in tree.iter_files()}
        selected = [nodes[name] for name in names]
        estimate = estimate_savings(selected, root=tree)
        require(estimate is not None and estimate.recoverable_max is not None, "Missing recovery estimate")
        if label == "duplicate_copy":
            groups = find_duplicates(tree, min_size=1, workers=1).groups
            require(len(groups) == 1, "Hard-linked names must not become independent duplicate copies")
            keeper = next(node for node in groups[0].files if node.name != "copy")
            estimates = estimate_duplicate_savings([replace(groups[0], kept=keeper)], tree)
            require(estimates is not None and estimates.total.recoverable_max == estimate.recoverable_max,
                    "Review and Duplicates recovery estimates disagree")
        before = available(root)
        for name in names:
            paths[name].unlink()  # only this probe's explicitly created disposable files
        recovered = available(root) - before
        require(recovered == estimate.recoverable_max, f"ext4 {label} recovery differs from its upper estimate")
        evidence.append({"case": label, "estimate": asdict(estimate), "measured_free_change": recovered})
    return evidence


def bind_proof(root: Path) -> dict[str, object]:
    """Verify a real same-device bind mount is listed but never traversed or treated as empty."""
    source, target = root / "owned-source", root / "owned-bind"
    source.mkdir()
    target.mkdir()
    write_payload(source / "payload", _BLOCK)
    command(["/usr/bin/mount", "--bind", str(source), str(target)])
    try:
        result = scan(root, options=ScanOptions(workers=1))
        node = next(child for child in result.root.children if child.name == target.name)
        ledger = capacity_ledger(result.root)
        require(source.stat().st_dev == target.stat().st_dev, "Bind fixture is not on the same device")
        require(node.is_link and node.error == MOUNT_BOUNDARY and not node.children,
                "A real same-device bind mount was traversed")
        require(ledger.mounted_folders == 1 and not ledger.coverage.complete and ledger.unaccounted is None,
                "Excluded mount incorrectly produced complete capacity coverage")
        require((str(target), MOUNT_BOUNDARY) in result.errors, "Mount omission was not reported")
        return {"same_device": True, "not_traversed": True, "incomplete": True, "mounted_folders": 1}
    finally:
        command(["/usr/bin/umount", str(target)])


def live_bind_proof(root: Path) -> dict[str, object]:
    """Mount after the initial survey, before and after a queued folder is opened."""
    source, target = root / "live-source", root / "live-target"
    source.mkdir()
    target.mkdir()
    write_payload(source / "foreign", _BLOCK * 2)
    write_payload(target / "original", _BLOCK)
    return {"before_open": _live_before(root, source, target),
            "after_open": _live_after(root, source, target)}


def _live_before(root: Path, source: Path, target: Path) -> dict[str, object]:
    original, mounted = scanner._read_folder, False

    def changed(folder, path, *args):
        nonlocal mounted
        if path == str(target):
            command(["/usr/bin/mount", "--bind", str(source), str(target)])
            mounted = True
        return original(folder, path, *args)

    try:
        with patch.object(scanner, "_read_folder", changed):
            try:
                scan(root, options=ScanOptions(workers=1))
            except MountChangedError:
                require(mounted, "Live bind was never created")
                return {"same_device": source.stat().st_dev == target.stat().st_dev,
                        "completed_result_refused": True}
            raise RuntimeError("New same-device bind mount was traversed")
    finally:
        if mounted:
            command(["/usr/bin/umount", str(target)])


def _live_after(root: Path, source: Path, target: Path) -> dict[str, object]:
    original, mounted, inspected = MountSurvey.listing, False, []

    @contextmanager
    def changed(survey, path, snapshot):
        nonlocal mounted
        with original(survey, path, snapshot) as entries:
            listing = entries
            if path == str(target):
                command(["/usr/bin/mount", "--bind", str(source), str(target)])
                mounted = True
                listing = list(entries)
                inspected.extend((entry.name, entry.stat(follow_symlinks=False).st_size) for entry in listing)
            yield listing

    try:
        with patch.object(MountSurvey, "listing", changed):
            try:
                scan(root, options=ScanOptions(workers=1))
            except MountChangedError:
                require(mounted and inspected == [("original", _BLOCK)], "Folder read crossed the new live bind")
                return {"original_metadata_pinned": True, "completed_result_refused": True}
            raise RuntimeError("Changed mount table produced a completed scan")
    finally:
        if mounted:
            command(["/usr/bin/umount", str(target)])


def descriptor_cost(root: Path) -> dict[str, object]:
    """Measure guarded versus path-based folder reads on the same warm-cache owned fixture."""
    selected = root / "timing"
    selected.mkdir()
    for number in range(1000):
        folder = selected / str(number)
        folder.mkdir()
        for name in ("a", "b"):
            (folder / name).write_bytes(b"x")

    @contextmanager
    def path_listing(_survey, path, _snapshot):
        with os.scandir(path) as entries:
            yield entries

    measurements = {}
    for workers in (1, 4):
        times = {"guarded": [], "path_based": []}
        for _repeat in range(5):
            for label, samples in times.items():
                context = (patch.object(MountSurvey, "listing", path_listing) if label == "path_based"
                           else patch.object(MountSurvey, "listing", MountSurvey.listing))
                with context:
                    started = time.monotonic()
                    result = scan(selected, options=ScanOptions(workers=workers))
                    samples.append(time.monotonic() - started)
                    require(not result.errors and result.root.file_count == _TIMING_FILES
                            and result.root.size == _TIMING_FILES,
                            "Descriptor timing scan did not match the fixture")
        measurements[str(workers)] = {label: statistics.median(values) for label, values in times.items()}
    return {"folders": 1001, "files": 2000, "repeats": 5, "median_seconds_by_workers": measurements,
            "comparison": "Only folder listing strategy differs; both retain initial/final mount surveys."}


def probe(scratch: Path, token: str) -> dict[str, object]:
    """Refuse foreign directories or the host namespace before creating a disposable image."""
    require(sys.platform.startswith("linux") and os.geteuid() == 0, "Requires Linux namespace privileges")
    require(not scratch.is_symlink() and scratch.name.startswith("filetree-volume-"), "Not an owned scratch root")
    owner = json.loads((scratch / "owner.json").read_text(encoding="utf-8"))
    require(owner["token"] == token and scratch.stat().st_uid == owner["uid"], "Scratch ownership mismatch")
    require(os.readlink("/proc/self/ns/mnt") != owner["namespace"], "Refusing the host mount namespace")
    require({path.name for path in scratch.iterdir()} == {"owner.json"}, "Scratch directory is not fresh")
    home = scratch / "home"
    home.mkdir()
    os.environ.update(HOME=str(home), XDG_DATA_HOME=str(home / "data"))
    image, root = scratch / "owned.ext4", scratch / "mounted"
    with image.open("xb") as stream:
        stream.truncate(64 * _MIB)
    root.mkdir()
    command(["/usr/sbin/mkfs.ext4", "-F", "-q", "-b", str(_BLOCK), "-m", "10", "-E",
             "lazy_itable_init=0,lazy_journal_init=0", str(image)])
    command(["/usr/bin/mount", "-o", "loop,nodev,nosuid,noexec", str(image), str(root)])
    try:
        paths = fixtures(root)
        available(root)
        return {"filesystem": "ext4", "private_namespace": True, "owned_image_bytes": 64 * _MIB,
                "capacity": ledger_proof(root, paths), "recovery": recovery_proof(root, paths),
                "bind_mount": bind_proof(root), "live_bind_mount": live_bind_proof(root),
                "descriptor_cost": descriptor_cost(root),
                "unverified": ["compression", "cloud_placeholders", "NTFS", "APFS", "shared_extents"]}
    finally:
        command(["/usr/bin/umount", str(root)])


def main() -> int:
    """Launch only a fresh owned image; preserve complete proof after the namespace has exited."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path("volume-evidence"))
    parser.add_argument("--probe", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--token", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe is not None:
        sys.stdout.write(json.dumps(probe(args.probe, args.token), ensure_ascii=False) + "\n")
        return 0
    require(sys.platform.startswith("linux"), "This probe runs on Linux only")
    with tempfile.TemporaryDirectory(prefix="filetree-volume-") as temporary:
        scratch, token = Path(temporary), secrets.token_hex(24)
        owner = {"token": token, "uid": os.getuid(), "namespace": os.readlink("/proc/self/ns/mnt")}
        (scratch / "owner.json").write_text(json.dumps(owner), encoding="utf-8")
        arguments = ["/usr/bin/sudo", "-n", "/usr/bin/unshare", "--mount", "--propagation", "private",
                     sys.executable, str(Path(__file__).resolve()), "--probe", str(scratch), "--token", token]
        result = subprocess.run(  # noqa: S603 # nosec B603
            arguments, check=True, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        proof = json.loads(result.stdout)
    require(proof.get("private_namespace") and len(proof.get("recovery", [])) == _RECOVERY_CASES
            and proof.get("bind_mount") and proof.get("live_bind_mount") and proof.get("descriptor_cost"),
            "Incomplete ext4 volume proof")
    args.evidence.mkdir(parents=True, exist_ok=True)
    with _atomic_file(args.evidence / "proof.json", encoding="utf-8") as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    sys.stdout.write("Owned ext4 capacity, recovery and bind-mount checks passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
