"""Mock-helper diagnostics preserve real process outcomes and bounded phase evidence."""

import json
import subprocess

import pytest

import test_windows_share_script as harness


def _phases(count=9):
    records = [dict(sequence=i + 1, phase=phase, event=event, elapsed_ms=i * 10)
               for i, (phase, event) in enumerate(harness._EXPECTED_PHASES[:count])]
    return "\n".join(harness._PHASE_PREFIX + json.dumps(row) for row in records).encode()


def _evidence(tmp_path):
    return tmp_path / "proof.json", "modeled mocked-helper evidence"


def test_success_saves_all_phases_without_changing_process_contract(tmp_path, monkeypatch):
    seen = []
    def run(command, **options):
        seen.append((command, options))
        return subprocess.CompletedProcess(command, 0, b'{"result":true}',
                                           _phases() + b"\nFILETREE_TEST_RUNTIME 5.1.owned\n")
    monkeypatch.setattr(harness.subprocess, "run", run)
    evidence = _evidence(tmp_path)
    data, record = harness._run("owned-powershell", "'owned case'", evidence)
    assert data == {"result": True}
    assert json.loads(evidence[0].read_text(encoding="utf-8")) == record
    assert record["mocked_smb"] and record["timeout_seconds"] == 20
    assert record["outcome"] == "completed" and record["returncode"] == 0
    assert record["harness"]["trace_complete"] and len(record["harness"]["steps"]) == 9
    assert record["harness"]["runtime"] == "5.1.owned"
    assert len(seen) == 1 and seen[0][1] == {"capture_output": True, "timeout": 20, "check": False}
    assert seen[0][0][:5] == ["owned-powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command"]
    assert "$PSModuleAutoLoadingPreference = 'None'" in seen[0][0][-1]


@pytest.mark.parametrize("complete", [False, True])
def test_timeout_is_not_retried_or_converted_by_partial_or_complete_trace(tmp_path, monkeypatch, complete):
    calls = []
    stderr = b"x" * 70000 + b"\n" + _phases(9 if complete else 2)
    original = subprocess.TimeoutExpired("owned", 20, output=b"y" * 70000, stderr=stderr)
    def timeout(*_args, **_kwargs):
        calls.append(1)
        raise original
    monkeypatch.setattr(harness.subprocess, "run", timeout)
    evidence = _evidence(tmp_path)
    with pytest.raises(AssertionError, match="helper timeout; deadline=20s") as raised:
        harness._run("owned", "case", evidence)
    assert raised.value.__cause__ is original and calls == [1]
    record = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert record["outcome"] == "timeout" and record["returncode"] is None
    assert record["stdout_truncated"] and record["stderr_truncated"]
    assert len(record["stdout"].encode()) <= 65536 and len(record["stderr"].encode()) <= 65536
    assert record["harness"]["trace_complete"] is complete
    assert record["harness"]["last_phase"]["phase"] == ("run-case" if complete else "import-modules")
    assert len(str(raised.value)) < 12000


@pytest.mark.parametrize("status", [0, 7])
def test_missing_trace_and_nonzero_exit_fail_after_saving_evidence(tmp_path, monkeypatch, status):
    monkeypatch.setattr(harness.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], status, b'{}', b'captured stderr'))
    evidence = _evidence(tmp_path)
    with pytest.raises(AssertionError, match="evidence="):
        harness._run("owned", "case", evidence)
    record = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert record["returncode"] == status and not record["harness"]["trace_complete"]
    assert record["harness"]["last_phase"] is None


def test_invalid_json_is_retained_with_its_actual_successful_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(harness.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 0, b'invalid JSON', _phases()))
    evidence = _evidence(tmp_path)
    with pytest.raises(AssertionError, match="validation=JSONDecodeError"):
        harness._run("owned", "case", evidence)
    record = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert record["outcome"] == "completed" and record["stdout"] == "invalid JSON"
    assert record["harness"]["trace_complete"]


def test_start_failure_and_evidence_write_failure_retain_their_causes(tmp_path, monkeypatch):
    original = FileNotFoundError("owned executable missing")
    def fail(*_args, **_kwargs):
        raise original
    monkeypatch.setattr(harness.subprocess, "run", fail)
    evidence = _evidence(tmp_path)
    with pytest.raises(AssertionError, match="start-failed") as raised:
        harness._run("owned", "case", evidence)
    assert raised.value.__cause__ is original
    before = evidence[0].read_text(encoding="utf-8")
    assert json.loads(before)["start_error"] == "owned executable missing"
    with pytest.raises(AssertionError, match="Evidence write failed") as raised:
        harness._run("owned", "case", evidence)
    assert raised.value.__cause__ is original and evidence[0].read_text(encoding="utf-8") == before


@pytest.mark.parametrize("payload", ['{}', '[]', 'broken', '{"sequence":true}', '[' * 1500])
def test_malformed_phase_records_do_not_mask_process_evidence(payload):
    record = harness._phase_record(harness._PHASE_PREFIX + payload)
    assert record["invalid_records"] == 1 and not record["trace_complete"] and not record["steps"]


def test_phase_validation_refuses_reordering_and_caps_history():
    lines = _phases().decode().splitlines()
    assert not harness._phase_record("\n".join(reversed(lines)))["trace_complete"]
    record = harness._phase_record("\n".join(lines * 20))
    assert len(record["steps"]) == 32 and not record["trace_complete"]
