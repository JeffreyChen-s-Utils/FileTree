"""Validate capacity/savings/bin/compaction only on a freshly created owned VHD/VHDX NTFS volume."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.capacity import capacity_ledger  # noqa: E402
from je_file_tree.core.compression_ops import compress_files, _kernel  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.core.scanner import ScanOptions, scan  # noqa: E402
from je_file_tree.core.savings import estimate_savings  # noqa: E402
from je_file_tree.core.windows_allocation import file_allocation  # noqa: E402
from tools.windows_owned_volume import owned_ntfs_volume, OwnedVolume, require, verify_volume  # noqa: E402
from tools.windows_bin_probe import bin_proof  # noqa: E402
from tools.windows_compaction_probe import capture_guest, compaction_proof  # noqa: E402
from tools.windows_recovery_probe import recovery_proof  # noqa: E402
from tools.windows_sparse_trash_probe import sparse_trash_proof  # noqa: E402
from tools.volume_evidence import ledger_record  # noqa: E402

_MIB = 1024 * 1024
_OPTIONS = ScanOptions(workers=1, exact_windows_allocation=True)


def _write(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _sparse(path: Path, *, logical_size: int = 64 * _MIB) -> None:
    kernel = _kernel()
    kernel.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                                      ctypes.c_void_p]
    _write(path, b"")
    handle = kernel.CreateFileW(str(path), 0x40000000, 0, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        returned = ctypes.c_uint32()
        if not kernel.DeviceIoControl(handle, 0x900c4, None, 0, None, 0, ctypes.byref(returned), None):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)
    with path.open("r+b") as stream:
        stream.seek(logical_size - 4096)
        stream.write(b"s" * 4096)
        stream.flush()
        os.fsync(stream.fileno())


def _fixtures(volume: OwnedVolume) -> Path:
    verify_volume(volume)
    root = volume.root / "owned-fixtures"
    root.mkdir()
    plain = root / "plain 測試.bin"
    _write(plain, b"dense owned data\n" * (2 * _MIB // 17))
    os.link(plain, root / "alias.bin")
    _write(root / "compressed.txt", b"owned compressible payload\n" * 262144)
    _sparse(root / "sparse.bin")
    _sparse(root / "sparse-recovery.bin", logical_size=8 * _MIB)
    tree = scan(root, options=_OPTIONS).root
    candidate = next(node for node in tree.children if node.name == "compressed.txt")
    before = hashlib.sha256(Path(candidate.path).read_bytes()).hexdigest()
    result = compress_files(tree, [candidate], "ntfs")
    require(result.completed == 1 and not result.failures and result.after < result.before,
            "Private NTFS compression did not reduce allocation")
    require(hashlib.sha256(Path(candidate.path).read_bytes()).hexdigest() == before, "Compression changed payload")
    return root


def _ledger(volume: OwnedVolume) -> dict:
    verify_volume(volume)
    result = scan(volume.root, options=_OPTIONS)
    ledger = capacity_ledger(result.root)
    usage = shutil.disk_usage(volume.root)
    require((ledger.total, ledger.used, ledger.free) == (usage.total, usage.used, usage.free),
            "Capacity differs from the live OS query")
    require(ledger.unavailable_free == max(0, usage.total - usage.used - usage.free), "OS remainder differs")
    require(ledger.metadata_bytes is None and ledger.omitted_bytes is None and ledger.other_volumes_bytes is None,
            "Unknown allocation buckets must remain unknown")
    files = list(result.root.iter_files())
    known = {node.path: file_allocation(node.path, os.lstat(node.path)) for node in files if not node.is_link}
    require(all(value is not None for value in known.values()), "Fresh ordinary fixture allocation is unknown")
    require(all(node.allocated == known[node.path] for node in files if not node.is_link),
            "Recorded exact allocation differs from FILE_STANDARD_INFO")
    require(ledger.named_allocated == sum(known.values()), "Named allocation differs from exact observations")
    unique = {}
    for path, allocation in known.items():
        info = os.lstat(path)
        unique[(info.st_dev, info.st_ino)] = allocation
    require(ledger.unique_allocated == sum(unique.values()), "Unique allocation differs from native hard-link IDs")
    if result.errors:
        require(ledger.status == "incomplete" and ledger.unaccounted is None, "Unreadable coverage was hidden")
    else:
        require(ledger.status == "estimated" and ledger.unaccounted == usage.used - sum(unique.values()),
                "Whole-volume remainder differs from known native allocation")
    return {"ledger": ledger_record(ledger), "os_usage": usage._asdict(), "errors": result.errors}


def _savings(volume: OwnedVolume, root: Path) -> dict:
    verify_volume(volume)
    tree = scan(root, options=_OPTIONS).root
    plain = next(node for node in tree.children if node.name.startswith("plain"))
    alias = next(node for node in tree.children if node.name == "alias.bin")
    sparse = next(node for node in tree.children if node.name == "sparse.bin")
    compressed = next(node for node in tree.children if node.name == "compressed.txt")
    single, both = estimate_savings([plain], root=tree), estimate_savings([plain, alias], root=tree)
    require(single.recoverable_min == single.recoverable_max == 0, "One hard-link name must promise no file data")
    require(both.allocated == plain.allocated and both.recoverable_max == plain.allocated,
            "All hard-link names must count file data once")
    require(sparse.allocated < sparse.size and compressed.allocated < compressed.size,
            "Native sparse/compressed allocation was not distinguished from length")
    total = estimate_savings(tree.children, root=tree)
    require(total.recoverable_min == 0 and total.uncertain and total.recoverable_max is not None,
            "Windows savings must retain uncertainty and a zero lower bound")
    return {"one_alias": asdict(single), "all_aliases": asdict(both), "all_fixtures": asdict(total),
            "sparse": {"size": sparse.size, "allocated": sparse.allocated},
            "compressed": {"size": compressed.size, "allocated": compressed.allocated}}


def _save(output: Path, evidence: dict) -> None:
    with _atomic_file(output, encoding="utf-8") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)


def main() -> int:
    """Run only an administrator-owned private image; no input disk/path selector or UAC prompt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("vhd", "vhdx"), default="vhdx",
                        help="Create only a fresh owned fixture in this format (default: vhdx)")
    args = parser.parse_args()
    captured = {}
    evidence = {}
    def after_detach(volume: OwnedVolume) -> None:
        evidence["compaction"] = compaction_proof(volume, captured)
        evidence["phase"] = "guest_compaction"
        _save(args.output, evidence)
    def record_recovery(name: str, result: dict) -> None:
        evidence.setdefault("actual_recovery", {})[name] = result
        evidence["phase"] = "recovery_" + name
        _save(args.output, evidence)
    def record_sparse(name: str, result: dict) -> None:
        evidence.setdefault("sparse_trash_diagnostic", {})[name] = result
        evidence["phase"] = "sparse_trash_" + name
        _save(args.output, evidence)
    with owned_ntfs_volume(kind=args.kind, after_detach=after_detach) as volume:
        root = _fixtures(volume)
        evidence = {"fresh_owned_disk": True, "kind": args.kind, "native_device": volume.physical,
                    "volume_id": volume.volume_id, "capacity": _ledger(volume), "savings": _savings(volume, root),
                    "cloud_placeholders": "unavailable: actual provider required",
                    "shared_extents": "unknown", "reserved_bytes": "not independently measured"}
        evidence["phase"] = "capacity_and_savings"
        evidence["owned_disk_detached_and_removed"] = False
        _save(args.output, evidence)
        evidence["bin"] = bin_proof(volume)
        evidence["phase"] = "private_bin"
        _save(args.output, evidence)
        recovery_proof(volume, root, record_recovery)
        sparse_trash_proof(volume, root, record_sparse)
        evidence["capacity_after_empty"] = _ledger(volume)
        captured = capture_guest(volume)
        evidence["phase"] = "guest_captured"
        _save(args.output, evidence)
    evidence["owned_disk_detached_and_removed"] = True
    evidence["phase"] = "complete"
    _save(args.output, evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
