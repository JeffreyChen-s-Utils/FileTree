"""Capture a slow owned Windows child's native waits without resetting its subprocess deadline."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import threading
import time

_LIMIT = 65536


class _Observer:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.process = None
        self.timer = None
        self.error = None
        self.stop_reason = None
        try:
            script = Path(__file__).with_name("windows_child_observer.py")
            executable = getattr(sys, "_base_executable", None) or sys.executable
            self.process = subprocess.Popen(  # noqa: S603 - fixed observer; validates captured sibling identity
                [executable, str(script), "--pid", str(pid)], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            self.timer = threading.Timer(5, self._stop, args=("observer-deadline",))
            self.timer.daemon = True
            self.timer.start()
        except OSError as error:
            self.error = {"type": type(error).__name__, "message": str(error)[:512]}

    def _stop(self, reason: str = "parent-finished") -> None:
        if self.process is not None and self.process.poll() is None:
            self.stop_reason = reason
            self.process.kill()

    def finish(self) -> dict:
        """Join only this observer; preserve partial lines and observation errors separately."""
        if self.process is None:
            return {"status": "start-failed", "child_pid": self.pid, "error": self.error}
        self.timer.cancel()
        self._stop()
        stdout, stderr = self.process.communicate()
        records, invalid = [], 0
        for line in stdout[:_LIMIT].splitlines()[:32]:
            try:
                record = json.loads(line)
            except (ValueError, RecursionError):
                invalid += 1
                continue
            if isinstance(record, dict):
                records.append(record)
            else:
                invalid += 1
        return {"status": "observed", "child_pid": self.pid, "returncode": self.process.returncode, "records": records,
                "stop_reason": self.stop_reason,
                "invalid_records": invalid, "output_truncated": len(stdout) > _LIMIT or len(stderr) > _LIMIT,
                "stderr": stderr[:_LIMIT].decode("utf-8", errors="replace")}


def _finish(observer: _Observer) -> dict:
    try:
        return observer.finish()
    except OSError as error:
        return {"status": "observation-failed", "type": type(error).__name__, "message": str(error)[:512]}


def run_observed(command: list[str], *, timeout: float, env: dict[str, str] | None = None,
                 check: bool = False, sample_after: float = 5) -> subprocess.CompletedProcess:
    """Run once; sample only a still-live slow Windows child and retain its actual output/outcome."""
    started = time.monotonic()
    observer = None
    observation = {"status": "not-sampled"}
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:  # noqa: S603
        try:
            try:
                stdout, stderr = process.communicate(timeout=min(timeout, sample_after))
            except subprocess.TimeoutExpired:
                if sys.platform == "win32" and process.poll() is None and time.monotonic()-started < timeout:
                    observer = _Observer(process.pid)
                stdout, stderr = process.communicate(timeout=max(0, timeout-(time.monotonic()-started)))
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            error = subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
            if observer is not None:
                observation = _finish(observer)
            error.process_observation = observation
            raise error from None
        except BaseException:
            # Match subprocess.run cleanup even when diagnostics or caller cancellation interrupts the wait.
            process.kill()
            process.wait()
            raise
        finally:
            if observer is not None and observation["status"] == "not-sampled":
                observation = _finish(observer)
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        result.process_observation = observation
        if check and result.returncode:
            error = subprocess.CalledProcessError(result.returncode, command, output=stdout, stderr=stderr)
            error.process_observation = observation
            raise error
        return result
