"""Observe actual recovery only for disposable payloads on the live owned private NTFS fixture."""

from collections.abc import Callable
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import shutil
import stat

from PySide6.QtWidgets import QMessageBox

from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.savings import estimate_savings
from je_file_tree.core.snapshot import stat_snapshot
from je_file_tree.gui.file_actions import trash_receipt
from tools import windows_bin_probe as bins
from tools.windows_owned_volume import OwnedVolume, require, verify_volume

_OPTIONS = ScanOptions(workers=1, exact_windows_allocation=True)
_QUESTIONS = 2


def _free(volume: OwnedVolume) -> int:
    verify_volume(volume)
    return shutil.disk_usage(volume.root).free


def _keeper(path: Path | None) -> dict | None:
    if path is None:
        return None
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
            "A remaining owned alias changed type")
    return {"identity": [info.st_dev, info.st_ino], "links": info.st_nlink, "size": info.st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _trash(volume: OwnedVolume, paths: list[Path], snapshots: list[bytes]) -> None:
    for path, captured in zip(paths, snapshots, strict=True):
        verify_volume(volume)
        require(stat_snapshot(str(path)) == captured, "Recovery fixture changed before Trash")
        receipt = trash_receipt(str(path))
        require(receipt.success and not os.path.lexists(path), "Owned recovery fixture was not moved to Trash")
        if receipt.destination:
            require(Path(receipt.destination).is_relative_to(volume.root), "Recovery Trash escaped private volume")


def _case(volume: OwnedVolume, root: Path, names: tuple[str, ...], keeper: Path | None = None) -> dict:
    verify_volume(volume)
    require(root == volume.root / "owned-fixtures" and root.resolve(strict=True) == root,
            "Refusing a foreign/linked recovery source scope")
    before_bin = bins._row(volume).trash
    require(before_bin.complete and before_bin.count == before_bin.size == 0, "Recovery bin was not empty")
    result = scan(root, options=_OPTIONS)
    require(not result.errors, "Recovery fixture scan was incomplete")
    selected = [node for node in result.root.children if node.name in names]
    require(len(selected) == len(names) and all(not node.is_link and not node.is_dir for node in selected),
            "Recovery selection differs from the owned ordinary fixture names")
    paths = [Path(node.path) for node in selected]
    captured = [stat_snapshot(str(path)) for path in paths]
    savings = estimate_savings(selected, root=result.root)
    retained = _keeper(keeper)
    before = _free(volume)
    _trash(volume, paths, captured)
    after_trash = _free(volume)
    with bins.owned_bin_dialog(volume) as (app, dialog, called):
        bins._settled(app, dialog)
        reviewed = bins._row(volume).trash
        require(reviewed.count == len(names), "Native bin count differs from the owned recovery selection")
        questions = bins._review(app, dialog, volume, QMessageBox.StandardButton.Yes)
        bins._wait(app, lambda: bins._row(volume).trash.count == 0)
        require(len(questions) == _QUESTIONS and called == [str(volume.root)] and not dialog.last_error,
                "Recovery native emptying did not complete its scoped two-question review")
        require(dialog.model.rows()[0].trash.count == 0, "Recovery GUI did not refresh the empty bin")
    after_empty = _free(volume)
    remaining = _keeper(keeper)
    if retained is not None:
        require(all(remaining[key] == retained[key] for key in ("identity", "size", "sha256"))
                and remaining["links"] == 1, "Remaining hard-link alias changed identity/content/link count")
    return {"names": list(names), "estimate": asdict(savings), "free_before_trash": before,
            "free_after_trash": after_trash, "free_after_empty": after_empty,
            "observed_net_free_delta": after_empty - before, "observed_empty_free_delta": after_empty - after_trash,
            "bin_before_empty": asdict(reviewed), "two_questions": questions,
            "remaining_alias_before": retained, "remaining_alias_after": remaining,
            "directory_metadata_bytes": None, "guaranteed_file_data_recovery": None}


def recovery_proof(volume: OwnedVolume, root: Path, record: Callable[[str, dict], None]) -> None:
    """Measure one/last/all hard-link names, compression and sparse recovery with partial-phase records.

    Raw OS free deltas include unknown bin/directory metadata and are never claimed as a guaranteed
    file-data estimate. QFile Trash and two-question joined native emptying use only the private drive.
    A failed case propagates with its preceding evidence intact; no host drive/bin is accepted.
    """
    record("one_hard_link", _case(volume, root, ("plain 測試.bin",), root / "alias.bin"))
    record("last_hard_link", _case(volume, root, ("alias.bin",)))
    verify_volume(volume)
    original, alias = root / "all names.bin", root / "all alias.bin"
    require(not os.path.lexists(original) and not os.path.lexists(alias), "Refusing existing all-link fixtures")
    with original.open("xb") as stream:
        stream.write(b"owned all-hard-link recovery\n" * 131072)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(original, alias)
    record("all_hard_links", _case(volume, root, (original.name, alias.name)))
    record("compressed", _case(volume, root, ("compressed.txt",)))
    record("sparse", _case(volume, root, ("sparse.bin",)))
