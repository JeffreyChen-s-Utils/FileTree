"""Owned-child diagnostics preserve native outcomes and cannot extend/retry helper execution."""

import ctypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import venv

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


def test_all_waits_use_remaining_deadline_and_preserve_first_partial_output(monkeypatch):
    waits, killed = [], []
    ticks = iter([0, 0, 2, 3, 15, 16])
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
    assert waits == [5, 12, 4, None] and killed == [True]
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
    monkeypatch.setattr(native, "_modules", lambda _api, pid, _ranges: {"event": "modules", "error": 5, "pid": pid})
    monkeypatch.setattr(native, "_thread_states", lambda _api, pid, _ranges: {"event": "thread-states", "pid": pid})
    monkeypatch.setattr(native, "_emit", emitted.append)
    monkeypatch.setattr(native, "_chain", lambda _api, _session, _pid, tid: queried.append(tid) or {"error": 5})
    native.observe(123)
    assert queried == list(range(16))
    assert emitted[1] == {"event": "threads", "count": 100, "truncated": True}
    assert emitted[2] == {"event": "modules", "error": 5, "pid": 123}  # before any wait query
    assert emitted[3] == {"event": "thread-states", "pid": 123}
    assert emitted[0]["cpu"] == {"error": 5} and emitted[-1]["event"] == "complete"


def _module_api(names, error):
    state = {"position": 0, "closed": []}

    def step(_handle, entry):
        if state["position"] >= len(names):
            return 0
        entry._obj.name = names[state["position"]]
        state["position"] += 1
        return 1
    api = SimpleNamespace(snapshot=lambda flags, pid: 77 if (flags, pid) == (0x18, 123) else 0,
                          module_first=step, module_next=step, close=state["closed"].append)
    return api, state


@pytest.mark.parametrize(("count", "error", "extra"), [(3, 18, {}), (170, 18, {}), (2, 299, {"error": 299})])
def test_module_snapshot_keeps_newest_names_and_reports_native_errors(monkeypatch, count, error, extra):
    names = [f"m{index}.dll" for index in range(count)]
    api, state = _module_api(names, error)
    monkeypatch.setattr(native.c, "get_last_error", lambda: error, raising=False)
    record = native._modules(api, 123)
    assert record == {"event": "modules", "count": count, "truncated": count > 160, "names": names[-160:], **extra}
    assert state["closed"] == [77]


def _process_buffer(processes):
    """Synthetic x64 SystemProcessInformation: ``processes`` is ``[(pid, [(tid, created, state, reason, start)])]``."""
    size = sum(0x100 + 0x50 * len(threads) for _pid, threads in processes)
    buffer, offset = ctypes.create_string_buffer(size), 0
    for number, (pid, threads) in enumerate(processes):
        length = 0x100 + 0x50 * len(threads)
        ctypes.c_ulong.from_buffer(buffer, offset).value = 0 if number == len(processes) - 1 else length
        ctypes.c_ulong.from_buffer(buffer, offset + 4).value = len(threads)
        ctypes.c_void_p.from_buffer(buffer, offset + 0x50).value = pid
        ctypes.c_ulonglong.from_buffer(buffer, offset + 0xD0).value = 11  # read operations
        ctypes.c_ulonglong.from_buffer(buffer, offset + 0xE8).value = 4096  # read bytes
        for index, (tid, created, state, reason, start) in enumerate(threads):
            record = native._SystemThread.from_buffer(buffer, offset + 0x100 + 0x50 * index)
            record.tid, record.created, record.start = tid, created, start
            record.state, record.wait_reason, record.switches = state, reason, tid
        offset += length
    return buffer


def test_thread_states_lead_with_the_main_thread_and_map_start_modules(monkeypatch):
    threads = [(30 + index, 1000 - index, 5, 15, 0) for index in range(60)] + [(7, 1, 5, 6, 0)]
    buffer = _process_buffer([(99, [(1, 1, 2, 0, 0)]), (123, threads)])
    starts = {7: 0x1010, 89: 0x2008}
    api = SimpleNamespace(system_information=lambda _cls, target, size, _needed: (
        ctypes.memmove(target, buffer, min(size, len(buffer))) and 0))
    monkeypatch.setattr(native, "_win32_start", lambda _api, pid, tid: starts.get(tid) if pid == 123 else None)
    record = native._thread_states(api, 123, [(0x1000, 0x100, "powershell.exe"), (0x2000, 0x10, "clr.dll")])
    assert record["count"] == 61 and record["truncated"] and len(record["threads"]) == 48
    assert record["io"]["read_operations"] == 11 and record["io"]["read_bytes"] == 4096
    main = record["threads"][0]
    assert main == {"tid": 7, "created_100ns": 1, "state": 5, "wait_reason": 6, "switches": 7, "wait_time_raw": 0,
                    "start_module": "powershell.exe", "start_offset": 0x10}
    assert {"start_module": "clr.dll", "start_offset": 8}.items() <= next(
        thread for thread in record["threads"] if thread["tid"] == 89).items()
    assert record["threads"][1]["created_100ns"] <= record["threads"][2]["created_100ns"]
    assert next(thread for thread in record["threads"] if thread["tid"] == 80)["start_module"] is None


@pytest.mark.parametrize(("status", "expected"), [(-1073741790, 0xC0000022), (0, "process not in snapshot")])
def test_thread_state_errors_are_recorded_not_guessed(monkeypatch, status, expected):
    buffer = _process_buffer([(99, [])])
    api = SimpleNamespace(system_information=lambda _cls, target, size, _needed: (
        ctypes.memmove(target, buffer, len(buffer)) and status))
    assert native._thread_states(api, 123, []) == {"event": "thread-states", "error": expected}


def test_growing_snapshot_buffer_stops_at_its_limit(monkeypatch):
    sizes = []

    def mismatch(_cls, _target, size, needed):
        sizes.append(size)
        needed._obj.value = size + 1
        return native._INFO_LENGTH_MISMATCH
    monkeypatch.setattr(native, "_PROCESS_BUFFER_LIMIT", 1 << 22)
    assert native._process_snapshot(SimpleNamespace(system_information=mismatch)) == native._INFO_LENGTH_MISMATCH
    assert sizes == [1 << 20, 1 << 21, 1 << 22]


def test_module_snapshot_failure_is_recorded_without_reading_entries(monkeypatch):
    monkeypatch.setattr(native.c, "get_last_error", lambda: 5, raising=False)
    api = SimpleNamespace(snapshot=lambda *_args: ctypes.c_void_p(-1).value,
                          module_first=lambda *_args: pytest.fail("Read an unopened snapshot"))
    assert native._modules(api, 123) == {"event": "modules", "error": 5}


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows owned-child wait-chain ABI")
def test_native_observer_reads_only_owned_live_child_and_balances_wait_session():
    assert ctypes.sizeof(native._WaitNode) == 280 and native._WaitNode.object.offset == 8
    assert ctypes.sizeof(native._ModuleEntry) == (1080 if ctypes.sizeof(ctypes.c_void_p) == 8 else 1064)
    script = Path(native.__file__).resolve()
    executable = getattr(sys, "_base_executable", None) or sys.executable
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
            [executable, "-c", child_script], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as child:
        try:
            result = subprocess.run(  # noqa: S603 - fixed read-only observer and captured owned child
                [executable, str(script), "--pid", str(child.pid)], capture_output=True, timeout=10, check=True)
            records = [json.loads(line) for line in result.stdout.splitlines()]
            assert records[0]["event"] == "identity" and records[0]["pid"] == child.pid
            assert records[0]["parent_pid"] == os.getpid() and records[0]["cpu"]["exited_100ns"] == 0
            created = records[0]["cpu"]["created_100ns"]
            assert all(record["emitted_filetime_100ns"] >= created for record in records)
            assert records[1]["count"] > 0
            modules = records[2]
            assert modules["event"] == "modules" and "error" not in modules and not modules["truncated"]
            assert any(name.lower().startswith("python") for name in modules["names"])
            states = records[3]
            assert states["event"] == "thread-states" and "error" not in states and states["count"] >= 2
            assert states["threads"][0]["start_module"].lower().startswith("python")  # the main thread leads
            assert all(isinstance(thread["wait_reason"], int) for thread in states["threads"])
            assert states["io"]["read_bytes"] >= 0
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
                              wait=lambda: -1)
    observer = runner._Observer.__new__(runner._Observer)
    observer.pid = 123
    observer.process, observer.timer = process, SimpleNamespace(cancel=lambda: None, ident=None)
    observer.stop_reason = None
    observer.captures = [runner._PipeCapture(io.BytesIO(data)) for data in
                         (b'bad\n[]\n{"event":"identity"}\n' + b'x'*70000, b'e'*70000)]
    for capture in observer.captures:
        capture.thread.start()
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


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows virtual-environment launcher binding")
def test_virtual_environment_observer_keeps_actual_sibling_parent_binding(tmp_path):
    environment = tmp_path / "owned-venv"
    venv.EnvBuilder(with_pip=False).create(environment)
    script = """
import json, os, subprocess, sys
from tools.observed_process import _Observer
command = [sys._base_executable, '-c', 'import sys;sys.stdin.readline()']
with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as target:
    observer = None
    try:
        observer = _Observer(target.pid)
        observer.process.wait(timeout=10)
        observation = observer.finish()
        print(json.dumps({'parent_pid': os.getpid(), 'target_pid': target.pid,
                          'executable': sys.executable, 'base_executable': sys._base_executable,
                          'observation': observation}))
    finally:
        if observer is not None:
            observer.finish()
        target.communicate(b'release\\n', timeout=5)
"""
    child_env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(  # noqa: S603 - fresh owned venv, base child and readonly observer only
        [str(environment / "Scripts/python.exe"), "-c", script], env=child_env,
        capture_output=True, timeout=20, check=True)
    record = json.loads(result.stdout)
    observation = record["observation"]
    identities = [item for item in observation["records"] if item["event"] == "identity"]
    assert identities, observation
    assert observation["returncode"] == 0 and identities[0]["pid"] == record["target_pid"]
    assert identities[0]["parent_pid"] == record["parent_pid"]
    assert record["executable"] != record["base_executable"] and identities[0]["cpu"]["created_100ns"] > 0


@pytest.mark.parametrize("base", ["owned-base.exe", None, "", "missing"])
def test_observer_uses_runtime_base_executable_with_original_hidden_flags_and_timer(monkeypatch, base):
    calls, timers = [], []
    monkeypatch.setattr(runner.sys, "executable", "owned-venv.exe")
    if base == "missing":
        monkeypatch.delattr(runner.sys, "_base_executable", raising=False)
    else:
        monkeypatch.setattr(runner.sys, "_base_executable", base, raising=False)
    monkeypatch.setattr(runner.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    def launch(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(poll=lambda: 0, returncode=0, wait=lambda: 0,
                               stdout=io.BytesIO(), stderr=io.BytesIO())

    def timer(seconds, callback, args):
        result = SimpleNamespace(start=lambda: None, cancel=lambda: None, ident=None)
        timers.append((seconds, callback, args, result))
        return result

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.threading, "Timer", timer)
    observer = runner._Observer(123)
    expected = "owned-base.exe" if base == "owned-base.exe" else "owned-venv.exe"
    assert calls == [([expected, str(Path(runner.__file__).with_name("windows_child_observer.py")), "--pid", "123"],
                      {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": 0x08000000})]
    assert len(timers) == 1 and timers[0][0] == 5 and timers[0][2] == ("observer-deadline",)
    assert timers[0][1] == observer._stop and timers[0][3].daemon
    assert observer.finish()["returncode"] == 0
