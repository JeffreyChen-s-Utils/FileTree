"""Owned native probe failure paths restore the exact captured DACL; mocks are no native evidence."""

from pathlib import Path
import os
import subprocess
import time
from types import SimpleNamespace

import pytest

from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ACCESS_DENIED, ScanResult
from je_file_tree.core.snapshot import pack_snapshot
from tools import mft_tree_probe as probe


@pytest.mark.parametrize("failed", ["deny", "compare", "restore", None])
def test_exact_acl_restoration_runs_after_every_probe_outcome(tmp_path, monkeypatch, failed):
    root = tmp_path / "owned-fixtures"
    root.mkdir()
    actions, phases = [], []
    def acl(_volume, path, action, descriptor=""):
        assert path.parent == root
        actions.append((action, descriptor))
        if failed == "deny" and action == "Deny":
            raise OSError("owned native ACL dispatch failed")
        if failed == "restore" and action == "Restore":
            return "different restored descriptor"
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
            probe._denied(SimpleNamespace(root=tmp_path), root, phases.append)
    else:
        result = probe._denied(SimpleNamespace(root=tmp_path), root, phases.append)
        assert result["descriptor_restored"] and result["incomplete"]
    assert actions == [("Read", ""), ("Deny", ""), ("Restore", "captured original descriptor")]
    assert phases[0]["acl_restoration"] == {"original_descriptor": "captured original descriptor"}
    assert phases[-1]["acl_restoration"] == {
        "original_descriptor": "captured original descriptor",
        "restored_descriptor": ("different restored descriptor" if failed == "restore"
                                else "captured original descriptor"),
        "equal": failed != "restore",
    }
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


def test_snapshot_diagnostics_report_exact_trailing_attribute_and_link_fields():
    info = SimpleNamespace(st_dev=1, st_ino=2, st_size=0, st_mode=0o40777, st_mtime_ns=100,
                           st_ctime_ns=100, st_file_attributes=0x10, st_nlink=1)
    ordinary = pack_snapshot(info)
    info.st_file_attributes, info.st_nlink = 0x10000010, 2
    audited = pack_snapshot(info)
    assert probe._field_difference("snapshot", ordinary, audited) == {
        "attributes": (0x10, 0x10000010), "links": (1, 2),
    }


def _directory_info():
    return SimpleNamespace(st_dev=1, st_ino=2, st_size=0, st_mode=0o40777, st_mtime_ns=100,
                           st_ctime_ns=100, st_file_attributes=0x10, st_nlink=1)


def test_only_proven_directory_representation_is_equivalent_without_changing_either_snapshot():
    info = _directory_info()
    ordinary = pack_snapshot(info)
    info.st_file_attributes |= 0x10000000
    audited = pack_snapshot(info)
    assert ordinary != audited and probe._same_snapshot(ordinary, audited)
    assert probe._same_snapshot(audited, ordinary)
    assert probe._field_difference("snapshot", ordinary, audited) == {"attributes": (16, 268435472)}


@pytest.mark.parametrize("field, value", [
    ("st_ino", 3), ("st_nlink", 2), ("st_mtime_ns", 101), ("st_ctime_ns", 101),
    ("st_file_attributes", 0x20000010), ("st_file_attributes", 0x10000012),
    ("st_file_attributes", 0x10000410), ("st_file_attributes", 0x10001010),
    ("st_file_attributes", 0x10000000), ("st_mode", 0o100666),
])
def test_directory_representation_never_hides_other_snapshot_changes(field, value):
    info = _directory_info()
    ordinary = pack_snapshot(info)
    info.st_file_attributes |= 0x10000000
    setattr(info, field, value)
    assert not probe._same_snapshot(ordinary, pack_snapshot(info))


def test_semantic_rows_keep_node_link_boundaries_and_all_other_fields_strict():
    info = _directory_info()
    ordinary = ScanResult(Node("owned", True, children=[], snapshot=pack_snapshot(info)), [])
    info.st_file_attributes |= 0x10000000
    audited = ScanResult(Node("owned", True, children=[], snapshot=pack_snapshot(info)), [], backend="mft")
    assert probe._same_rows(probe._rows(ordinary), probe._rows(audited))
    ordinary.root.is_link = audited.root.is_link = True
    assert not probe._same_rows(probe._rows(ordinary), probe._rows(audited))
    ordinary.root.is_link = audited.root.is_link = False
    audited.root.allocated = 1
    assert not probe._same_rows(probe._rows(ordinary), probe._rows(audited))


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


def test_acl_child_uses_only_matching_system_modules_and_keeps_parent_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "verify_volume", lambda _v: None)
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    monkeypatch.setenv("PSMODULEPATH", "incompatible-edition-modules")
    monkeypatch.setenv("PsMoDuLePaTh", "another-incompatible-module-key")
    monkeypatch.setenv("FILETREE_PROBE_SENTINEL", "preserved")
    original = [(key, value) for key, value in os.environ.items() if key.casefold() == "psmodulepath"]
    def run(command, **kwargs):
        environment = kwargs.get("env")
        assert environment is not None
        modules = [(key, value) for key, value in environment.items() if key.casefold() == "psmodulepath"]
        assert modules == [("PSModulePath", str(Path(command[0]).parent / "Modules"))]
        assert environment["FILETREE_PROBE_SENTINEL"] == "preserved"
        return SimpleNamespace(stdout='{"descriptor": "original descriptor"}')
    monkeypatch.setattr(probe.subprocess, "run", run)
    assert probe._acl(SimpleNamespace(root=tmp_path, volume_id="owned identity"),
                      tmp_path / "owned-fixtures/denied-owned", "Read") == "original descriptor"
    assert [(key, value) for key, value in os.environ.items() if key.casefold() == "psmodulepath"] == original


def test_probe_timings_measure_wall_clock_even_when_scan_elapsed_is_zero(tmp_path, monkeypatch):
    def scan(_root, *, on_root=None, **_kwargs):
        result = ScanResult(Node(str(tmp_path), True, children=[]), [], elapsed=0,
                            backend="mft" if on_root is not None else "ordinary")
        if on_root is not None:
            on_root(result.root)
        return result
    clock = iter((10.0, 10.005, 10.01, 10.215))
    monkeypatch.setattr(probe, "scan", scan)
    monkeypatch.setattr(time, "perf_counter", lambda: next(clock))
    result = probe._compare(tmp_path, probe.ScanOptions())
    assert result["ordinary_seconds"] == pytest.approx(0.005)
    assert result["mft_seconds"] == pytest.approx(0.205)
