"""Owned fatal child processes must retain context without altering Qt handlers."""

from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_workflow_actions import _jobs

_ROOT = Path(__file__).resolve().parents[1]
_PREFIX = '''
import os
import sys
import pytest
if os.name == "nt":
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(3)
else:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
'''
_HELD_THREAD = '''
import threading
ready = threading.Event()
release = threading.Event()
def held_owned_thread():
    ready.set()
    release.wait()
threading.Thread(target=held_owned_thread, daemon=True).start()
assert ready.wait(5)
'''


def _run(tmp_path: Path, source: str) -> tuple[subprocess.CompletedProcess, Path]:
    target = tmp_path / "test_owned.py"
    target.write_text(_PREFIX + source, encoding="utf-8")
    evidence = tmp_path / "evidence"
    command = [sys.executable, "-m", "tools.run_pytest", "--evidence", str(evidence), "--",
               "-c", str(_ROOT / "pyproject.toml"), "--confcutdir", str(tmp_path), str(target), "-q"]
    # A fixed interpreter runs only the fixture created above; no user process is targeted.
    result = subprocess.run(command, cwd=_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,  # noqa: S603
                            env=dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"),
                            timeout=45, check=False)
    return result, evidence


@pytest.mark.parametrize("fails", [False, True])
def test_runner_preserves_exit_and_qt_message_handler(tmp_path, fails):
    result, evidence = _run(tmp_path, f'''
from PySide6.QtCore import qInstallMessageHandler, qWarning
def test_owned():
    os.write(2, ("owned-pid:" + str(os.getpid()) + "\\n").encode())
    def handler(kind, context, message):
        os.write(2, ("owned-handler:" + message + "\\n").encode())
    original = qInstallMessageHandler(handler)
    try:
        qWarning("owned-warning")
        assert qInstallMessageHandler(original) is handler
    finally:
        qInstallMessageHandler(original)
    assert {not fails!r}
''')
    assert result.returncode == int(fails)
    process = json.loads((evidence / "process.json").read_text(encoding="utf-8"))
    assert process["state"] == "exited" and process["returncode"] == int(fails)
    context = json.loads((evidence / "active.json").read_text(encoding="utf-8"))
    assert context["phase"] == "session-finished" and context["outcome"] == str(int(fails))
    assert process["child_pid"] > 0 and context["pid"] != process["parent_pid"]
    assert f"owned-pid:{context['pid']}".encode() in (evidence / "output.log").read_bytes()
    assert b"owned-handler:owned-warning" in (evidence / "output.log").read_bytes()


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_qt_fatal_retains_message_active_phase_and_entry_snapshot(tmp_path, phase):
    source = '''
from PySide6.QtCore import qFatal
@pytest.fixture
def owned():
    BEFORE
    yield
    AFTER
def test_owned(owned):
    BODY
'''
    fatal = 'os.write(2, ("owned-pid:" + str(os.getpid()) + "\\n").encode()); qFatal("owned-qt-fatal")'
    source = source.replace("BEFORE", fatal if phase == "setup" else "pass")
    source = source.replace("BODY", fatal if phase == "call" else "pass")
    source = source.replace("AFTER", fatal if phase == "teardown" else "pass")
    result, evidence = _run(tmp_path, _HELD_THREAD + source)
    assert result.returncode != 0
    process = json.loads((evidence / "process.json").read_text(encoding="utf-8"))
    context = json.loads((evidence / "active.json").read_text(encoding="utf-8"))
    assert process["state"] == "exited" and process["returncode"] != 0
    assert context["phase"] == phase and context["nodeid"].endswith("test_owned")
    assert process["child_pid"] > 0 and context["pid"] != process["parent_pid"]
    assert f"owned-pid:{context['pid']}".encode() in (evidence / "output.log").read_bytes()
    assert b"owned-qt-fatal" in (evidence / "output.log").read_bytes()
    snapshot = (evidence / "phase-threads.txt").read_text(encoding="utf-8")
    assert json.loads(snapshot.splitlines()[0]) == context
    assert "Phase-entry snapshot, not a fault-time traceback." in snapshot
    assert "pytest_runtest_" + phase in snapshot
    assert "held_owned_thread" in snapshot


def test_abort_retains_fault_time_python_traceback(tmp_path):
    result, evidence = _run(tmp_path, _HELD_THREAD + '''
def test_owned():
    os.abort()
''')
    assert result.returncode != 0
    output = (evidence / "output.log").read_bytes()
    assert b"Fatal Python error" in output and b"test_owned" in output
    assert b"held_owned_thread" in output
    context = json.loads((evidence / "active.json").read_text(encoding="utf-8"))
    assert context["phase"] == "call"


def test_existing_evidence_is_never_overwritten(tmp_path):
    from tools.run_pytest import run_tests

    marker = tmp_path / "marker"
    marker.write_text("retained", encoding="utf-8")
    with pytest.raises(FileExistsError):
        run_tests(tmp_path, [])
    assert marker.read_text(encoding="utf-8") == "retained"


def test_export_replace_fault_injection_cannot_break_diagnostic_teardown(tmp_path):
    result, evidence = _run(tmp_path, '''
def test_owned(monkeypatch):
    def denied(*args):
        raise PermissionError("owned export failure")
    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(PermissionError, match="owned export failure"):
        os.replace("owned-source", "owned-target")
def test_following():
    assert os.replace.__name__ == "replace"
''')
    assert result.returncode == 0
    context = json.loads((evidence / "active.json").read_text(encoding="utf-8"))
    assert context["phase"] == "session-finished" and context["outcome"] == "0"


def test_recording_failure_is_visible_and_still_releases_fixtures(tmp_path):
    marker = tmp_path / "released"
    result, evidence = _run(tmp_path, f'''
from pathlib import Path
def test_owned(monkeypatch, request):
    recorder = request.config.pluginmanager.get_plugin("filetree-phase-context")
    original = recorder._record
    def denied(phase, *args, **kwargs):
        if phase == "teardown":
            raise PermissionError("owned diagnostic failure")
        return original(phase, *args, **kwargs)
    monkeypatch.setattr(recorder, "_record", denied)
    request.addfinalizer(lambda: Path({str(marker)!r}).write_text("released", encoding="utf-8"))
def test_following():
    assert Path({str(marker)!r}).read_text(encoding="utf-8") == "released"
''')
    assert result.returncode == 1
    assert marker.read_text(encoding="utf-8") == "released"
    assert b"owned diagnostic failure" in (evidence / "output.log").read_bytes()
    context = json.loads((evidence / "active.json").read_text(encoding="utf-8"))
    assert context["phase"] == "session-finished" and context["outcome"] == "1"


def test_every_pytest_ci_job_retains_native_context_after_failure():
    jobs = dict(_jobs(_ROOT / ".github/workflows/test.yml"))
    for name in ("windows", "linux", "macos", "qt68"):
        job = jobs[name]
        assert "python -m tools.run_pytest --evidence build/pytest-context --" in job
        assert "build/pytest-context/" in job
        upload = job.split("- name: Preserve pytest native context", 1)[1]
        assert upload.index("if: always()") < upload.index("uses: actions/upload-artifact@")


def _isolated_recorder():
    spec = importlib.util.spec_from_file_location("owned_context", _ROOT / "tools/pytest_context.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("code", [5, 32, 33])
def test_temporary_windows_reader_refusals_only_retry_publication(tmp_path, monkeypatch, code):
    recorder = _isolated_recorder()
    native = recorder._ATOMIC_REPLACE
    attempts, pauses = [], []

    def replace(source, target):
        attempts.append((source, target))
        if len(attempts) < 3:
            error = PermissionError("owned reader")
            error.winerror = code
            raise error
        native(source, target)

    monkeypatch.setattr(recorder, "_ATOMIC_REPLACE", replace)
    monkeypatch.setattr(recorder, "_PUBLISH_PAUSE", pauses.append)
    target = tmp_path / "active.json"
    recorder.write_record(target, {"phase": "call"})
    assert json.loads(target.read_text(encoding="utf-8")) == {"phase": "call"}
    assert len(attempts) == 3 and pauses == [.01, .01]
    assert len(set(attempts)) == 1


@pytest.mark.parametrize("code, attempts_expected", [(5, 10), (None, 1)])
def test_permanent_or_unrelated_write_failure_is_bounded_and_visible(tmp_path, monkeypatch, code, attempts_expected):
    recorder = _isolated_recorder()
    target = tmp_path / "active.json"
    target.write_text('{"phase":"prior"}', encoding="utf-8")
    attempts, pauses = [], []

    def refused(*args):
        attempts.append(args)
        error = PermissionError("owned persistent refusal")
        if code is not None:
            error.winerror = code
        raise error

    monkeypatch.setattr(recorder, "_ATOMIC_REPLACE", refused)
    monkeypatch.setattr(recorder, "_PUBLISH_PAUSE", pauses.append)
    with pytest.raises(PermissionError, match="owned persistent refusal"):
        recorder.write_record(target, {"phase": "call"})
    assert len(attempts) == attempts_expected and len(pauses) == attempts_expected - 1
    assert json.loads(target.read_text(encoding="utf-8")) == {"phase": "prior"}


@pytest.mark.skipif(os.name != "nt", reason="Windows native open-reader rename refusal")
def test_native_read_handle_can_release_between_atomic_publication_attempts(tmp_path, monkeypatch):
    recorder = _isolated_recorder()
    target = tmp_path / "active.json"
    recorder.write_record(target, {"phase": "prior"})
    pauses = []
    with target.open("rb") as reader:
        def release(delay):
            pauses.append(delay)
            reader.close()
        monkeypatch.setattr(recorder, "_PUBLISH_PAUSE", release)
        recorder.write_record(target, {"phase": "call"})
    assert pauses == [.01]
    assert json.loads(target.read_text(encoding="utf-8")) == {"phase": "call"}
