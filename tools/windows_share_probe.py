"""Read-only scanner proof on a share created exclusively by validate_windows_share.ps1."""

from __future__ import annotations

import argparse
import base64
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.allocation import allocation_unit  # noqa: E402
from je_file_tree.core.cleanup import EMPTY_FOLDERS, find_cleanup  # noqa: E402
from je_file_tree.core.coverage import coverage_of  # noqa: E402
from je_file_tree.core.scanner import ACCESS_DENIED, ScanOptions, ScanResult, scan  # noqa: E402
from tools.windows_owned_volume import require  # noqa: E402
from tools.observed_process import run_observed  # noqa: E402
from tools.windows_trace_clock import trace_clock  # noqa: E402

_BRANCHES = 256
_OPTIONS = ScanOptions(workers=1, file_times=True, exact_windows_allocation=True)
_OUTPUT_LIMIT = 65536
_STEP_PREFIX = "FILETREE_SMB_STEP "
_WARMUP_TIMEOUT = 120
# The first Windows PowerShell 5.1 launch on a fresh runner waits in the kernel while its images load
# (2.6 s to the first statement and 1.35 s for the first ConvertFrom-Json, against about 0.16 s and
# 0.08 s for every later launch; U-20261017-64). Warm it once, outside the helpers' own deadlines.
_WARMUP_SCRIPT = "$null = '{\"warm\":1}' | ConvertFrom-Json"
_STEP_NAMES = {"runner-guard", "identity-check", "root-scope", "owner-receipt", "share-presence",
               "receipt-read", "receipt-parse", "receipt-identity",
               "owned-share-lookup", "share-ownership", "remove-owned-share", "helper-complete",
               *(f"owned-entry-{number}" for number in range(1, 5))}


class ShareDisconnectError(RuntimeError):
    """A failed disconnect proof with bounded native observations retained for the outer fixture."""

    def __init__(self, proof: dict, error: Exception) -> None:
        self.proof = {**proof, "failure": {"type": type(error).__name__, "message": _output(str(error))[0]}}
        super().__init__(f"Native SMB disconnect proof failed: {error}")


def _output(value: str | bytes | None) -> tuple[str, bool]:
    raw = value.encode("utf-8", errors="replace") if isinstance(value, str) else value or b""
    return raw[-_OUTPUT_LIMIT:].decode("utf-8", errors="replace"), len(raw) > _OUTPUT_LIMIT


def _steps(stderr: str) -> tuple[list[dict], int]:
    records, invalid = [], 0
    for line in stderr.splitlines():
        _before, prefix, payload = line.rpartition(_STEP_PREFIX)
        if not prefix:
            continue
        try:
            item = json.loads(payload)
        except (json.JSONDecodeError, RecursionError):
            invalid += 1
            continue
        if (not isinstance(item, dict) or set(item) != {"sequence", "step", "event", "elapsed_ms"}
                or type(item["sequence"]) is not int or item["sequence"] <= 0
                or type(item["step"]) is not str or item["step"] not in _STEP_NAMES
                or item["event"] not in ("started", "completed")
                or type(item["elapsed_ms"]) is not int or item["elapsed_ms"] < 0):
            invalid += 1
            continue
        records.append(item)
    return records[-64:], invalid


def _helper_record(result, started: float) -> dict:
    stdout, out_truncated = _output(getattr(result, "stdout", None))
    stderr, err_truncated = _output(getattr(result, "stderr", None))
    steps, invalid = _steps(stderr)
    complete = bool(steps and [step["sequence"] for step in steps] == list(range(1, len(steps)+1))
                    and steps[-1]["step"] == "helper-complete" and steps[-1]["event"] == "completed" and not invalid)
    if isinstance(result, subprocess.TimeoutExpired):
        outcome = "timeout"
    elif isinstance(result, OSError):
        outcome = "start-failed"
    else:
        outcome = "completed" if getattr(result, "returncode", None) == 0 else "failed"
    return {"outcome": outcome, "returncode": getattr(result, "returncode", None), "timeout_seconds": 30,
            "elapsed_seconds": round(time.monotonic()-started, 6), "stdout": stdout, "stderr": stderr,
            "stdout_truncated": out_truncated, "stderr_truncated": err_truncated,
            "steps": steps, "invalid_step_records": invalid, "trace_complete": complete,
            "process_observation": getattr(result, "process_observation", {"status": "not-sampled"}),
            "clock": trace_clock(stderr, "FILETREE_SMB_CLOCK ",
                                 getattr(result, "process_observation", {"status": "not-sampled"}))}


def windows_powershell() -> Path:
    """The system's Windows PowerShell 5.1, never a PATH lookup."""
    return Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"


def warm_powershell(program: Path, environment: dict[str, str] | None = None) -> dict:
    """Start Windows PowerShell once and convert one literal JSON value; bounded, recorded, never retried.

    It only moves the runner's one-time cold start out of the measured helpers. A failed or timed-out
    warm-up is evidence and changes no helper deadline, check or outcome.
    """
    encoded = base64.b64encode(_WARMUP_SCRIPT.encode("utf-16-le")).decode("ascii")
    started = time.monotonic()
    try:
        result = subprocess.run(  # noqa: S603 - fixed system program and literal script, no shell
            [str(program), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, timeout=_WARMUP_TIMEOUT, env=environment, check=False)
    except subprocess.TimeoutExpired:
        return {"outcome": "timeout", "timeout_seconds": _WARMUP_TIMEOUT,
                "elapsed_seconds": round(time.monotonic() - started, 3)}
    except OSError as error:
        return {"outcome": "start-failed", "error": str(error)[:2048]}
    return {"outcome": "completed", "returncode": result.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "stderr": result.stderr[-4096:].decode("utf-8", errors="replace")}


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


def _helper_environment(program: Path) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key.casefold() != "psmodulepath"}
    environment["PSModulePath"] = str(program.parent / "Modules")
    return environment


def _warm_up() -> dict:
    """Warm the helper's runtime; without SYSTEMROOT (not Windows) there is none to warm."""
    if "SYSTEMROOT" not in os.environ:
        return {"outcome": "unavailable", "reason": "SYSTEMROOT is not set"}
    program = windows_powershell()
    return warm_powershell(program, _helper_environment(program))


def _disconnect(owned: Path, args) -> dict:
    captured: dict = {"disconnected": False, "powershell_warmup": _warm_up()}
    pause = threading.Event()

    def progress(current) -> None:
        if captured.get("helper_attempted") or not current.files:
            return
        # A final callback must never be misreported as a mid-scan disconnect.
        require(current.files < _BRANCHES * 4, "Share scan completed before disconnect; no proof")
        program = windows_powershell()
        script = Path(__file__).with_name("validate_windows_share.ps1").resolve(strict=True)
        environment = _helper_environment(program)
        captured.update(helper_attempted=True, observed_files_before_disconnect=current.files)
        pause.set()
        started = time.monotonic()
        try:
            completed = run_observed(
                [str(program), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script),
                 "-DisposableRunner", "-DisconnectOnly", "-FixtureRoot", str(owned)],
                check=True, timeout=30, env=environment)
        except (subprocess.SubprocessError, OSError) as error:
            captured["helper"] = _helper_record(error, started)
            raise
        else:
            captured["helper"] = _helper_record(completed, started)
        finally:
            pause.clear()
        require(captured["helper"]["trace_complete"], "Native SMB helper step evidence is incomplete")
        captured["disconnected"] = True

    try:
        result = scan(args.unc, options=_OPTIONS, progress=progress, progress_interval=.001, pause=pause)
        require(captured["disconnected"], "Native mid-scan share disconnect was not exercised")
        _safe_failure(result)
    except (subprocess.SubprocessError, OSError, RuntimeError) as error:
        raise ShareDisconnectError(captured, error) from error
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
        try:
            proof = _disconnect(owned, args)
        except ShareDisconnectError as error:
            sys.stdout.write(json.dumps(error.proof) + "\n")
            raise SystemExit(1) from None
    else:
        expected = json.loads((owned / "inventory.json").read_text(encoding="utf-8"))
        require(_inventory(owned / "sources") == expected, "SMB fixture source identity/content changed")
        proof = {"source_preserved": True, "identity_and_hashes_equal": True}
    sys.stdout.write(json.dumps(proof) + "\n")


if __name__ == "__main__":
    main()
