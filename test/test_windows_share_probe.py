"""The native share probe never accepts a host session or infers success from missed failures."""

from types import SimpleNamespace
import subprocess

import pytest

from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.scanner import ACCESS_DENIED, ScanProgress, ScanResult, scan
from tools import windows_share_probe as probe


def test_share_probe_refuses_owner_session_before_reading_a_fixture(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(RuntimeError, match="Disposable native"):
        probe._owned(None)


def test_share_failure_does_not_treat_unread_branch_as_empty(tmp_path):
    denied = tmp_path / "denied"
    denied.mkdir()
    result = scan(tmp_path)
    node = result.root.children[0]
    node.error = ACCESS_DENIED
    result.errors.append((node.path, ACCESS_DENIED))
    probe._safe_failure(result)
    assert not coverage_of(result.root).complete
    result.errors.clear()
    with pytest.raises(RuntimeError, match="incomplete coverage"):
        probe._safe_failure(result)


def test_share_failure_rejects_a_false_empty_cleanup_proposal(tmp_path):
    (tmp_path / "actual-empty").mkdir()
    (tmp_path / "denied").mkdir()
    result = scan(tmp_path)
    node = next(node for node in result.root.children if node.name == "denied")
    node.error = ACCESS_DENIED
    result.errors.append((node.path, ACCESS_DENIED))
    with pytest.raises(RuntimeError, match="empty-folder cleanup"):
        probe._safe_failure(result)


@pytest.mark.parametrize("fails", [False, True])
def test_share_disconnect_pauses_new_reads_and_always_resumes(monkeypatch, tmp_path, fails):
    args = SimpleNamespace(unc=r"\\localhost\owned")
    result = SimpleNamespace(errors=[("owned branch", "disconnected")], root=SimpleNamespace(file_count=5))
    observed = []
    active = None

    def scanner(root, *, options, progress, progress_interval, pause):
        nonlocal active
        active = pause
        assert not pause.is_set() and options.workers == 1 and progress_interval > 0
        progress(ScanProgress(1, 2, 4096, root))
        assert not pause.is_set()
        progress(ScanProgress(5, 2, 8192, root))
        return result

    def disconnect(command, **kwargs):
        assert active.is_set()
        assert kwargs["check"] and kwargs["timeout"] == 30
        assert command[-2:] == ["-FixtureRoot", str(tmp_path)]
        observed.append(command)
        if fails:
            raise subprocess.TimeoutExpired(command, 30)

    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    monkeypatch.setattr(probe, "scan", scanner)
    monkeypatch.setattr(probe.subprocess, "run", disconnect)
    monkeypatch.setattr(probe, "_safe_failure", observed.append)
    if fails:
        with pytest.raises(subprocess.TimeoutExpired):
            probe._disconnect(tmp_path, args)
        assert not active.is_set() and len(observed) == 1
    else:
        proof = probe._disconnect(tmp_path, args)
        assert len(observed) == 2 and observed[-1] is result
        assert proof["observed_files_before_disconnect"] == 1
        assert proof["disconnected"] and proof["incomplete"]


def test_share_disconnect_rejects_an_end_of_scan_callback_before_removing_any_share(monkeypatch, tmp_path):
    def scanner(root, *, progress, **kwargs):
        progress(ScanProgress(probe._BRANCHES * 4 + 2, 256, 4096, root))

    monkeypatch.setattr(probe, "scan", scanner)
    with pytest.raises(RuntimeError, match="completed before disconnect"):
        probe._disconnect(tmp_path, SimpleNamespace(unc="owned"))


def test_share_row_parity_detects_allocation_and_coverage_changes(tmp_path):
    (tmp_path / "keep.bin").write_bytes(b"kept data")
    result = scan(tmp_path)
    before = probe._rows(result)
    result.root.children[0].allocated += 1
    assert probe._rows(result) != before
    other = ScanResult(result.root, errors=[("owned", ACCESS_DENIED)])
    with pytest.raises(RuntimeError, match="incomplete coverage"):
        probe._safe_failure(other)
