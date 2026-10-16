"""Execute only extracted share helpers with mocked SMB commands; never create a host share."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import pytest

from tools import windows_share_probe as probe

_SOURCE = Path(__file__).resolve().parents[1] / "tools/validate_windows_share.ps1"


@pytest.fixture(params=["powershell.exe", "pwsh"])
def shell(request):
    program = shutil.which(request.param)
    if program is None:
        pytest.skip("PowerShell runtime unavailable for mocked script helpers")
    return program


def _literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _run(shell, script):
    preamble = r"""
$ErrorActionPreference = 'Stop'
Import-Module Microsoft.PowerShell.Management, Microsoft.PowerShell.Utility
$PSModuleAutoLoadingPreference = 'None'
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(SOURCE, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw $parseErrors[0] }
$wanted = @('Write-DisconnectStep', 'Confirm-OwnedRoot', 'Remove-OwnedShare', 'Invoke-Probe')
foreach ($name in $wanted) {
    $definition = $ast.FindAll({ param($item)
        $item -is [Management.Automation.Language.FunctionDefinitionAst] -and $item.Name -eq $name
    }, $true)
    if ($definition.Count -ne 1) { throw 'Expected one helper definition' }
    . ([scriptblock]::Create($definition[0].Extent.Text))
}
$DisconnectOnly = $true
$script:DisconnectSequence = 0
$script:DisconnectClock = [Diagnostics.Stopwatch]::StartNew()
""".replace("SOURCE", _literal(_SOURCE))
    result = subprocess.run(  # noqa: S603 - trusted local helpers, mocked SMB only
        [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", preamble + script],
        capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    return json.loads(result.stdout.decode("utf-8-sig")), probe._helper_record(result, 0)


@pytest.mark.parametrize("changed", ["none", "path", "special", "sid"])
def test_owned_share_steps_keep_exact_checks_and_do_not_repeat_native_commands(shell, tmp_path, changed):
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
    data, record = _run(shell, script)
    assert data == {"refused": changed != "none", "lookups": 0 if changed == "sid" else 1,
                    "removals": 1 if changed == "none" else 0}
    assert not record["invalid_step_records"]
    if changed == "none":
        assert record["trace_complete"]
        assert [step["event"] for step in record["steps"] if step["step"] == "remove-owned-share"] == [
            "started", "completed"]
    else:
        assert record["steps"][-1]["event"] == "started"
        assert record["steps"][-1]["step"] == ("owner-receipt" if changed == "sid" else "share-ownership")


@pytest.mark.parametrize("status", [0, 7])
def test_probe_json_is_saved_before_nonzero_exit_is_propagated(shell, tmp_path, status):
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
    data, _record = _run(shell, script)
    assert data["refused"] is bool(status) and data["saves"] == 1 and data["preference"] is True
    assert data["proof"]["phase"] == ("failed" if status else "disconnect")
    assert data["proof"]["disconnect"]["helper"]["outcome"] == "timeout"
