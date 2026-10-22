"""Execute only extracted share helpers with mocked SMB commands; never create a host share."""

import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

import pytest

from tools import windows_share_probe as probe
from tools.observed_process import run_observed
from tools.windows_trace_clock import trace_clock

_SOURCE = Path(__file__).resolve().parents[1] / "tools/validate_windows_share.ps1"
_PHASE_PREFIX = "FILETREE_TEST_PHASE "
_EXPECTED_PHASES = [("entry", "completed"), ("import-modules", "started"), ("import-modules", "completed"),
                    ("parse-source", "started"), ("parse-source", "completed"),
                    ("extract-helpers", "started"), ("extract-helpers", "completed"),
                    ("run-case", "started"), ("run-case", "completed")]
_PREAMBLE = r"""
$ErrorActionPreference = 'Stop'
$script:TestClockBefore = [DateTime]::UtcNow.ToFileTimeUtc()
$script:TestClock = [Diagnostics.Stopwatch]::StartNew()
$script:TestClockAfter = [DateTime]::UtcNow.ToFileTimeUtc()
$script:TestOrigin = 'FILETREE_TEST_CLOCK {{"pid":{0},"before_filetime_100ns":{1},"after_filetime_100ns":{2}}}' -f (
    $PID, $script:TestClockBefore, $script:TestClockAfter)
[Console]::Error.WriteLine($script:TestOrigin)
$script:TestSequence = 0
function Write-TestPhase([string]$phase, [string]$event) {
    $script:TestSequence += 1
    $line = 'FILETREE_TEST_PHASE {{"sequence":{0},"phase":"{1}","event":"{2}","elapsed_ms":{3}}}' -f `
        $script:TestSequence, $phase, $event, $script:TestClock.ElapsedMilliseconds
    [Console]::Error.WriteLine($line)
    [Console]::Error.Flush()
}
Write-TestPhase 'entry' 'completed'
[Console]::Error.WriteLine('FILETREE_TEST_RUNTIME ' + $PSVersionTable.PSVersion.ToString())
Write-TestPhase 'import-modules' 'started'
Import-Module Microsoft.PowerShell.Management, Microsoft.PowerShell.Utility
Write-TestPhase 'import-modules' 'completed'
$PSModuleAutoLoadingPreference = 'None'
$tokens = $null; $parseErrors = $null
Write-TestPhase 'parse-source' 'started'
$ast = [Management.Automation.Language.Parser]::ParseFile(SOURCE, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw $parseErrors[0] }
Write-TestPhase 'parse-source' 'completed'
Write-TestPhase 'extract-helpers' 'started'
$wanted = @('Start-DisconnectClock', 'Write-DisconnectStep', 'Confirm-OwnedRoot', 'Remove-OwnedShare', 'Invoke-Probe')
foreach ($name in $wanted) {
    $definition = $ast.FindAll({ param($item)
        $item -is [Management.Automation.Language.FunctionDefinitionAst] -and $item.Name -eq $name
    }, $true)
    if ($definition.Count -ne 1) { throw 'Expected one helper definition' }
    . ([scriptblock]::Create($definition[0].Extent.Text))
}
Write-TestPhase 'extract-helpers' 'completed'
$DisconnectOnly = $true
$script:DisconnectSequence = 0
Start-DisconnectClock
Write-TestPhase 'run-case' 'started'
"""


_WARMED: dict[str, dict] = {}


@pytest.fixture(params=["powershell.exe", "pwsh"])
def shell(request):
    """The runtime, started once per session first: a fresh runner's cold start is not the helper's time.

    Hosted Windows PowerShell 5.1 took 2.6 s to its first statement and 1.35 s for its first JSON
    conversion on the first launch, then about 0.16/0.08 s (U-20261017-64); the 20 s deadline stays.
    """
    program = shutil.which(request.param)
    if program is None:
        pytest.skip("PowerShell runtime unavailable for mocked script helpers")
    if program not in _WARMED:
        _WARMED[program] = probe.warm_powershell(Path(program))
    return program


@pytest.fixture
def evidence(tmp_path, request):
    directory = Path(os.environ.get("FILETREE_SHARE_SCRIPT_EVIDENCE", str(tmp_path)))
    directory.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_.-]", "-", request.node.name)[:80]
    return directory / f"{name}-{uuid.uuid4().hex}.json", request.node.nodeid


def _literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _phase_record(stderr):
    steps, invalid = [], 0
    for line in stderr.splitlines():
        if not line.startswith(_PHASE_PREFIX):
            continue
        try:
            item = json.loads(line[len(_PHASE_PREFIX):])
        except (ValueError, RecursionError):
            invalid += 1
            continue
        if (not isinstance(item, dict) or set(item) != {"sequence", "phase", "event", "elapsed_ms"}
                or type(item["sequence"]) is not int or item["sequence"] <= 0
                or (item["phase"], item["event"]) not in _EXPECTED_PHASES
                or type(item["elapsed_ms"]) is not int or item["elapsed_ms"] < 0):
            invalid += 1
            continue
        steps.append(item)
    complete = (not invalid and [item["sequence"] for item in steps] == list(range(1, len(_EXPECTED_PHASES) + 1))
                and [(item["phase"], item["event"]) for item in steps] == _EXPECTED_PHASES
                and all(left["elapsed_ms"] <= right["elapsed_ms"]
                        for left, right in zip(steps, steps[1:], strict=False)))
    versions = [line.removeprefix("FILETREE_TEST_RUNTIME ") for line in stderr.splitlines()
                if line.startswith("FILETREE_TEST_RUNTIME ")]
    return {"steps": steps[-32:], "invalid_records": invalid, "trace_complete": complete,
            "last_phase": steps[-1] if steps else None, "runtime": versions[-1][:80] if versions else None}


def _failure(record, path):
    return (f"Mocked PowerShell helper {record['outcome']}; deadline=20s, returncode={record['returncode']}; "
            f"evidence={path}; last_phase={record['harness']['last_phase']}; "
            f"validation={record.get('validation_error')}\n"
            f"stderr tail:\n{record['stderr'][-8192:]}\nstdout tail:\n{record['stdout'][-2048:]}")


def _run(shell, script, evidence):
    preamble = _PREAMBLE.replace("SOURCE", _literal(_SOURCE))
    command = [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
               preamble + script + "\nWrite-TestPhase 'run-case' 'completed'\n"]
    started = time.monotonic()
    failure = None
    try:
        result = run_observed(command, timeout=20, check=False)
    except (subprocess.TimeoutExpired, OSError) as error:
        result, failure = error, error
    record = probe._helper_record(result, started)
    record.update(timeout_seconds=20, shell=shell, case=evidence[1], mocked_smb=True,
                  case_sha256=hashlib.sha256(script.encode("utf-8")).hexdigest())
    if failure is not None:
        record["exception_type"] = type(failure).__name__
        if isinstance(failure, OSError):
            record["start_error"] = str(failure)[:2048]
    record["harness"] = _phase_record(record["stderr"])
    record["harness"]["clock"] = trace_clock(record["stderr"], "FILETREE_TEST_CLOCK ", record["process_observation"])
    data = None
    if record["outcome"] == "completed":
        try:
            data = json.loads(result.stdout.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            record["validation_error"] = type(error).__name__
            failure = error
    path = evidence[0]
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False)
    except OSError as error:
        raise AssertionError(f"Evidence write failed: {error}\n{_failure(record, path)}") from failure or error
    if record["outcome"] != "completed" or failure is not None or not record["harness"]["trace_complete"]:
        raise AssertionError(_failure(record, path)) from failure
    return data, record


@pytest.mark.parametrize("changed", ["none", "path", "special", "sid"])
def test_owned_share_steps_keep_exact_checks_and_do_not_repeat_native_commands(shell, tmp_path, changed, evidence):
    root = tmp_path / ("filetree-smb-" + uuid.uuid4().hex)
    (root / "sources").mkdir(parents=True)
    share = "ftscan-" + root.name.removeprefix("filetree-smb-")
    (root / "owner.json").write_text(json.dumps({"root": str(root), "share": share,
                                                "sid": "wrong" if changed == "sid" else "runner"}), encoding="utf-8")
    script = r"""
$env:RUNNER_TEMP = PARENT
$identity = [pscustomobject]@{ User = [pscustomobject]@{ Value = 'runner' } }
$fixture = ROOT
$script:lookups = 0; $script:removals = 0
function Get-SmbShare {
    [CmdletBinding()] param([string]$Name)
    $script:lookups += 1
    if ($Name -ne SHARE) { throw 'Wrong mock share' }
    return [pscustomobject]@{ Path = SHAREPATH; Special = SPECIAL }
}
function Remove-SmbShare {
    param([string]$Name, [switch]$Force, [bool]$Confirm)
    if ($Name -ne SHARE -or -not $Force -or $Confirm) { throw 'Wrong removal arguments' }
    $script:removals += 1
}
$refused = $false
try { Remove-OwnedShare $fixture; Write-DisconnectStep 'helper-complete' 'completed' }
catch { $refused = $true }
@{ refused = $refused; lookups = $script:lookups; removals = $script:removals } | ConvertTo-Json -Compress
"""
    values = {"PARENT": _literal(tmp_path), "ROOT": _literal(root), "SHARE": _literal(share),
              "SHAREPATH": _literal(root / ("other" if changed == "path" else "sources")),
              "SPECIAL": "$true" if changed == "special" else "$false"}
    for key in sorted(values, key=len, reverse=True):
        script = script.replace(key, values[key])
    data, record = _run(shell, script, evidence)
    assert data == {"refused": changed != "none", "lookups": 0 if changed == "sid" else 1,
                    "removals": 1 if changed == "none" else 0}
    assert not record["invalid_step_records"]
    assert record["clock"]["status"] in ("origin-only", "aligned-origin")
    assert record["harness"]["clock"]["status"] in ("origin-only", "aligned-origin")
    if changed == "none":
        assert record["trace_complete"]
        assert [step["event"] for step in record["steps"] if step["step"] == "remove-owned-share"] == [
            "started", "completed"]
    else:
        assert record["steps"][-1]["event"] == "started"
        assert record["steps"][-1]["step"] == ("receipt-identity" if changed == "sid" else "share-ownership")


@pytest.mark.parametrize("status", [0, 7])
def test_probe_json_is_saved_before_nonzero_exit_is_propagated(shell, tmp_path, status, evidence):
    script = r"""
$PSNativeCommandUseErrorActionPreference = $true
$proof = [ordered]@{ phase = 'started' }; $scratch = 'owned'; $unc = 'owned'; $mapping = 'Z:'
$script:saves = 0
function python {
    & PYTHON_EXECUTABLE PYTHON_SCRIPT RETCODE
}
function Save-Proof { $script:saves += 1 }
$refused = $false
try { Invoke-Probe 'disconnect' } catch { $refused = $true }
@{ refused = $refused; saves = $script:saves; proof = $proof
   preference = $PSNativeCommandUseErrorActionPreference } | ConvertTo-Json -Depth 8 -Compress
"""
    child = tmp_path / "child.py"
    child.write_text('import json,sys\nprint(json.dumps({"disconnected":False,"helper":{"outcome":"timeout"}}))\n'
                     'sys.exit(int(sys.argv[1]))\n', encoding="utf-8")
    script = script.replace("PYTHON_EXECUTABLE", _literal(sys.executable))
    script = script.replace("PYTHON_SCRIPT", _literal(child)).replace("RETCODE", str(status))
    data, _record = _run(shell, script, evidence)
    assert data["refused"] is bool(status) and data["saves"] == 1 and data["preference"] is True
    assert data["proof"]["phase"] == ("failed" if status else "disconnect")
    assert data["proof"]["disconnect"]["helper"]["outcome"] == "timeout"


def test_receipt_staging_preserves_baseline_empty_invalid_and_utf8_semantics(shell, tmp_path, evidence):
    parent = tmp_path / "receipt space's"
    root = parent / ("filetree-smb-" + uuid.uuid4().hex)
    (root / "sources").mkdir(parents=True)
    share = "ftscan-" + root.name.removeprefix("filetree-smb-")
    valid = {"root": str(root), "share": share, "sid": "runner"}
    payloads = {"valid": json.dumps(valid), "bom": "\ufeff" + json.dumps(valid),
                "unicode": json.dumps({**valid, "note": "\u6536\u64da"}, ensure_ascii=False),
                "empty": "", "null": "null", "array": "[]", "broken": "{", "missing": "{}",
                "sid": json.dumps({**valid, "sid": "different"})}
    cases = ",\n".join("@{ name=" + _literal(name) + "; text=" + _literal(text) + " }"
                        for name, text in payloads.items())
    baseline = _SOURCE.parents[1] / "test/fixtures/windows_confirm_owned_root_before_clock.ps1"
    assert hashlib.sha256(baseline.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == (
        "dc3c357f85918d18b9b9e47727eec1871c0c004ae50d44c01cd53a37a686299a")
    script = r"""
$env:RUNNER_TEMP = PARENT
$identity = [pscustomobject]@{ User = [pscustomobject]@{ Value = 'runner' } }
$fixture = ROOT
$tokens = $null; $errors = $null
$old = [Management.Automation.Language.Parser]::ParseFile(BASELINE, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Invalid baseline function' }
$definition = $old.FindAll({ param($item)
    $item -is [Management.Automation.Language.FunctionDefinitionAst] -and $item.Name -eq 'Confirm-OwnedRoot'
}, $true)
if ($definition.Count -ne 1) { throw 'Ambiguous baseline function' }
. ([scriptblock]::Create($definition[0].Extent.Text.Replace('function Confirm-OwnedRoot(',
                                                         'function Confirm-OwnedRootBaseline(')))
$results = foreach ($case in @(CASES)) {
    [IO.File]::WriteAllText((Join-Path $fixture 'owner.json'), $case.text, [Text.UTF8Encoding]::new($false))
    $oldError = ''; $newError = ''; $oldReceipt = $null; $newReceipt = $null
    try { $oldReceipt = Confirm-OwnedRootBaseline $fixture } catch { $oldError = $_.Exception.GetType().FullName }
    try { $newReceipt = Confirm-OwnedRoot $fixture } catch { $newError = $_.Exception.GetType().FullName }
    @{ name=$case.name; old_refused=($oldError -ne ''); new_refused=($newError -ne '')
       same_error=($oldError -eq $newError)
       same_receipt=(($oldReceipt | ConvertTo-Json -Compress) -eq ($newReceipt | ConvertTo-Json -Compress)) }
}
ConvertTo-Json -InputObject @($results) -Compress
"""
    values = {"PARENT": _literal(parent), "ROOT": _literal(root), "BASELINE": _literal(baseline), "CASES": cases}
    script = re.sub(r"\b(PARENT|ROOT|BASELINE|CASES)\b", lambda match: values[match[0]], script)
    data, _record = _run(shell, script, evidence)
    assert len(data) == len(payloads)
    for result in data:
        assert result["same_error"] and result["same_receipt"]
        assert result["old_refused"] is result["new_refused"] is (result["name"] not in {"valid", "bom", "unicode"})


def test_native_clock_brackets_match_same_process_birth_units(shell, evidence):
    script = r"""
$process = [Diagnostics.Process]::GetCurrentProcess()
try {
    @{ pid=$PID; created_filetime_100ns=$process.StartTime.ToUniversalTime().ToFileTimeUtc() } |
        ConvertTo-Json -Compress
} finally { $process.Dispose() }
"""
    data, record = _run(shell, script, evidence)
    for clock in (record["clock"], record["harness"]["clock"]):
        origin = clock["origin"]
        assert origin["pid"] == data["pid"]
        assert data["created_filetime_100ns"] <= origin["before_filetime_100ns"] <= origin["after_filetime_100ns"]


def test_each_runtime_is_warmed_once_and_only_recorded(monkeypatch):
    calls = []
    monkeypatch.setattr(probe, "warm_powershell", lambda program: calls.append(program) or {"outcome": "timeout"})
    monkeypatch.setattr(shutil, "which", lambda name: f"C:/runtime/{name}")
    monkeypatch.setattr(sys.modules[__name__], "_WARMED", {})
    request = type("Request", (), {"param": "powershell.exe"})()
    assert shell.__wrapped__(request) == "C:/runtime/powershell.exe"
    assert shell.__wrapped__(request) == "C:/runtime/powershell.exe"
    assert calls == [Path("C:/runtime/powershell.exe")]  # a failed warm-up is recorded, not retried
