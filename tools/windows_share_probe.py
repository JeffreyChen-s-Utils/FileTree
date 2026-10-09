"""Read-only scanner proof on a share created exclusively by validate_windows_share.ps1."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.allocation import allocation_unit  # noqa: E402
from je_file_tree.core.cleanup import EMPTY_FOLDERS, find_cleanup  # noqa: E402
from je_file_tree.core.coverage import coverage_of  # noqa: E402
from je_file_tree.core.scanner import ACCESS_DENIED, ScanOptions, ScanResult, scan  # noqa: E402
from tools.windows_owned_volume import require  # noqa: E402

_BRANCHES = 256
_OPTIONS = ScanOptions(workers=1, file_times=True, exact_windows_allocation=True)


def _owned(args) -> Path:
    require(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted", "Disposable native Windows runner required")
    owned = args.owned.resolve(strict=True)
    require(owned.parent == Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
            and re.fullmatch(r"filetree-smb-[0-9a-f]{32}", owned.name) is not None, "Unowned SMB fixture")
    receipt = json.loads((owned / "owner.json").read_text(encoding="utf-8-sig"))
    share = "ftscan-" + owned.name.removeprefix("filetree-smb-")
    require(receipt["root"] == str(owned) and receipt["share"] == share
            and args.unc == "\\\\localhost\\" + share, "SMB receipt or loopback scope differs")
    require(re.fullmatch(r"[T-Z]:\\", args.mapped) is not None, "Invalid fixture drive")
    require(not owned.is_symlink() and not (owned / "sources").is_symlink(), "Redirected SMB source")
    return owned


def _inventory(root: Path) -> dict:
    result = {}
    for path in root.rglob("*"):
        info = path.lstat()
        require(not info.st_file_attributes & 0x400, "Owned source became a reparse point")
        result[str(path.relative_to(root))] = [info.st_dev, info.st_ino, info.st_size,
                                             hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None]
    return result


def _prepare(owned: Path) -> dict:
    root = owned / "sources"
    require(not any(root.iterdir()), "Existing SMB source fixtures refused")
    (root / "root.bin").write_bytes(b"owned SMB source" * 8192)
    (root / "denied").mkdir()
    (root / "denied" / "keep.bin").write_bytes(b"owned denied source")
    for index in range(_BRANCHES):
        folder = root / f"branch-{index:03}"
        folder.mkdir()
        for number in range(4):
            (folder / f"file-{number}.bin").write_bytes(bytes([index]) * (4097 + number))
    captured = _inventory(root)
    (owned / "inventory.json").write_text(json.dumps(captured), encoding="utf-8")
    return {"files": sum(row[-1] is not None for row in captured.values()), "branches": _BRANCHES}


def _rows(result: ScanResult) -> list[tuple]:
    return sorted((os.path.relpath(node.path, result.root.path), node.is_dir, node.is_link,
                   node.size, node.allocated, node.file_count, node.dir_count, node.error)
                  for node in result.root.iter_nodes())


def _compare(owned: Path, args) -> dict:
    local = scan(owned / "sources", options=_OPTIONS)
    require(not local.errors and coverage_of(local.root).complete, "Local fixture baseline is incomplete")
    unit = allocation_unit(str(owned / "sources"))
    require(unit is not None, "Local allocation unit is unknown")
    observations = []
    for transport, root in (("UNC", args.unc), ("mapped", args.mapped)):
        native_unit = allocation_unit(root)
        require(native_unit == unit, "Share-root native allocation unit differs from backing volume")
        for workers in (1, 4):
            result = scan(root, options=replace(_OPTIONS, workers=workers))
            require(not result.errors and coverage_of(result.root).complete
                    and _rows(result) == _rows(local), "SMB tree differs from complete local baseline")
            observations.append({"transport": transport, "workers": workers, "seconds": result.elapsed,
                                 "allocation_unit": native_unit, "files": result.root.file_count,
                                 "logical_bytes": result.root.size, "allocated_bytes": result.root.allocated,
                                 "equal": True})
    return {"cases": observations, "slow_remote_link_verified": False}


def _safe_failure(result: ScanResult) -> None:
    require(bool(result.errors) and not coverage_of(result.root).complete, "SMB failure lost incomplete coverage")
    proposals = find_cleanup(result.root, now=10**12)
    require(proposals is not None and not any(group.key == EMPTY_FOLDERS for group in proposals),
            "SMB failure produced an empty-folder cleanup proposal")


def _denied(args) -> dict:
    observations = []
    for transport, root in (("UNC", args.unc), ("mapped", args.mapped)):
        for workers in (1, 4):
            result = scan(root, options=replace(_OPTIONS, workers=workers))
            denied = next(node for node in result.root.children if node.name == "denied")
            require(denied.error == ACCESS_DENIED and not denied.children, "SMB bypassed denied listing")
            _safe_failure(result)
            observations.append({"transport": transport, "workers": workers, "access_denied": True,
                                 "incomplete": True, "empty_cleanup_proposals": 0})
    return {"cases": observations}


def _disconnect(owned: Path, args) -> dict:
    captured = {"disconnected": False}
    pause = threading.Event()

    def progress(current) -> None:
        if captured["disconnected"] or not current.files:
            return
        # A final callback must never be misreported as a mid-scan disconnect.
        require(current.files < _BRANCHES * 4, "Share scan completed before disconnect; no proof")
        program = Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        script = Path(__file__).with_name("validate_windows_share.ps1").resolve(strict=True)
        environment = {key: value for key, value in os.environ.items() if key.casefold() != "psmodulepath"}
        environment["PSModulePath"] = str(program.parent / "Modules")
        pause.set()
        try:
            subprocess.run([str(program), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script),  # noqa: S603
                            "-DisposableRunner", "-DisconnectOnly", "-FixtureRoot", str(owned)],
                           check=True, timeout=30, capture_output=True, env=environment)
        finally:
            pause.clear()
        captured.update(disconnected=True, observed_files_before_disconnect=current.files)

    result = scan(args.unc, options=_OPTIONS, progress=progress, progress_interval=.001, pause=pause)
    require(captured["disconnected"], "Native mid-scan share disconnect was not exercised")
    _safe_failure(result)
    return {**captured, "incomplete": True, "errors": len(result.errors), "files": result.root.file_count,
            "empty_cleanup_proposals": 0}


def main() -> None:
    """Use only this disposable runner's private receipt and preserve local identity/content throughout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare", "compare", "denied", "disconnect", "verify"), required=True)
    parser.add_argument("--owned", type=Path, required=True)
    parser.add_argument("--unc", required=True)
    parser.add_argument("--mapped", required=True)
    args = parser.parse_args()
    owned = _owned(args)
    if args.mode == "prepare":
        proof = _prepare(owned)
    elif args.mode == "compare":
        proof = _compare(owned, args)
    elif args.mode == "denied":
        proof = _denied(args)
    elif args.mode == "disconnect":
        proof = _disconnect(owned, args)
    else:
        expected = json.loads((owned / "inventory.json").read_text(encoding="utf-8"))
        require(_inventory(owned / "sources") == expected, "SMB fixture source identity/content changed")
        proof = {"source_preserved": True, "identity_and_hashes_equal": True}
    sys.stdout.write(json.dumps(proof) + "\n")


if __name__ == "__main__":
    main()
