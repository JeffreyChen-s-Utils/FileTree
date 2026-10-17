"""Capture a slow owned Windows child's native waits without resetting its subprocess deadline."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import threading
import time

_LIMIT = 65536


class _PipeCapture:
    def __init__(self, stream) -> None:
        self.stream = stream
        self.data = bytearray()
        self.truncated = False
        self.error = None
        self.thread = threading.Thread(target=self._read, daemon=True)

    def _read(self) -> None:
        try:
            with self.stream:
                while chunk := self.stream.read(4096):
                    remaining = _LIMIT-len(self.data)
                    self.data.extend(chunk[:remaining])
                    self.truncated |= len(chunk) > remaining
        except OSError as error:
            self.error = {"type": type(error).__name__, "message": str(error)[:512]}

    def finish(self) -> None:
        if self.thread.ident is not None:
            self.thread.join()
        else:
            self.stream.close()


class _Observer:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.process = None
        self.timer = None
        self.error = None
        self.stop_reason = None
        self.captures = []
        try:
            script = Path(__file__).with_name("windows_child_observer.py")
            executable = getattr(sys, "_base_executable", None) or sys.executable
            self.process = subprocess.Popen(  # noqa: S603 - fixed observer; validates captured sibling identity
                [executable, str(script), "--pid", str(pid)], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            for stream in (self.process.stdout, self.process.stderr):
                self.captures.append(_PipeCapture(stream))
            self.timer = threading.Timer(5, self._stop, args=("observer-deadline",))
            self.timer.daemon = True
            self.timer.start()
            for capture in self.captures:
                capture.thread.start()
        except (OSError, RuntimeError) as error:
            self.error = {"type": type(error).__name__, "message": str(error)[:512]}
            self._failed_start()
        except BaseException:
            self._failed_start()
            raise

    def _cancel_timer(self) -> None:
        if self.timer is not None:
            self.timer.cancel()
            if self.timer.ident is not None:
                self.timer.join()

    def _failed_start(self) -> None:
        self._cancel_timer()
        if self.process is not None:
            self._stop("observer-start-failed")
            self.process.wait()
            for capture in self.captures:
                capture.finish()
            for stream in (self.process.stdout, self.process.stderr):
                stream.close()
            self.process = None

    def _stop(self, reason: str = "parent-finished") -> None:
        if self.process is not None and self.process.poll() is None:
            if self.stop_reason is None:
                self.stop_reason = reason
            self.process.kill()

    def finish(self) -> dict:
        """Join only this observer; preserve partial lines and observation errors separately."""
        if self.process is None:
            return {"status": "start-failed", "child_pid": self.pid, "error": self.error}
        self._cancel_timer()
        self._stop()
        self.process.wait()
        for capture in self.captures:
            capture.finish()
        stdout, stderr = (capture.data for capture in self.captures)
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
        errors = {name: capture.error for name, capture in zip(("stdout", "stderr"), self.captures, strict=True)
                  if capture.error}
        return {"status": "observed", "child_pid": self.pid, "returncode": self.process.returncode, "records": records,
                "stop_reason": self.stop_reason,
                "invalid_records": invalid, "output_truncated": any(capture.truncated for capture in self.captures),
                **({"capture_errors": errors} if errors else {}),
                "stderr": stderr[:_LIMIT].decode("utf-8", errors="replace")}


def _finish(observer: _Observer) -> dict:
    try:
        return observer.finish()
    except OSError as error:
        return {"status": "observation-failed", "type": type(error).__name__, "message": str(error)[:512]}


def _finish_samples(observers: list[_Observer]) -> dict:
    records = [_finish(observer) for observer in observers]
    if not records:
        return {"status": "not-sampled"}
    return records[0] if len(records) == 1 else {**records[0], "later_samples": records[1:]}


def _communicate(process: subprocess.Popen, started: float, timeout: float,
                 sample_after: float, observers: list[_Observer]) -> tuple[bytes, bytes]:
    # Leave each fixed five-second observer bound intact; collect it only after the target exits.
    times = [sample_after]
    if timeout-5 >= sample_after+5:
        times.append(timeout-5)
    for when in times:
        if when >= timeout:
            break
        try:
            return process.communicate(timeout=max(0, when-(time.monotonic()-started)))
        except subprocess.TimeoutExpired:
            if sys.platform == "win32" and process.poll() is None and time.monotonic()-started < timeout:
                observers.append(_Observer(process.pid))
    return process.communicate(timeout=max(0, timeout-(time.monotonic()-started)))


def run_observed(command: list[str], *, timeout: float, env: dict[str, str] | None = None,
                 check: bool = False, sample_after: float = 5) -> subprocess.CompletedProcess:
    """Run once; take at most two still-live Windows samples within the original target deadline.

    Keep the first sample's report shape; an optional later_samples list holds the final-window
    observation. Result collection follows target exit; every wait uses the original deadline's remainder.
    """
    started = time.monotonic()
    observers: list[_Observer] = []
    observation = {"status": "not-sampled"}
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:  # noqa: S603
        try:
            stdout, stderr = _communicate(process, started, timeout, sample_after, observers)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            error = subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
            observation = _finish_samples(observers)
            error.process_observation = observation
            raise error from None
        except BaseException:
            # Match subprocess.run cleanup even when diagnostics or caller cancellation interrupts the wait.
            process.kill()
            process.wait()
            raise
        finally:
            if observers and observation["status"] == "not-sampled":
                observation = _finish_samples(observers)
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        result.process_observation = observation
        if check and result.returncode:
            error = subprocess.CalledProcessError(result.returncode, command, output=stdout, stderr=stderr)
            error.process_observation = observation
            raise error
        return result
