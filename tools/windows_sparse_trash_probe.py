"""Observe Qt Trash size boundaries only on a fresh owned private NTFS test volume."""

from collections.abc import Callable
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import re
import platform
import shutil

import PySide6
from PySide6.QtCore import QFile, qVersion
from PySide6.QtWidgets import QMessageBox

from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import stat_snapshot
from tools import windows_recovery_probe as recovery
from tools.windows_owned_volume import OwnedVolume, require, verify_volume

_MIB = 1024 * 1024
_LENGTHS = (8, 16, 32, 48, 64, 96)
_INVENTORY_LIMIT = 256


def _settings(volume: OwnedVolume) -> dict:
    import winreg  # noqa: PLC0415 - native diagnostic is never called on other platforms

    verify_volume(volume)
    match = re.fullmatch(r"\\\\\?\\Volume(\{[0-9a-fA-F-]{36}\})\\", volume.volume_id)
    require(match is not None, "Unknown private volume GUID; refusing registry lookup")
    key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume" + "\\" + match[1]
    values = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ) as handle:
            for name in ("MaxCapacity", "NukeOnDelete"):
                try:
                    value, kind = winreg.QueryValueEx(handle, name)
                    values[name] = {"value": value if isinstance(value, int) else None, "type": kind}
                except FileNotFoundError:
                    values[name] = None
    except FileNotFoundError:
        return {"key_present": False, "values": {}, "effective_quota_bytes": None}
    return {"key_present": True, "values": values, "effective_quota_bytes": None}


def _inventory(volume: OwnedVolume) -> dict:
    verify_volume(volume)
    path = volume.root / "$Recycle.Bin"
    if not os.path.lexists(path):
        return {"present": False, "entries": [], "errors": []}
    result = scan(path, options=recovery._OPTIONS)
    rows = []
    for node in result.root.iter_files():
        require(len(rows) < _INVENTORY_LIMIT, "Private bin diagnostic exceeded its inventory bound")
        rows.append({"path": node.path, "size": node.size, "allocated": node.allocated,
                     "link": node.is_link, "error": node.error})
    return {"present": True, "entries": rows, "errors": result.errors}


def _write_sparse(path: Path, length: int) -> dict:
    # Imported at call time because the main validator also calls this probe.
    from tools.validate_windows_volume import _sparse  # noqa: PLC0415

    require(not os.path.lexists(path), "Refusing an existing diagnostic payload")
    _sparse(path, logical_size=length)
    captured = stat_snapshot(str(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_MIB):
            digest.update(chunk)
    require(stat_snapshot(str(path)) == captured, "Owned diagnostic payload changed while hashing")
    return {"snapshot": captured.hex(), "logical": length, "sha256": digest.hexdigest()}


def _case(volume: OwnedVolume, root: Path, length: int, pending: Callable[[dict], None]) -> dict:
    verify_volume(volume)
    require(root == volume.root / "owned-fixtures" and root.resolve(strict=True) == root,
            "Refusing a foreign diagnostic scope")
    before_bin = recovery.bins._row(volume).trash
    require(before_bin.complete and before_bin.count == before_bin.size == 0, "Diagnostic bin must start empty")
    path = root / f"owned-sparse-trash-{length // _MIB}MiB.bin"
    captured = _write_sparse(path, length)
    result = scan(root, options=recovery._OPTIONS)
    selected = next(node for node in result.root.children if node.name == path.name)
    require(not result.errors and not selected.is_link and selected.snapshot == bytes.fromhex(captured["snapshot"]),
            "Diagnostic scan did not retain the owned payload proof")
    before = recovery._free(volume)
    receipts = recovery._trash(volume, [path], [bytes.fromhex(captured["snapshot"])])
    after = recovery._free(volume)
    with recovery.bins.owned_bin_dialog(volume) as (app, dialog, called):
        recovery.bins._settled(app, dialog)
        observed = recovery.bins._row(volume).trash
        evidence = {**captured, "allocated": selected.allocated, "source_absent": not os.path.lexists(path),
                    "qt_receipts": receipts, "native_bin": asdict(observed), "bin_inventory": _inventory(volume),
                    "volume_settings": _settings(volume), "free_before": before, "free_after_trash": after,
                    "observed_trash_free_delta": after - before, "native_empty_completed": False,
                    "retention": "unknown", "phase": "after_trash", "guaranteed_recovery": None}
        pending(evidence)
        require(observed.complete and observed.count in (0, 1), "Unexpected private bin diagnostic inventory")
        if observed.count == 1:
            require(observed.size == length, "Private diagnostic native bin length differs")
            questions = recovery.bins._review(app, dialog, volume, QMessageBox.StandardButton.Yes)
            recovery.bins._wait(app, lambda: recovery.bins._row(volume).trash.count == 0)
            require(len(questions) == recovery._QUESTIONS and called == [str(volume.root)] and not dialog.last_error,
                    "Private diagnostic emptying did not complete its owned review")
            evidence.update(native_empty_completed=True, retention="native_bin_observed")
        else:
            require(not called, "Unobserved diagnostic bin must never authorize emptying")
    return {**evidence, "phase": "observed", "free_after_review": recovery._free(volume)}


def sparse_trash_proof(volume: OwnedVolume, root: Path, record: Callable[[str, dict], None]) -> None:
    """Compare six newly created sparse lengths, retaining unknown no-bin outcomes without emptying them.

    This uses only the live owned image, literal generated payload names and its private bin. Registry
    preferences are read-only observations, never effective-quota authority. No host bin is inspected.
    Missing native inventory is not claimed as recycling, recovery, or an explained permanent removal.
    """
    verify_volume(volume)
    supports = getattr(QFile, "supportsMoveToTrash", None)
    record("environment", {"qt": qVersion(), "pyside": PySide6.__version__, "windows": platform.version(),
                           "supports_trash": bool(supports()) if supports else None,
                           "filesystem_total": shutil.disk_usage(volume.root).total})
    for length in _LENGTHS:
        name = f"{length}MiB"
        observed = _case(volume, root, length * _MIB, lambda pending, key=name: record(key, pending))
        record(name, observed)
