"""Native APFS evidence on one fresh owned image; no Finder automation or existing user bin."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import ctypes
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.capacity import capacity_ledger  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.core.scanner import ScanOptions, scan  # noqa: E402
from je_file_tree.core.savings import estimate_savings  # noqa: E402
from je_file_tree.core.trash_size import trash_usage  # noqa: E402
from tools.macos_owned_image import OwnedImage, command, require  # noqa: E402
from tools.volume_evidence import ledger_record  # noqa: E402

_MIB = 1024 * 1024
_BLOCK = 4096
_BIN_BYTES = 65536


def write_payload(path: Path, size: int, *, sparse: bool = False) -> None:
    """Create and flush only an exclusive disposable fixture."""
    with path.open("xb") as stream:
        if sparse:
            stream.seek(size - _BLOCK)
            stream.write(b"s" * _BLOCK)
        else:
            stream.write(b"p" * size)
        stream.flush()
        os.fsync(stream.fileno())


def file_record(path: Path) -> dict[str, object]:
    """Hash complete owned payloads and retain native allocation and identity separately."""
    with path.open("rb") as stream:
        info = os.fstat(stream.fileno())
        digest = hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else (
            hashlib.sha256(stream.read()).hexdigest())
    return {"identity": [info.st_dev, info.st_ino], "links": info.st_nlink, "logical": info.st_size,
            "allocated": info.st_blocks * 512, "flags": info.st_flags, "sha256": digest}


def fixtures(image: OwnedImage) -> dict[str, Path]:
    """Create native hard links, sparse/ditto-compressed data, clonefile data and a private uid bin."""
    image.check()
    folder = image.root / "owned-fixtures"
    folder.mkdir(mode=0o700)
    paths = {name: folder / name for name in
             ("plain", "alias", "all-a", "all-b", "sparse", "compression-source", "compressed", "clone")}
    for name in ("plain", "all-a", "compression-source"):
        write_payload(paths[name], 8 * _MIB)
    os.link(paths["plain"], paths["alias"])
    os.link(paths["all-a"], paths["all-b"])
    write_payload(paths["sparse"], 32 * _MIB, sparse=True)
    command(["/usr/bin/ditto", "--hfsCompression", str(paths["compression-source"]), str(paths["compressed"])])
    library = ctypes.CDLL(None, use_errno=True)
    library.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    library.clonefile.restype = ctypes.c_int
    if library.clonefile(os.fsencode(paths["compression-source"]), os.fsencode(paths["clone"]), 0):
        raise OSError(ctypes.get_errno(), "Native owned APFS clonefile failed")
    bins = image.root / ".Trashes"
    if not bins.exists():
        bins.mkdir(mode=0o700)
    info = bins.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_dev == image.root.stat().st_dev, "Unsafe private bin parent")
    scope = bins / str(os.getuid())
    scope.mkdir(mode=0o700)
    paths["bin"] = scope / "owned-payload"
    write_payload(paths["bin"], _BIN_BYTES)
    records = {name: file_record(path) for name, path in paths.items()}
    require(records["sparse"]["allocated"] < records["sparse"]["logical"], "Native sparse allocation unavailable")
    require(records["compressed"]["flags"] & stat.UF_COMPRESSED
            and records["compressed"]["allocated"] < records["compressed"]["logical"],
            "Native compression was not verified")
    require(records["clone"]["identity"] != records["compression-source"]["identity"]
            and records["clone"]["sha256"] == records["compression-source"]["sha256"], "Native clone differs")
    return paths


def os_capacity(root: Path) -> dict[str, int]:
    """Native fragment counts; APFS container sharing is not independent reserved-byte measurement."""
    info = os.statvfs(root)
    return {"total": info.f_blocks * info.f_frsize,
            "used": (info.f_blocks - info.f_bfree) * info.f_frsize,
            "free": info.f_bavail * info.f_frsize,
            "unavailable_free": max(0, info.f_bfree - info.f_bavail) * info.f_frsize}


def ledger_proof(image: OwnedImage, paths: dict[str, Path]) -> dict[str, object]:
    """Compare file allocation and bin logical/allocated scopes while preserving native coverage errors."""
    image.check()
    result = scan(image.root, options=ScanOptions(workers=1))
    before = os_capacity(image.root)
    ledger = capacity_ledger(result.root)
    after = os_capacity(image.root)
    require(ledger.total == before["total"] == after["total"], "APFS total differs from native statvfs")
    for key in ("used", "free", "unavailable_free"):
        require(min(before[key], after[key]) <= getattr(ledger, key) <= max(before[key], after[key]),
                f"APFS {key} differs from bracketed native samples")
    nodes = {node.path: node for node in result.root.iter_files()}
    records = {name: file_record(path) for name, path in paths.items()}
    for name, path in paths.items():
        node = nodes[str(path)]
        require(node.size == records[name]["logical"] and node.allocated == records[name]["allocated"],
                f"APFS fixture allocation differs: {name}")
    inventory = trash_usage(str(image.root))
    require(inventory is not None and inventory.complete and inventory.count == 1 and inventory.size == _BIN_BYTES,
            "Private APFS uid bin query differs from the owned logical payload")
    require(ledger.recycle_bin_complete and ledger.recycle_bin_seen == records["bin"]["allocated"],
            "APFS bin ledger differs from owned allocated payload")
    require(ledger.metadata_bytes is None and ledger.omitted_bytes is None and ledger.other_volumes_bytes is None,
            "Unmeasured APFS ledger buckets must remain unknown")
    require(ledger.coverage.complete or ledger.unaccounted is None, "Incomplete APFS coverage published a remainder")
    return {"ledger": ledger_record(ledger), "native_before": before, "native_after": after,
            "fixtures": records, "bin_inventory": asdict(inventory), "bin_scope": "fresh image current uid only",
            "independent_shared_extent_bytes": None, "independent_reserved_bytes": None,
            "scan_errors": result.errors, "native_volume": image.check()}


def unlink_fixtures(paths: dict[str, Path], captured: dict[str, dict[str, object]]) -> None:
    """Recheck full owned identities/payloads, accounting only for this batch's own hard-link removals."""
    removed: dict[tuple[int, int], int] = {}
    for name, original in captured.items():
        expected = dict(original)
        identity = tuple(expected["identity"])
        expected["links"] -= removed.get(identity, 0)
        require(file_record(paths[name]) == expected, "Disposable recovery fixture changed")
        paths[name].unlink()  # only the exclusive private-image fixtures created above
        removed[identity] = removed.get(identity, 0) + 1


def recovery_proof(image: OwnedImage, paths: dict[str, Path], *,
                   record: Callable[[dict[str, object]], None] | None = None) -> list[dict[str, object]]:
    """Unlink only captured disposable fixtures; sample actual deltas without promising exact reclamation."""
    records = []
    cases = (("one_hard_link", ("alias",)), ("last_hard_link", ("plain",)),
             ("all_hard_links", ("all-a", "all-b")), ("sparse", ("sparse",)),
             ("compressed", ("compressed",)), ("clone_first", ("clone",)),
             ("clone_last", ("compression-source",)))
    for label, names in cases:
        image.check()
        tree = scan(paths["plain"].parent, options=ScanOptions(workers=1)).root
        require(not tree.error and all(node.error is None for node in tree.iter_nodes()), "Owned recovery scan failed")
        nodes = {node.name: node for node in tree.iter_files()}
        estimate = estimate_savings([nodes[name] for name in names], root=tree)
        require(estimate is not None and estimate.recoverable_min == 0
                and estimate.recoverable_max is not None and estimate.uncertain, "APFS recovery uncertainty lost")
        if label == "one_hard_link":
            require(estimate.recoverable_max == 0, "One hard-link name cannot release the surviving data")
        captured = {name: file_record(paths[name]) for name in names}
        kept = {name: file_record(path) for name, path in paths.items() if name not in names and path.exists()}
        command(["/bin/sync"])
        before = os_capacity(image.root)["free"]
        unlink_fixtures(paths, captured)
        command(["/bin/sync"])
        samples = []
        for _sample in range(4):
            samples.append(os_capacity(image.root)["free"] - before)
            time.sleep(0.1)
        for name, kept_record in kept.items():
            actual = file_record(paths[name])
            require(actual["identity"] == kept_record["identity"] and actual["sha256"] == kept_record["sha256"],
                    "Unselected owned payload/identity changed")
        actual = {"case": label, "estimate": asdict(estimate), "native_free_change_samples": samples,
                  "selected_before": captured, "unselected_sources_preserved": True,
                  "independent_shared_extent_bytes": None, "directory_metadata_bytes": None,
                  "delta_scope": "OS free change includes deferred reclamation and filesystem metadata"}
        records.append(actual)
        if record is not None:
            record(actual)
    return records


def save(evidence: Path, proof: dict[str, object]) -> None:
    """Preserve phase/failure evidence atomically, including retained owned fixture locations."""
    with _atomic_file(evidence / "proof.json", encoding="utf-8") as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def cross_volume_proof(image: OwnedImage) -> dict[str, object]:
    """Use production fcopyfile between the owned host scratch and its fresh APFS image."""
    from tools.validate_macos_sources import _copy_and_link, _sources  # noqa: PLC0415

    image.check()
    source, unused = _sources(image.owned)
    target = image.root / unused.name
    target.mkdir(mode=0o700)
    require(source.stat().st_dev != target.stat().st_dev, "Cross-volume fixture shares its source device")
    proof = _copy_and_link(source, target)
    proof.update(copy_scope="cross-volume", source_device=source.stat().st_dev,
                 target_device=target.stat().st_dev, finder_automation=False, trash_invoked=False)
    return proof


def main() -> int:
    """No existing-image selector; uncertain attachment/detachment never grants scratch deletion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path("macos-volume-evidence"))
    args = parser.parse_args()
    image = OwnedImage()  # platform/privilege refusal precedes any fixture or evidence creation
    proof: dict[str, object] = {"phase": "started", "owned": str(image.owned), "host_bins_modified": False,
                                "finder_automation": False, "cleanup_verified": False}
    args.evidence.mkdir(parents=True, exist_ok=True)
    save(args.evidence, proof)

    def record(value: dict[str, object]) -> None:
        proof.setdefault("recovery", []).append(value)
        save(args.evidence, proof)

    try:
        image.create()
        image.attach()
        proof.update(phase="attached", device=image.device, volume_uuid=image.volume_uuid)
        save(args.evidence, proof)
        paths = fixtures(image)
        proof["capacity"] = ledger_proof(image, paths)
        save(args.evidence, proof)
        recovery_proof(image, paths, record=record)
        proof["cross_volume"] = cross_volume_proof(image)
        save(args.evidence, proof)
        from tools.macos_apfs_peer import reservation_proof  # noqa: PLC0415

        proof["reservation"] = reservation_proof(image)
        proof["phase"] = "validated"
        save(args.evidence, proof)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        proof.update(phase="failed", error=str(error))
        if isinstance(error, subprocess.CalledProcessError):
            proof["native_command_error"] = {
                "returncode": error.returncode,
                "stdout": (error.stdout or b"")[:65536].decode("utf-8", errors="replace"),
                "stderr": (error.stderr or b"")[:65536].decode("utf-8", errors="replace")}
        raise
    finally:
        try:
            if image.attached:
                image.detach()
            image.cleanup()
            proof["cleanup_verified"] = True
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            proof.update(cleanup_error=str(error), retained_owned_fixture=str(image.owned))
        save(args.evidence, proof)
    require(proof["cleanup_verified"], "Owned APFS fixture retained; inspect phase evidence")
    proof["phase"] = "complete"
    save(args.evidence, proof)
    sys.stdout.write("Owned APFS capacity, bin allocation and recovery evidence complete.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
