"""Owned native probe failure paths restore the exact captured DACL; mocks are no native evidence."""

from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ACCESS_DENIED, ScanResult
from tools import mft_tree_probe as probe


@pytest.mark.parametrize("failed", ["deny", "compare", None])
def test_exact_acl_restoration_runs_after_every_probe_outcome(tmp_path, monkeypatch, failed):
    root = tmp_path / "owned-fixtures"
    root.mkdir()
    actions = []
    def acl(_volume, path, action, descriptor=""):
        assert path.parent == root
        actions.append((action, descriptor))
        if failed == "deny" and action == "Deny":
            raise OSError("owned native ACL dispatch failed")
        return "captured original descriptor"
    def scan(_root, **_kwargs):
        path = next(root.iterdir())
        tree = Node(str(root), True, children=[])
        tree.children.append(Node(path.name, True, error=ACCESS_DENIED, parent=tree, children=[]))
        return ScanResult(tree, [(str(path), ACCESS_DENIED)], backend="mft")
    def compare(*_args):
        if failed == "compare":
            raise RuntimeError("owned comparison failed")
        return {"equal": True}
    monkeypatch.setattr(probe, "_acl", acl)
    monkeypatch.setattr(probe, "scan", scan)
    monkeypatch.setattr(probe, "_compare", compare)
    if failed:
        with pytest.raises((OSError, RuntimeError), match="owned"):
            probe._denied(SimpleNamespace(root=tmp_path), root, lambda _phase: None)
    else:
        result = probe._denied(SimpleNamespace(root=tmp_path), root, lambda _phase: None)
        assert result["descriptor_restored"] and result["incomplete"]
    assert actions == [("Read", ""), ("Deny", ""), ("Restore", "captured original descriptor")]
    assert next(root.iterdir()).joinpath("keep-secret.bin").read_bytes() == b"owned permission fixture"


def test_native_parity_failure_reports_first_exact_field_without_weakening_comparison(tmp_path, monkeypatch):
    ordinary = ScanResult(Node(str(tmp_path), True, allocated=123, children=[]), [])
    audited = ScanResult(Node(str(tmp_path), True, allocated=456, children=[]), [], backend="mft")
    replies = iter((ordinary, audited))
    def scan(_root, *, on_root=None, **_kwargs):
        result = next(replies)
        if on_root is not None:
            on_root(result.root)
        return result
    monkeypatch.setattr(probe, "scan", scan)
    with pytest.raises(RuntimeError, match="allocated.*123.*456"):
        probe._compare(tmp_path, probe.ScanOptions())


def test_native_parity_diagnostics_are_bounded_and_distinguish_missing_nodes_from_errors(tmp_path):
    ordinary = ScanResult(Node(str(tmp_path), True, children=[]), [("owned", "x" * 4096)])
    audited = ScanResult(Node(str(tmp_path), True, children=[]), [], backend="mft")
    detail = probe._parity_detail(ordinary, audited)
    assert detail.startswith("errors ordinary=") and len(detail) <= 2048
    audited.root.children.append(Node("extra", False, parent=audited.root))
    assert probe._parity_detail(ordinary, audited) == "node counts ordinary=1, mft=2"


def test_acl_dispatch_refuses_outside_owned_private_tree_before_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "verify_volume", lambda _v: None)
    def forbidden(*_args, **_kwargs):
        pytest.fail("Nonowned ACL path must not dispatch")
    monkeypatch.setattr(probe.subprocess, "run", forbidden)
    with pytest.raises(RuntimeError, match="nonowned"):
        probe._acl(SimpleNamespace(root=tmp_path), tmp_path / "keep", "Deny")


def test_native_acl_script_refuses_arbitrary_host_paths_before_volume_or_acl_access():
    script = Path(probe.__file__).with_name("mft_fixture_acl.ps1").read_text(encoding="utf-8")
    assert script.index("Only the fresh private-image") < script.index("Get-CimInstance")
    assert "[IO.FileAttributes]::ReparsePoint" in script and "VolumeId" in script
    assert "FileSystemRights]::ListDirectory" in script and "SetSecurityDescriptorSddlForm" in script


def test_failed_native_acl_subprocess_retains_bounded_stderr_in_phase_error(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "verify_volume", lambda _v: None)
    def failed(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["owned fixed script"], stderr="prefix" + "x" * 2100)
    monkeypatch.setattr(probe.subprocess, "run", failed)
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    with pytest.raises(RuntimeError) as captured:
        probe._acl(SimpleNamespace(root=tmp_path, volume_id="owned native identity"),
                   tmp_path / "owned-fixtures/denied-owned", "Deny")
    assert str(captured.value) == "Owned ACL Deny failed: " + "x" * 2000
