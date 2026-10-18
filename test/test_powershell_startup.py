"""Start-up samples keep every launch's actual outcome and clocks; they never retry or change helpers."""

import json
import shutil
import subprocess
import sys

import pytest

from test_workflow_actions import _jobs
from tools import measure_powershell_startup as startup
from tools.measure_powershell_startup import _CLOCK_PREFIX, _JSON_PREFIX

_ROOT = startup.Path(__file__).resolve().parents[1]


def _stderr(pid, before, json_ms=None):
    origin = {"pid": pid, "before_filetime_100ns": before, "after_filetime_100ns": before + 10}
    lines = [_CLOCK_PREFIX + json.dumps(origin)] + ([f"{_JSON_PREFIX}{json_ms}"] if json_ms is not None else [])
    return "\r\n".join(lines).encode()


def test_completed_launch_keeps_origin_offset_json_time_and_observation(monkeypatch):
    calls = []
    monkeypatch.setattr(startup, "_filetime", lambda: 1_000_000)
    observation = {"status": "observed", "child_pid": 7, "records": []}

    def run(command, *, timeout, sample_after):
        calls.append((command, timeout, sample_after))
        result = subprocess.CompletedProcess(command, 0, b"", _stderr(7, 1_000_000 + 52_000, 83))
        result.process_observation = observation
        return result
    monkeypatch.setattr(startup, "run_observed", run)
    record = startup.launch(startup.Path("powershell.exe"), 1)
    [(command, timeout, sample_after)] = calls
    assert command[1:5] == ["-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand"]
    assert startup.base64.b64decode(command[5]).decode("utf-16-le") == startup._SCRIPT
    assert (timeout, sample_after) == (30, 1.0)
    assert record["outcome"] == "completed" and record["launch_to_origin_ms"] == 5.2
    assert record["first_json_ms"] == 83 and record["process_observation"] is observation
    assert record["clock"]["status"] == "origin-only"


def test_timeout_and_start_failure_are_recorded_without_retry(monkeypatch):
    attempts = []

    def timed_out(command, **_kwargs):
        attempts.append(command)
        error = subprocess.TimeoutExpired(command, 30, output=b"", stderr=b"")
        error.process_observation = {"status": "observed", "records": [{"event": "thread-states"}]}
        raise error
    monkeypatch.setattr(startup, "run_observed", timed_out)
    record = startup.launch(startup.Path("powershell.exe"), 2)
    assert len(attempts) == 1 and record["outcome"] == "timeout" and record["launch_to_origin_ms"] is None
    assert record["process_observation"]["records"] == [{"event": "thread-states"}]

    def missing(*_args, **_kwargs):
        raise FileNotFoundError("powershell.exe missing")
    monkeypatch.setattr(startup, "run_observed", missing)
    assert startup.launch(startup.Path("powershell.exe"), 3)["outcome"] == "start-failed"


def test_measure_runs_launches_in_order_and_counts_timeouts(monkeypatch):
    outcomes = iter(["completed", "timeout", "completed"])
    monkeypatch.setattr(startup, "powershell", lambda: startup.Path("C:/Windows/powershell.exe"))
    monkeypatch.setattr(startup, "launch", lambda _program, number: {
        "launch": number, "outcome": next(outcomes), "launch_to_origin_ms": None if number == 2 else number * 10.0})
    report = startup.measure(3)
    assert [item["launch"] for item in report["launches"]] == [1, 2, 3]
    assert report["launch_to_origin_ms"] == [10.0, 30.0] and report["timeouts"] == 1


@pytest.mark.parametrize("stderr", [b"", f"{_JSON_PREFIX}12\r\n{_JSON_PREFIX}13".encode(), f"{_JSON_PREFIX}x".encode()])
def test_missing_ambiguous_or_invalid_json_markers_stay_unknown(stderr):
    assert startup._json_ms(stderr.decode()) is None


def test_existing_report_is_never_overwritten(tmp_path, monkeypatch):
    target = tmp_path / "report.json"
    target.write_text("kept", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["measure", "--output", str(target), "--launches", "1"])
    monkeypatch.setattr(startup, "measure", lambda _launches: pytest.fail("Measured into an existing report"))
    monkeypatch.setattr(startup.sys, "platform", "win32")
    with pytest.raises(FileExistsError):
        startup.main()
    assert target.read_text(encoding="utf-8") == "kept"


@pytest.mark.skipif(sys.platform != "win32" or shutil.which("powershell.exe") is None,
                    reason="native Windows PowerShell 5.1")
def test_native_launch_prints_a_valid_origin_and_json_marker():
    record = startup.launch(startup.powershell(), 1)
    assert record["outcome"] == "completed" and record["returncode"] == 0
    assert record["clock"]["status"] in ("origin-only", "aligned-origin")
    assert record["launch_to_origin_ms"] > 0 and record["first_json_ms"] is not None


def test_ci_job_samples_startup_with_pinned_actions_and_keeps_the_report():
    job = dict(_jobs(_ROOT / ".github/workflows/test.yml"))["powershell-startup"]
    assert "runs-on: windows-latest" in job and "timeout-minutes: 10" in job and "timeout-minutes: 8" in job
    assert "python -m tools.measure_powershell_startup --output powershell-startup.json" in job
    upload = job.split("- name: Preserve start-up samples", 1)[1]
    assert upload.index("if: always()") < upload.index("uses: actions/upload-artifact@")
    assert "pip install" not in job  # standard library only
