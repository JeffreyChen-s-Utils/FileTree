"""Native tree/options/ACL/performance comparisons only inside a fresh owned private NTFS image."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import uuid

from je_file_tree.core.mft_reader import NTFSReader
from je_file_tree.core.mft_scan import _audit
from je_file_tree.core.scanner import ACCESS_DENIED, NOT_SCANNED, ScanCancelledError, ScanOptions, ScanResult, scan
from je_file_tree.core.snapshot import snapshot_times, unpack_snapshot
from je_file_tree.core.windows_directory import WindowsEntry
from tools.windows_owned_volume import OwnedVolume, require, verify_volume

_ROW_FIELDS = ("path", "is_dir", "is_link", "size", "allocated", "file_count", "dir_count", "modified",
               "error", "snapshot", "owner", "accounting")


def _rows(result: ScanResult) -> list[tuple]:
    return sorted((node.path, node.is_dir, node.is_link, node.size, node.allocated, node.file_count,
                   node.dir_count, node.modified, node.error, node.snapshot, node.owner, node.accounting)
                  for node in result.root.iter_nodes())


def _field_difference(name: str, left: object, right: object) -> object:
    if name == "snapshot" and isinstance(left, bytes) and isinstance(right, bytes):
        before, after = asdict(unpack_snapshot(left)), asdict(unpack_snapshot(right))
        before["times"], after["times"] = snapshot_times(left), snapshot_times(right)
        return {key: (value, after[key]) for key, value in before.items() if value != after[key]}
    return repr(left)[:256], repr(right)[:256]


def _parity_detail(ordinary: ScanResult, audited: ScanResult) -> str:
    before, after = _rows(ordinary), _rows(audited)
    if len(before) != len(after):
        return f"node counts ordinary={len(before)}, mft={len(after)}"
    for left, right in zip(before, after, strict=True):
        if left != right:
            changes = {name: _field_difference(name, a, b)
                       for name, a, b in zip(_ROW_FIELDS, left, right, strict=True) if a != b}
            return f"first owned node {left[0]!r}: {changes!r}"[:2048]
    return f"errors ordinary={ordinary.errors[:3]!r}, mft={audited.errors[:3]!r}"[:2048]


def _diagnose(root: Path, ordinary: ScanResult) -> None:
    # If a candidate refuses, retain the precise owned raw discrepancy without changing scan fallback.
    with NTFSReader(str(root)) as native:
        for node in ordinary.root.iter_nodes():
            if node is ordinary.root or node.snapshot is None or node.is_link:
                continue
            info = os.lstat(node.path)
            if info.st_file_attributes & (0x400 | 0x1000 | 0x40000 | 0x400000):
                continue
            entry = WindowsEntry(node.name, info.st_ino, info.st_size, 0, info.st_file_attributes,
                                 info.st_reparse_tag, (info.st_ctime_ns, 0, info.st_mtime_ns, info.st_ctime_ns))
            _audit(native, info, entry, os.lstat(node.parent.path).st_ino, lambda: None)
    raise RuntimeError("Experimental private-image tree refused despite matching per-entry raw metadata")


def _compare(root: Path, options: ScanOptions) -> dict:
    ordinary = scan(root, options=options)
    published = []
    audited = scan(root, options=replace(options, experimental_mft=True), on_root=published.append)
    if audited.backend != "mft":
        _diagnose(root, ordinary)
    require(audited.root is published[0] and len(published) == 1, "Native scan published another root")
    require(_rows(ordinary) == _rows(audited) and sorted(ordinary.errors) == sorted(audited.errors),
            "Native metadata tree differs from ordinary Node/options/coverage: " + _parity_detail(ordinary, audited))
    require(ordinary.hard_links == audited.hard_links, "Native metadata hard-link accounting differs")
    return {"options": asdict(options), "ordinary_seconds": ordinary.elapsed,
            "mft_seconds": audited.elapsed, "nodes": len(_rows(audited)), "errors": len(audited.errors),
            "files": audited.root.file_count, "logical_bytes": audited.root.size,
            "allocated_bytes": audited.root.allocated, "backend": audited.backend, "equal": True}


def _acl(volume: OwnedVolume, path: Path, action: str, descriptor: str = "") -> str:
    verify_volume(volume)
    require(path.parent == volume.root / "owned-fixtures" and path.name.startswith("denied-"),
            "Refusing a nonowned ACL fixture")
    program = Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = Path(__file__).with_name("mft_fixture_acl.ps1").resolve(strict=True)
    try:
        result = subprocess.run([str(program), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script),  # noqa: S603
                                 "-Action", action, "-Path", str(path), "-VolumeId", volume.volume_id,
                                 "-Descriptor", descriptor], check=True, timeout=30,
                                capture_output=True, encoding="utf-8")
    except subprocess.SubprocessError as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise RuntimeError(f"Owned ACL {action} failed: {str(detail)[-2000:]}") from error
    return json.loads(result.stdout)["descriptor"]


def _denied(volume: OwnedVolume, root: Path, save: Callable[[dict], None]) -> dict:
    path = root / ("denied-" + uuid.uuid4().hex)
    path.mkdir()
    payload = path / "keep-secret.bin"
    payload.write_bytes(b"owned permission fixture")
    identity, original = (path.stat().st_dev, path.stat().st_ino), _acl(volume, path, "Read")
    try:
        _acl(volume, path, "Deny")
        result = scan(root, options=ScanOptions(experimental_mft=True))
        require(result.backend == "mft", "Native denied branch caused unexpected ordinary fallback")
        node = next(child for child in result.root.children if child.path == str(path))
        require(node.error == ACCESS_DENIED and not node.children
                and (str(path), ACCESS_DENIED) in result.errors, "Raw scan bypassed denied directory listing")
        compared = _compare(root, ScanOptions())
        save({"denied_branch": {"path": str(path), "equal": True, "incomplete": True}})
    finally:
        current = path.lstat()
        require((current.st_dev, current.st_ino) == identity and not getattr(current, "st_file_attributes", 0) & 0x400,
                "Denied fixture changed before exact ACL restoration")
        restored = _acl(volume, path, "Restore", original)
        require(restored == original, "Original owned DACL was not restored exactly")
    require(payload.read_bytes() == b"owned permission fixture", "Denied payload changed")
    return {"equal": True, "incomplete": True, "descriptor_restored": True, "comparison": compared}


def _cancel(root: Path) -> dict:
    cancel, published = threading.Event(), []
    try:
        scan(root, options=ScanOptions(experimental_mft=True, count_hard_links=True),
             cancel=cancel, on_root=published.append, progress=lambda _p: cancel.set(), progress_interval=0)
    except ScanCancelledError as error:
        partial = error.partial
        require(partial is not None and partial.backend == "mft" and partial.root is published[0],
                "Native cancellation lost the single partial root")
        require(any(node.error == NOT_SCANNED for node in partial.root.iter_nodes()),
                "Native cancellation hid unread branches")
        require(partial.hard_links is not None, "Native partial scan lost hard-link accounting")
        return {"backend": partial.backend, "partial": True, "single_root": True, "counted": True}
    raise RuntimeError("Native cancellation fixture completed without honoring stop")


def validate_tree(volume: OwnedVolume, root: Path, save: Callable[[dict], None]) -> dict:
    """Compare options and the whole private drive, restore only the owned denied DACL, keep payloads.

    save receives bounded scalar phase evidence before expensive comparisons. Timings are native
    observations on this disposable drive, never proof of large-volume speed or default enablement.
    """
    verify_volume(volume)
    require(root == volume.root / "owned-fixtures", "Refusing a nonowned tree fixture")
    branch = root / "tree-branch"
    branch.mkdir()
    (branch / "empty").mkdir()
    (branch / "keep.bin").write_bytes(b"owned tree bytes")
    (root / ".tree-hidden.bin").write_bytes(b"owned hidden bytes")
    os.symlink(branch, root / "tree-link", target_is_directory=True)
    options = [ScanOptions(workers=1), ScanOptions(workers=4), ScanOptions(include_hidden=False),
               ScanOptions(exclude=("tree-branch",)),
               ScanOptions(file_times=True, windows_owners=True, exact_windows_allocation=True,
                           count_hard_links=True)]
    comparisons = []
    for option in options:
        comparison = _compare(root, option)
        comparisons.append(comparison)
        save({"tree_comparisons": comparisons})
    denied = _denied(volume, root, save)
    cancelled = _cancel(root)
    full_drive = [_compare(volume.root, ScanOptions()) for _ in range(3)]
    medians = {f"{backend}_seconds": statistics.median(row[f"{backend}_seconds"] for row in full_drive)
               for backend in ("ordinary", "mft")}
    require((branch / "keep.bin").read_bytes() == b"owned tree bytes"
            and (root / ".tree-hidden.bin").read_bytes() == b"owned hidden bytes"
            and (root / "tree-link").is_symlink() and os.readlink(root / "tree-link") == str(branch),
            "Additional tree payloads/link changed")
    return {"tree_comparisons": comparisons, "denied_branch": denied, "cancellation": cancelled,
            "full_private_drive": full_drive, "full_private_drive_medians": medians,
            "default_enabled": False, "large_real_drive_validated": False, "tree_payloads_preserved": True}
