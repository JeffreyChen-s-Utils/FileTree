"""Run only installer inventory helpers against owned scratch, without installing any product."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_POWERSHELL = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(_POWERSHELL is None, reason="PowerShell 7 inventory helper unavailable")


def _run(tmp_path, body):
    script = tmp_path / "inventory.ps1"
    validator = str(_ROOT / "tools/validate_msi.ps1").replace("'", "''")
    script.write_text("param([string]$Source)\n$ErrorActionPreference = 'Stop'\n"
                      f"$ast = [Management.Automation.Language.Parser]::ParseFile('{validator}', "
                      "[ref]$null, [ref]$null)\n"
                      "$names = @('Read-OwnedInventory', 'Confirm-Inventory')\n"
                      "$definitions = $ast.FindAll({ param($node)\n"
                      "    $node -is [Management.Automation.Language.FunctionDefinitionAst] "
                      "-and $node.Name -in $names\n"
                      "}, $true)\n"
                      "foreach ($definition in $definitions) { . ([scriptblock]::Create($definition.Extent.Text)) }\n"
                      + body, encoding="utf-8")
    result = subprocess.run([_POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(script),  # noqa: S603
                             str(tmp_path / "owned")], check=True, capture_output=True,
                            encoding="utf-8", timeout=30)
    return json.loads(result.stdout)


def _payload(tmp_path):
    root = tmp_path / "owned"
    (root / "空白 folder").mkdir(parents=True)
    (root / "data.bin").write_bytes(b"source contents")
    return root


def test_native_inventory_retains_empty_directories_and_compares_complete_hashes(tmp_path):
    _payload(tmp_path)
    inventory = _run(tmp_path, "$inventory = Read-OwnedInventory $Source\n"
                              "Confirm-Inventory $Source $inventory\n$inventory | ConvertTo-Json\n")
    assert inventory["."] == inventory["空白 folder"] == "<directory>"
    assert len(inventory["data.bin"]) == 64 and len(inventory) == 3


@pytest.mark.parametrize("mutation", [
    "[IO.File]::WriteAllText((Join-Path $Source 'data.bin'), 'changed')",
    "[IO.File]::WriteAllText((Join-Path $Source 'arrival.bin'), 'arrival')",
    "New-Item -ItemType Directory -Path (Join-Path $Source 'arrival') | Out-Null",
])
def test_changed_data_and_unknown_file_or_empty_directory_refuse(tmp_path, mutation):
    _payload(tmp_path)
    result = _run(tmp_path, "$inventory = Read-OwnedInventory $Source\n" + mutation + "\n"
                  "try { Confirm-Inventory $Source $inventory; throw 'Unexpected acceptance' }\n"
                  "catch { @{ error = $_.Exception.Message } | ConvertTo-Json }\n")
    assert "Payload" in result["error"] and "Unexpected acceptance" not in result["error"]


def test_linked_payload_refuses_before_inventory_traversal(tmp_path):
    root = _payload(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"owned directory symlinks unavailable: {error}")
    result = _run(tmp_path, "try { Read-OwnedInventory $Source | Out-Null; throw 'Unexpected acceptance' }\n"
                  "catch { @{ error = $_.Exception.Message } | ConvertTo-Json }\n")
    assert result["error"] == "Payload contains a link."
