"""Owned-child diagnostics preserve native outcomes and cannot extend/retry helper execution."""

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from tools import observed_process as runner
from tools import windows_child_observer as native
from tools.windows_share_probe import _helper_record


@pytest.mark.parametrize("code", [0, 7])
def test_normal_and_failed_children_keep_exact_streams_and_status(code):
    command = [sys.executable, "-c", f"import sys;print('out');print('err',file=sys.stderr);sys.exit({code})"]
    result = runner.run_observed(command, timeout=10)
    assert result.returncode == code and result.stdout.strip() == b"out" and result.stderr.strip() == b"err"
    assert result.process_observation == {"status": "not-sampled"}


def test_checked_failure_preserves_observation_and_actual_exit(monkeypatch):
    observed = {"status": "modeled-observation-failure"}
    monkeypatch.setattr(runner, "_Observer", lambda _pid: SimpleNamespace(finish=lambda: observed))
    monkeypatch.setattr(runner.sys, "platform", "win32")
    command = [sys.executable, "-c", "import time,sys;time.sleep(.2);print('kept');sys.exit(7)"]
    with pytest.raises(subprocess.CalledProcessError) as caught:
        runner.run_observed(command, timeout=10, check=True, sample_after=.02)
    assert caught.value.returncode == 7 and caught.value.stdout.strip() == b"kept"
    assert caught.value.process_observation is observed
    assert _helper_record(caught.value, time.monotonic())["process_observation"] is observed


@pytest.mark.parametrize("startup_delay", [0, .7])
def test_timeout_keeps_all_output_once_reaps_child_and_does_not_retry(monkeypatch, tmp_path, startup_delay):
    seen = []
    original = runner.subprocess.Popen
    ready = tmp_path / "output-flushed"
    command = [sys.executable, "-c", "import time,sys;from pathlib import Path;time.sleep(float(sys.argv[2]));"
               "print('once',flush=True);print('error',file=sys.stderr,flush=True);"
               "Path(sys.argv[1]).touch();time.sleep(30)", str(ready), str(startup_delay)]
    # Prepare emitted bytes before the runner's unchanged .5 s communication deadline.
    with original(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:  # noqa: S603
        try:
            deadline = time.monotonic() + 10
            while not ready.exists():
                assert child.poll() is None and time.monotonic() < deadline, "Owned child never signaled flushed output"
                time.sleep(.01)

            def launch(actual_command, **kwargs):
                assert actual_command == command
                assert kwargs == {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "env": None}
                seen.append(child)
                return child

            monkeypatch.setattr(runner.subprocess, "Popen", launch)
            monkeypatch.setattr(runner, "_Observer", lambda _pid: SimpleNamespace(finish=lambda: {"status": "test"}))
            with pytest.raises(subprocess.TimeoutExpired) as caught:
                runner.run_observed(command, timeout=.5, sample_after=.1)
            assert caught.value.timeout == .5
            assert caught.value.stdout.strip() == b"once" and caught.value.stderr.strip() == b"error"
            assert len(seen) == 1 and seen[0].poll() is not None
        finally:
            if child.poll() is None:
                child.kill()
            child.wait()


def test_observation_error_does_not_replace_timeout(monkeypatch):
    class Broken:
        def finish(self):
            raise OSError("modeled read failure")

    monkeypatch.setattr(runner, "_Observer", lambda _pid: Broken())
    monkeypatch.setattr(runner.sys, "platform", "win32")
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        runner.run_observed([sys.executable, "-c", "import time;time.sleep(30)"], timeout=.3, sample_after=.05)
    record = _helper_record(caught.value, time.monotonic())
    assert record["outcome"] == "timeout" and record["process_observation"]["status"] == "observation-failed"
    assert caught.value.stdout == b"" and caught.value.stderr == b""


def test_second_wait_uses_remaining_deadline_and_preserves_first_partial_output(monkeypatch):
    waits, killed = [], []
    ticks = iter([0, 2, 3, 8])
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(runner.sys, "platform", "win32")
    monkeypatch.setattr(runner, "_Observer", lambda _pid: SimpleNamespace(finish=lambda: {"status": "test"}))

    class Child:
        pid = 123
        returncode = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def communicate(self, timeout=None):
            waits.append(timeout)
            if timeout is not None:
                raise subprocess.TimeoutExpired(["owned"], timeout, output=b"partial")
            return b"partial-final", b"stderr-final"

        def poll(self):
            return None

        def kill(self):
            killed.append(True)

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_args, **_kwargs: Child())
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        runner.run_observed(["owned"], timeout=20)
    assert waits == [5, 17, None] and killed == [True]
    assert caught.value.stdout == b"partial-final" and caught.value.timeout == 20


@pytest.mark.parametrize("error", [KeyboardInterrupt(), RuntimeError("interrupted diagnostic")])
def test_interrupted_wait_reaps_only_its_captured_child_and_reraises(monkeypatch, error):
    closed = []

    class Child:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def communicate(self, **_kwargs):
            raise error

        def kill(self):
            closed.append("kill")

        def wait(self):
            closed.append("join")

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_args, **_kwargs: Child())
    with pytest.raises(type(error)) as caught:
        runner.run_observed(["owned"], timeout=20)
    assert caught.value is error and closed == ["kill", "join"]


def test_observer_refuses_current_or_parent_process_without_native_queries(monkeypatch):
    monkeypatch.setattr(native.sys, "platform", "win32")
    for pid in (0, -1, os.getpid(), os.getppid()):
        with pytest.raises(RuntimeError, match="separate owned"):
            native.observe(pid)


def test_observer_refuses_non_sibling_before_wait_or_cpu_queries(monkeypatch):
    monkeypatch.setattr(native.sys, "platform", "win32")
    monkeypatch.setattr(native, "_Native", object)
    monkeypatch.setattr(native, "_entries", lambda *_args: [(123, os.getppid()+1, 1)])
    with pytest.raises(RuntimeError, match="not a child"):
        native.observe(123)


def test_thread_and_node_output_caps_and_native_errors_remain_visible(monkeypatch):
    emitted, queried = [], []
    monkeypatch.setattr(native.sys, "platform", "win32")
    api = SimpleNamespace(open_wait=lambda *_args: 1, close_wait=lambda _handle: None)
    monkeypatch.setattr(native, "_Native", lambda: api)
    monkeypatch.setattr(native, "_entries", lambda _api, threads: (
        [(123, tid) for tid in range(100)] if threads else [(123, os.getppid(), 100)]))
    monkeypatch.setattr(native, "_cpu", lambda *_args: {"error": 5})
    monkeypatch.setattr(native, "_emit", emitted.append)
    monkeypatch.setattr(native, "_chain", lambda _api, _session, _pid, tid: queried.append(tid) or {"error": 5})
    native.observe(123)
    assert queried == list(range(16))
    assert emitted[1] == {"event": "threads", "count": 100, "truncated": True}
    assert emitted[0]["cpu"] == {"error": 5} and emitted[-1]["event"] == "complete"


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows owned-child wait-chain ABI")
def test_native_observer_reads_only_owned_live_child_and_balances_wait_session():
    assert ctypes.sizeof(native._WaitNode) == 280 and native._WaitNode.object.offset == 8
    script = Path(native.__file__).resolve()
    child_script = """
import ctypes as c, sys, threading
from ctypes import wintypes as w
k = c.WinDLL('kernel32', use_last_error=True)
k.CreateMutexW.argtypes = [c.c_void_p, w.BOOL, w.LPCWSTR]; k.CreateMutexW.restype = w.HANDLE
k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]; k.WaitForSingleObject.restype = w.DWORD
k.ReleaseMutex.argtypes = [w.HANDLE]; k.CloseHandle.argtypes = [w.HANDLE]
mutex = k.CreateMutexW(None, True, None)
if not mutex: raise c.WinError(c.get_last_error())
def wait():
    if k.WaitForSingleObject(mutex, 10000) == 0: k.ReleaseMutex(mutex)
worker = threading.Thread(target=wait)
worker.start()
print('ready', flush=True)
sys.stdin.readline()
k.ReleaseMutex(mutex)
worker.join()
k.CloseHandle(mutex)
"""
    with subprocess.Popen(  # noqa: S603 - fixed owned mutex fixture; no share or existing process touched
            [sys.executable, "-c", child_script], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as child:
        try:
            result = subprocess.run(  # noqa: S603 - fixed read-only observer and captured owned child
                [sys.executable, str(script), "--pid", str(child.pid)], capture_output=True, timeout=10, check=True)
            records = [json.loads(line) for line in result.stdout.splitlines()]
            assert records[0]["event"] == "identity" and records[0]["pid"] == child.pid
            assert records[0]["parent_pid"] == os.getpid() and records[0]["cpu"]["exited_100ns"] == 0
            created = records[0]["cpu"]["created_100ns"]
            assert all(record["emitted_filetime_100ns"] >= created for record in records)
            assert records[1]["count"] > 0
            chains = [record for record in records if record["event"] == "chain"]
            assert chains or records[-1]["event"] == "wait-session-error"
            for chain in chains:
                if chain.get("nodes"):
                    assert chain["nodes"][0]["pid"] == child.pid
                assert len(chain.get("nodes", [])) <= 16
                if "query_before_filetime_100ns" in chain:
                    assert created <= chain["query_before_filetime_100ns"] <= chain["query_after_filetime_100ns"]
                    assert chain["query_after_filetime_100ns"] <= chain["emitted_filetime_100ns"]
        finally:
            stdout, _stderr = child.communicate(b"release\n", timeout=5)
        assert stdout.strip() == b"ready" and child.returncode == 0


def test_observer_start_failure_keeps_helper_outcome(monkeypatch):
    original = runner.subprocess.Popen

    def launch(command, **kwargs):
        if "--pid" in command:
            raise OSError("modeled observer start failure")
        return original(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(runner.sys, "platform", "win32")
    result = runner.run_observed([sys.executable, "-c", "import time;time.sleep(.2);print('original')"],
                                 timeout=10, sample_after=.02)
    assert result.returncode == 0 and result.stdout.strip() == b"original"
    assert result.process_observation["status"] == "start-failed"


def test_observer_output_caps_invalid_json_and_cancellation_do_not_invent_completion(monkeypatch):
    killed = []
    process = SimpleNamespace(poll=lambda: None, kill=lambda: killed.append(True), returncode=-1,
                              communicate=lambda: (b'bad\n[]\n{"event":"identity"}\n' + b'x'*70000, b'e'*70000))
    observer = runner._Observer.__new__(runner._Observer)
    observer.pid = 123
    observer.process, observer.timer = process, SimpleNamespace(cancel=lambda: None)
    observer.stop_reason = None
    record = observer.finish()
    assert killed == [True] and record["stop_reason"] == "parent-finished"
    assert record["records"] == [{"event": "identity"}] and record["invalid_records"] == 3
    assert record["output_truncated"] and len(record["stderr"]) == 65536


def test_reused_or_foreign_thread_id_is_refused_before_native_wait_query(monkeypatch):
    closed, queried = [], []
    api = SimpleNamespace(open_thread=lambda *_args: 42, thread_pid=lambda _handle: 999,
                          close=closed.append)
    monkeypatch.setattr(native, "_wait", lambda *_args: queried.append(True))
    monkeypatch.setattr(native.c, "get_last_error", lambda: 5, raising=False)
    record = native._chain(api, 1, 123, 7)
    assert record["ownership_refused"] and closed == [42] and not queried
