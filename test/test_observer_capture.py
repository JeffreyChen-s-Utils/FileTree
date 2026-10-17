"""Observer pipes must drain during capture while retained diagnostics remain bounded."""

import io
import os
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from tools import observed_process as runner


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows anonymous-pipe and WCT capture")
def test_owned_observer_completes_full_thread_capture_before_finish(tmp_path):
    ready = tmp_path / "threads-ready"
    code = """
import sys, threading
from pathlib import Path
event = threading.Event()
workers = [threading.Thread(target=event.wait, daemon=True) for _ in range(20)]
for worker in workers: worker.start()
Path(sys.argv[1]).touch()
sys.stdin.readline()
"""
    executable = getattr(sys, "_base_executable", None) or sys.executable
    with subprocess.Popen(  # noqa: S603 - fresh owned held-live threads; no other process or source touched
            [executable, "-c", code, str(ready)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE) as target:
        observer = None
        try:
            deadline = time.monotonic() + 10
            while not ready.exists():
                assert target.poll() is None and time.monotonic() < deadline
                time.sleep(.01)
            observer = runner._Observer(target.pid)
            observer.process.wait(timeout=7)
            result = observer.finish()
            assert result["returncode"] == 0 and result["stop_reason"] is None, result
            records = result["records"]
            assert records[0]["pid"] == target.pid and records[0]["parent_pid"] == os.getpid()
            assert records[1]["count"] >= 21 and records[1]["truncated"]
            assert sum(r["event"] == "chain" for r in records) == 16
            assert records[-1]["event"] == "complete" and not result["output_truncated"]
            assert target.poll() is None and observer.finish() == result
        finally:
            if observer is not None:
                observer.finish()
            target.communicate(b"release\n", timeout=5)
        assert target.returncode == 0


def test_real_producer_can_fill_both_pipes_beyond_report_caps_before_finish(monkeypatch):
    original = subprocess.Popen
    launched = []
    code = "import sys;sys.stdout.buffer.write(b'x'*200000);sys.stdout.flush();" \
           "sys.stderr.buffer.write(b'e'*200000);sys.stderr.flush()"

    def launch(command, **kwargs):
        assert command[-2:] == ["--pid", "123"]
        assert kwargs == {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "creationflags": 0}
        child = original([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        launched.append(child)
        return child

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    observer = runner._Observer(123)
    try:
        observer.process.wait(timeout=7)
        result = observer.finish()
        assert result["returncode"] == 0 and result["stop_reason"] is None, result
        assert result["output_truncated"] and len(result["stderr"]) == 65536
        assert result["invalid_records"] == 1 and result["records"] == []
        assert len(launched) == 1
    finally:
        observer.finish()
    assert all(not capture.thread.is_alive() and capture.stream.closed for capture in observer.captures)
    assert all(len(capture.data) == 65536 for capture in observer.captures)
    assert not observer.timer.is_alive()


@pytest.mark.parametrize("size", [65535, 65536, 65537, 200000])
def test_stream_capture_retains_exact_cap_and_still_drains_all_input(size):
    stream = io.BytesIO(b"x"*size)
    capture = runner._PipeCapture(stream)
    capture.thread.start()
    capture.finish()
    assert capture.data == b"x"*min(size, 65536)
    assert capture.truncated is (size > 65536)
    assert capture.error is None and stream.closed and not capture.thread.is_alive()


def test_stream_read_failure_retains_partial_bytes_and_reports_the_error():
    class Broken(io.BytesIO):
        def read(self, _size):
            if self.tell():
                raise OSError("owned read failure")
            return super().read(4)

    capture = runner._PipeCapture(Broken(b"kept"))
    capture.thread.start()
    capture.finish()
    assert capture.data == b"kept" and not capture.truncated
    assert capture.error == {"type": "OSError", "message": "owned read failure"}
    assert capture.stream.closed and not capture.thread.is_alive()


@pytest.mark.parametrize("error", [RuntimeError("reader unavailable"), KeyboardInterrupt()])
def test_partial_reader_start_failure_reaps_observer_and_closes_both_pipes(monkeypatch, error):
    original_launch, original_capture = subprocess.Popen, runner._PipeCapture
    launched, captures = [], []

    def launch(_command, **_kwargs):
        process = original_launch([sys.executable, "-c", "import time;time.sleep(30)"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        launched.append(process)
        return process

    def capture(stream):
        result = original_capture(stream)
        captures.append(result)
        if len(captures) == 2:
            def fail():
                raise error
            monkeypatch.setattr(result.thread, "start", fail)
        return result

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(runner, "_PipeCapture", capture)
    if isinstance(error, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt) as caught:
            runner._Observer(123)
        assert caught.value is error
    else:
        observer = runner._Observer(123)
        result = observer.finish()
        assert result == {"status": "start-failed", "child_pid": 123,
                          "error": {"type": "RuntimeError", "message": "reader unavailable"}}
        assert not observer.timer.is_alive()
    assert len(launched) == 1 and launched[0].poll() is not None
    assert all(c.stream.closed and not c.thread.is_alive() for c in captures)


def test_partial_read_errors_remain_separate_from_native_exit_and_records():
    class Broken(io.BytesIO):
        def read(self, _size):
            raise OSError("stream unavailable")

    observer = runner._Observer.__new__(runner._Observer)
    observer.pid, observer.timer, observer.stop_reason = 123, None, None
    observer.process = SimpleNamespace(poll=lambda: 7, wait=lambda: 7, returncode=7)
    observer.captures = [runner._PipeCapture(Broken()),
                         runner._PipeCapture(io.BytesIO(b"native stderr"))]
    for capture in observer.captures:
        capture.thread.start()
    result = observer.finish()
    assert result["returncode"] == 7 and result["stderr"] == "native stderr"
    assert result["records"] == [] and result["stop_reason"] is None
    assert result["capture_errors"] == {"stdout": {"type": "OSError", "message": "stream unavailable"}}
    assert not result["output_truncated"] and all(c.stream.closed for c in observer.captures)


@pytest.mark.parametrize("stop", ["parent-finished", "observer-deadline"])
def test_stopping_live_observer_keeps_flushed_partial_streams_and_joins_readers(monkeypatch, tmp_path, stop):
    original, launched = subprocess.Popen, []
    ready = tmp_path / "flushed"
    code = "import sys;from pathlib import Path;" \
           "print('{\"event\":\"identity\"}',flush=True);print('partial',file=sys.stderr,flush=True);" \
           "Path(sys.argv[1]).touch();sys.stdin.readline()"

    def launch(_command, **_kwargs):
        process = original([sys.executable, "-c", code, str(ready)], stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        launched.append(process)
        return process

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    observer = runner._Observer(123)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists():
            assert observer.process.poll() is None and time.monotonic() < deadline
            time.sleep(.01)
        if stop == "observer-deadline":
            observer.timer.function(*observer.timer.args)
        result = observer.finish()
        assert result["stop_reason"] == stop and result["returncode"] != 0
        assert result["records"] == [{"event": "identity"}] and result["stderr"].strip() == "partial"
        assert not result["output_truncated"] and result["invalid_records"] == 0
        assert observer.finish() == result and len(launched) == 1
    finally:
        observer.finish()
        observer.process.stdin.close()
    assert not observer.timer.is_alive()
    assert all(c.stream.closed and not c.thread.is_alive() for c in observer.captures)
