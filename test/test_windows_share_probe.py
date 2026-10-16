"""The native share probe never accepts a host session or infers success from missed failures."""

from types import SimpleNamespace
import subprocess
import json

import pytest

from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.scanner import ACCESS_DENIED, ScanProgress, ScanResult, scan
from tools import windows_share_probe as probe


def _steps(*steps):
    return "".join('FILETREE_SMB_STEP ' + json.dumps({
        "sequence": index, "step": step, "event": event, "elapsed_ms": index,
    }) + "\n" for index, (step, event) in enumerate(steps, 1)).encode()


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
            raise subprocess.TimeoutExpired(command, 30, stderr=_steps(("remove-owned-share", "started")))
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=_steps(("helper-complete", "completed")))

    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    monkeypatch.setattr(probe, "scan", scanner)
    monkeypatch.setattr(probe, "run_observed", disconnect)
    monkeypatch.setattr(probe, "_safe_failure", observed.append)
    if fails:
        with pytest.raises(probe.ShareDisconnectError) as caught:
            probe._disconnect(tmp_path, args)
        assert not active.is_set() and len(observed) == 1
        assert isinstance(caught.value.__cause__, subprocess.TimeoutExpired)
        assert caught.value.proof["disconnected"] is False
        assert caught.value.proof["observed_files_before_disconnect"] == 1
        helper = caught.value.proof["helper"]
        assert helper["outcome"] == "timeout" and helper["returncode"] is None
        assert helper["steps"][-1]["step"] == "remove-owned-share"
        assert helper["steps"][-1]["event"] == "started" and not helper["trace_complete"]
    else:
        proof = probe._disconnect(tmp_path, args)
        assert len(observed) == 2 and observed[-1] is result
        assert proof["observed_files_before_disconnect"] == 1
        assert proof["disconnected"] and proof["incomplete"]
        assert proof["helper"]["returncode"] == 0 and proof["helper"]["trace_complete"]


@pytest.mark.parametrize("error", [
    subprocess.CalledProcessError(7, ["owned-helper"], output=b"native out",
                                  stderr=_steps(("share-ownership", "started"))),
    FileNotFoundError("helper unavailable"),
    subprocess.SubprocessError("helper transport failed"),
])
def test_disconnect_helper_failure_keeps_the_actual_outcome_without_retry(monkeypatch, tmp_path, error):
    observed = []

    def scanner(root, *, progress, pause, **_kwargs):
        try:
            progress(ScanProgress(1, 0, 1, root))
        finally:
            assert not pause.is_set()

    def fail(command, **kwargs):
        observed.append(command)
        raise error

    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    monkeypatch.setattr(probe, "scan", scanner)
    monkeypatch.setattr(probe, "run_observed", fail)
    with pytest.raises(probe.ShareDisconnectError) as caught:
        probe._disconnect(tmp_path, SimpleNamespace(unc="owned"))
    assert len(observed) == 1 and caught.value.__cause__ is error
    helper = caught.value.proof["helper"]
    assert helper["returncode"] == getattr(error, "returncode", None)
    assert helper["outcome"] == ("start-failed" if isinstance(error, OSError) else "failed")
    assert not caught.value.proof["disconnected"]


def test_post_disconnect_refusal_preserves_helper_success(monkeypatch, tmp_path):
    def scanner(root, *, progress, **_kwargs):
        progress(ScanProgress(1, 0, 1, root))
        return SimpleNamespace(errors=[], root=SimpleNamespace(file_count=1))

    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    monkeypatch.setattr(probe, "scan", scanner)
    monkeypatch.setattr(probe, "run_observed", lambda command, **_kwargs: subprocess.CompletedProcess(
        command, 0, stdout=b"", stderr=_steps(("helper-complete", "completed"))))
    with pytest.raises(probe.ShareDisconnectError) as caught:
        probe._disconnect(tmp_path, SimpleNamespace(unc="owned"))
    assert caught.value.proof["disconnected"] is True
    assert caught.value.proof["helper"]["returncode"] == 0
    assert caught.value.proof["failure"]["type"] == "RuntimeError"


def test_helper_record_bounds_output_and_retains_last_timeout_step():
    stderr = b"\xff"*100000 + _steps(("owned-share-lookup", "started"))
    error = subprocess.TimeoutExpired(["owned-helper"], 30, output=b"x"*100000, stderr=stderr)
    record = probe._helper_record(error, 0)
    assert len(record["stdout"]) <= 65536 and len(record["stderr"]) <= 65536
    assert record["stdout_truncated"] and record["stderr_truncated"]
    assert record["steps"][-1]["step"] == "owned-share-lookup"
    assert record["returncode"] is None and record["timeout_seconds"] == 30
    assert not record["trace_complete"]


def test_disconnect_cli_emits_partial_json_and_a_nonzero_exit(monkeypatch, tmp_path, capsys):
    partial = {"disconnected": False, "helper": {"outcome": "timeout"}}
    error = probe.ShareDisconnectError(partial, RuntimeError("modeled failure"))
    monkeypatch.setattr(probe, "_owned", lambda _args: tmp_path)
    monkeypatch.setattr(probe, "_disconnect", lambda *_args: (_ for _ in ()).throw(error))
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--mode", "disconnect", "--owned", str(tmp_path),
                                          "--unc", "owned", "--mapped", "Z:\\"])
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code == 1
    saved = json.loads(capsys.readouterr().out)
    assert saved["disconnected"] is False and saved["helper"]["outcome"] == "timeout"


@pytest.mark.parametrize("payload", ["{broken", "[]", '{"sequence":1,"step":[],"event":"started","elapsed_ms":0}'])
def test_malformed_step_output_never_masks_the_actual_timeout(payload):
    error = subprocess.TimeoutExpired(["owned-helper"], 30, stderr=('FILETREE_SMB_STEP ' + payload).encode())
    record = probe._helper_record(error, 0)
    assert record["outcome"] == "timeout" and record["invalid_step_records"] == 1
    assert not record["trace_complete"] and not record["steps"]


def test_timeout_after_completion_marker_is_still_a_timeout():
    error = subprocess.TimeoutExpired(["owned-helper"], 30, stderr=_steps(("helper-complete", "completed")))
    record = probe._helper_record(error, 0)
    assert record["trace_complete"] and record["outcome"] == "timeout" and record["returncode"] is None


def test_zero_exit_without_step_evidence_cannot_establish_a_disconnect(monkeypatch, tmp_path):
    def scanner(root, *, progress, **_kwargs):
        progress(ScanProgress(1, 0, 1, root))

    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    monkeypatch.setattr(probe, "scan", scanner)
    monkeypatch.setattr(probe, "run_observed", lambda command, **_kwargs: subprocess.CompletedProcess(
        command, 0, stdout=b"", stderr=b""))
    with pytest.raises(probe.ShareDisconnectError, match="step evidence") as caught:
        probe._disconnect(tmp_path, SimpleNamespace(unc="owned"))
    assert caught.value.proof["helper"]["returncode"] == 0 and not caught.value.proof["disconnected"]


def test_repeated_callbacks_never_retry_a_failed_native_helper(monkeypatch, tmp_path):
    commands = []

    def scanner(root, *, progress, **_kwargs):
        with pytest.raises(subprocess.TimeoutExpired):
            progress(ScanProgress(1, 0, 1, root))
        progress(ScanProgress(2, 0, 2, root))
        return SimpleNamespace(errors=[], root=SimpleNamespace(file_count=2))

    def fail(command, **_kwargs):
        commands.append(command)
        raise subprocess.TimeoutExpired(command, 30)

    monkeypatch.setenv("SYSTEMROOT", str(tmp_path))
    monkeypatch.setattr(probe, "scan", scanner)
    monkeypatch.setattr(probe, "run_observed", fail)
    with pytest.raises(probe.ShareDisconnectError) as caught:
        probe._disconnect(tmp_path, SimpleNamespace(unc="owned"))
    assert len(commands) == 1 and caught.value.proof["helper_attempted"]
    assert caught.value.proof["helper"]["outcome"] == "timeout"


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
