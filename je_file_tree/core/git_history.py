"""Bounded, cancellable read-only Git object inspection without lazy network fetching."""

from __future__ import annotations

import heapq
import os
import queue
import re
import subprocess  # nosec B404 - fixed Git plumbing commands without a shell
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO

from je_file_tree.core.pacing import give_way

_LINE_LIMIT = 256
_ERROR_LIMIT = 16384
_OID = re.compile(rb"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_TYPES = {b"blob", b"tree", b"commit", b"tag"}
_OBJECT_FIELDS = 3


class GitHistoryCancelledError(Exception):
    """The user stopped a repository inspection before it completed."""


@dataclass(frozen=True, slots=True)
class GitObject:
    """Reachable object metadata; size is the uncompressed length, not recoverable disk space."""

    oid: str
    kind: str
    size: int


@dataclass(frozen=True, slots=True)
class GitHistory:
    """Largest reachable objects, complete counts, and loose objects which GC may pack."""

    rows: list[GitObject]
    count: int
    logical: int
    loose: int


def _environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS="0",
                       GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    return environment


def _command(path: str, *arguments: str) -> list[str]:
    return ["git", "--no-pager", "--no-lazy-fetch", "--no-optional-locks", "--no-replace-objects",
            "-c", "core.fsmonitor=false", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
            "-C", os.path.abspath(path), *arguments]


def _enqueue(item: bytes | OSError | None, lines: queue.Queue, stopped: threading.Event) -> bool:
    while not stopped.is_set():
        try:
            lines.put(item, timeout=.05)
            return True
        except queue.Full:
            continue
    return False


def _read_lines(stream: BinaryIO, lines: queue.Queue, stopped: threading.Event) -> None:
    try:
        while not stopped.is_set():
            line = stream.readline(_LINE_LIMIT)
            if not _enqueue(line or None, lines, stopped) or not line:
                return
    except OSError as error:
        _enqueue(error, lines, stopped)


def _read_errors(stream: BinaryIO, errors: bytearray) -> None:
    try:
        while chunk := stream.read(4096):
            errors.extend(chunk[:max(0, _ERROR_LIMIT - len(errors))])
    except OSError as error:
        errors.extend(str(error).encode("utf-8")[:max(0, _ERROR_LIMIT - len(errors))])


class _GitProcess:
    """Drain bounded pipes independently so cancellation cannot deadlock on a full stdout/stderr."""

    def __init__(self, command: list[str], environment: dict[str, str], *, stdin: BinaryIO | None = None,
                 pipe_only: bool = False) -> None:
        self.process = subprocess.Popen(  # noqa: S603 # nosec B603 - fixed internal Git plumbing
            command, env=environment, stdin=stdin or subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        self.stopped, self.errors, self.output = threading.Event(), bytearray(), queue.Queue(maxsize=64)
        self.readers = [threading.Thread(target=_read_errors, args=(self.process.stderr, self.errors))]
        if not pipe_only:
            self.readers.append(threading.Thread(target=_read_lines,
                                                  args=(self.process.stdout, self.output, self.stopped)))
        for reader in self.readers:
            reader.start()

    def lines(self, cancel: threading.Event | None, deadline: float) -> Iterator[bytes]:
        """Yield bounded metadata lines while checking stop and deadline between replies."""
        while True:
            give_way()
            if cancel is not None and cancel.is_set():
                raise GitHistoryCancelledError
            if time.monotonic() > deadline:
                raise OSError("Git inspection timed out")
            try:
                line = self.output.get(timeout=.05)
            except queue.Empty:
                continue
            if line is None:
                return
            if isinstance(line, OSError):
                raise line
            yield line

    def check(self) -> None:
        """Require a successful exit, preserving only bounded stderr on failure."""
        try:
            code = self.process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            raise OSError("Git did not finish after its output ended") from error
        self.readers[0].join()
        if code:
            raise OSError(self.errors.decode("utf-8", errors="replace") or f"Git exited with status {code}")

    def close(self) -> None:
        """Reap this process and its pipe readers, never terminating unrelated programs."""
        self.stopped.set()
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        for reader in self.readers:
            reader.join()
        for stream in (self.process.stdout, self.process.stderr):
            stream.close()


def _object(line: bytes) -> GitObject:
    fields = line.split()
    if len(fields) != _OBJECT_FIELDS or not _OID.fullmatch(fields[0]) or fields[1] not in _TYPES:
        raise OSError("Git object metadata is missing or malformed; missing objects are not downloaded")
    try:
        size = int(fields[2])
    except ValueError as error:
        raise OSError("Invalid Git object length") from error
    if size < 0:
        raise OSError("Invalid Git object length")
    return GitObject(fields[0].decode("ascii"), fields[1].decode("ascii"), size)


def _largest(path: str, limit: int, cancel: threading.Event | None,
             deadline: float) -> tuple[list[GitObject], int, int]:
    environment = _environment()
    revision = _GitProcess(_command(path, "rev-list", "--objects", "--all", "--no-object-names"),
                           environment, pipe_only=True)
    objects = None
    try:
        objects = _GitProcess(_command(path, "cat-file", "--batch-check", "--buffer"), environment,
                             stdin=revision.process.stdout)
        revision.process.stdout.close()
        heap, count, logical = [], 0, 0
        for line in objects.lines(cancel, deadline):
            row = _object(line)
            count, logical = count + 1, logical + row.size
            item = (row.size, row.oid, count, row)
            if len(heap) < limit:
                heapq.heappush(heap, item)
            elif item[:2] > heap[0][:2]:
                heapq.heapreplace(heap, item)
        revision.check()
        objects.check()
        return [item[3] for item in sorted(heap, reverse=True)], count, logical
    finally:
        if objects is not None:
            objects.close()
        revision.close()


def _loose(path: str, cancel: threading.Event | None, deadline: float) -> int:
    process = _GitProcess(_command(path, "count-objects", "-v"), _environment())
    count = None
    try:
        for line in process.lines(cancel, deadline):
            if line.startswith(b"count: "):
                count = int(line.partition(b": ")[2])
        process.check()
    finally:
        process.close()
    if count is None or count < 0:
        raise OSError("Git did not report a valid loose-object count")
    return count


def git_history(path: str, *, limit: int = 1000, cancel: threading.Event | None = None,
                seconds: float = 120) -> GitHistory:
    """Inspect all refs with fixed Git plumbing, keeping only the largest ``limit`` objects.

    Paths are supplied through -C, never a shell. Git must support --no-lazy-fetch; older Git fails
    before reading objects. Optional locks, automatic maintenance and filesystem-monitor hooks are
    disabled. No gc/repack, modification or network fetching is performed. Stored-object paths are
    intentionally omitted because rev-list object-name hints can be ambiguous or change newlines.
    """
    if limit < 1 or seconds <= 0:
        raise ValueError("Git inspection limits must be positive")
    deadline = time.monotonic() + seconds
    rows, count, logical = _largest(path, limit, cancel, deadline)
    return GitHistory(rows, count, logical, _loose(path, cancel, deadline))
