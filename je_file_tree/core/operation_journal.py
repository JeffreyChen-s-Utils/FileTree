"""Atomic append-only audit segments for approved operations, never file contents or restore promises."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO

from je_file_tree.core.export import _atomic_file
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import unpack_snapshot

if os.name == "nt":
    import msvcrt
else:
    import fcntl

_SEGMENT_BYTES = 4 * 1024 * 1024
_EVENT_BYTES = 256 * 1024
_LOCK_SECONDS = 2
_SEGMENT = re.compile(r"actions-(\d{8})-([0-9a-f]{32})\.jsonl\Z")
_STATUSES = frozenset({"approved", "moved", "restored", "linked", "compacted", "skipped", "failed"})
_IDENTITY_PARTS = 2


@dataclass(frozen=True, slots=True)
class OperationOutcome:
    """Observed status, stable reason detail and optional platform-provided Trash destination."""

    status: str
    detail: str = ""
    destination: str | None = None


@dataclass(frozen=True, slots=True)
class OperationRecord:
    """One approved/result event, with stable IDs and the original item identity."""

    id: str
    batch: str
    timestamp: str
    source: str
    identity: tuple[int, int] | None
    reason: str
    outcome: OperationOutcome

    @classmethod
    def approved(cls, batch: str, node: Node, reason: str) -> OperationRecord:
        """Capture the original path/identity before any tree detachment or platform move."""
        identity = unpack_snapshot(node.snapshot).identity if node.snapshot is not None else None
        return cls(uuid.uuid4().hex, batch, _now(), node.path, identity, reason, OperationOutcome("approved"))

    def finished(self, outcome: OperationOutcome) -> OperationRecord:
        """Append a new event for the same operation; the approved event is never edited."""
        return replace(self, timestamp=_now(), outcome=outcome)


@dataclass(frozen=True, slots=True)
class JournalRead:
    """Latest event per operation plus damaged/unavailable segment counts."""

    records: list[OperationRecord]
    invalid: int = 0
    unavailable: int = 0


class OperationJournal:
    """Daily/4 MB atomic JSONL segments, retained for 90 days and at most 50 MB by default."""

    def __init__(self, directory: str | os.PathLike[str], *, days: int = 90, max_bytes: int = 50 * 1024 * 1024) -> None:
        if type(days) is not int or days <= 0 or type(max_bytes) is not int or max_bytes < _EVENT_BYTES:
            raise ValueError("invalid journal retention")
        self.directory = Path(directory)
        self.days, self.max_bytes = days, max_bytes

    def append(self, records: Sequence[OperationRecord]) -> None:
        """Append approved/result events atomically; an error preserves the previous complete segment."""
        if not records:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        with _lock(self.directory / ".journal-lock"):
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            limit = min(_SEGMENT_BYTES, self.max_bytes)
            paths = self._segments()
            current = next((path for path in reversed(paths) if path.name.startswith(f"actions-{today}-")), None)
            for block in _blocks(records, limit):
                if current is None or current.stat().st_size + len(block) > limit:
                    current = self.directory / f"actions-{today}-{uuid.uuid4().hex}.jsonl"
                _append_atomic(current, block)
            self._retain()

    def recent(self, *, limit: int = 500) -> JournalRead:
        """Read latest outcomes on a worker; an approved-only operation has an unknown final outcome."""
        latest: dict[str, OperationRecord] = {}
        invalid = unavailable = 0
        budget = self.max_bytes
        for path in reversed(self._segments()):
            give_way()
            try:
                size = path.stat().st_size
                if size > budget:
                    unavailable += 1
                    continue
                budget -= size
                with path.open(encoding="utf-8") as stream:
                    for line in iter(lambda: stream.readline(_EVENT_BYTES + 1), ""):
                        if len(line.encode("utf-8")) > _EVENT_BYTES:
                            invalid += 1
                            break
                        try:
                            record = _decode(line)
                        except (ValueError, TypeError, KeyError, RecursionError):
                            invalid += 1
                            continue
                        previous = latest.get(record.id)
                        if (previous is None or previous.outcome.status == "approved"
                                or (record.outcome.status != "approved" and record.timestamp >= previous.timestamp)):
                            latest[record.id] = record
            except (OSError, UnicodeError):
                unavailable += 1
        records = sorted(latest.values(), key=lambda record: record.timestamp, reverse=True)
        return JournalRead(records[:max(0, limit)], invalid, unavailable)

    def _segments(self) -> list[Path]:
        if not self.directory.exists():
            return []
        return sorted((path for path in self.directory.iterdir()
                       if _SEGMENT.fullmatch(path.name) and path.is_file() and not path.is_symlink()),
                      key=lambda path: (path.stat().st_mtime_ns, path.name))

    def _retain(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.days)).strftime("%Y%m%d")
        paths = self._segments()
        total = sum(path.stat().st_size for path in paths)
        for path in paths[:-1]:  # Never remove the segment just written, even under a tiny budget.
            if path.name[8:16] < cutoff or total > self.max_bytes:
                size = path.stat().st_size
                path.unlink()  # Only this application's recognized journal segments, never scanned entries.
                total -= size


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _encode(record: OperationRecord) -> bytes:
    if record.outcome.status not in _STATUSES:
        raise ValueError("invalid operation outcome")
    value = {"version": 1, "id": record.id, "batch": record.batch, "time": record.timestamp,
             "source": record.source, "identity": list(map(str, record.identity)) if record.identity else None,
             "reason": record.reason, "result": record.outcome.status, "detail": record.outcome.detail,
             "destination": record.outcome.destination}
    encoded = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > _EVENT_BYTES:
        raise ValueError("operation record too large")
    return encoded


def _decode(line: str) -> OperationRecord:
    value = json.loads(line)
    fields = {"version", "id", "batch", "time", "source", "identity", "reason", "result", "detail", "destination"}
    if (not isinstance(value, dict) or set(value) != fields
            or type(value["version"]) is not int or value["version"] != 1):
        raise ValueError("invalid journal record")
    for key in ("id", "batch", "time", "source", "reason", "result", "detail"):
        if not isinstance(value[key], str):
            raise ValueError("invalid journal field")
    timestamp = datetime.fromisoformat(value["time"])
    if value["result"] not in _STATUSES or timestamp.tzinfo is None:
        raise ValueError("invalid journal status or time")
    destination = value["destination"]
    if destination is not None and not isinstance(destination, str):
        raise ValueError("invalid destination")
    identity = value["identity"]
    if identity is not None:
        if (not isinstance(identity, list) or len(identity) != _IDENTITY_PARTS
                or any(not isinstance(part, str) or not part.isdecimal() for part in identity)):
            raise ValueError("invalid identity")
        identity = (int(identity[0]), int(identity[1]))
    return OperationRecord(value["id"], value["batch"],
                           timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds"),
                           value["source"], identity, value["reason"],
                           OperationOutcome(value["result"], value["detail"], destination))


def _blocks(records: Sequence[OperationRecord], limit: int) -> Iterator[bytes]:
    block = bytearray()
    for record in records:
        encoded = _encode(record)
        if block and len(block) + len(encoded) > limit:
            yield bytes(block)
            block.clear()
        block.extend(encoded)
    if block:
        yield bytes(block)


def _append_atomic(path: Path, block: bytes) -> None:
    handle, temporary = tempfile.mkstemp(prefix=".journal-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            if path.exists():
                with path.open("rb") as previous:
                    shutil.copyfileobj(previous, stream)
            stream.write(block)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    with path.open("a+b") as stream:
        deadline = time.monotonic() + _LOCK_SECONDS
        while True:
            try:
                _file_lock(stream, acquire=True)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
        try:
            # Lock the byte even beyond EOF before initializing it. Two first writers must
            # not race a flush against another writer's already-held Windows byte lock.
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            yield
        finally:
            _file_lock(stream, acquire=False)


def _file_lock(stream: BinaryIO, *, acquire: bool) -> None:
    stream.seek(0)
    if os.name == "nt":
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB if acquire else fcntl.LOCK_UN)


def export_journal(records: Sequence[OperationRecord], target: str | os.PathLike[str], *,
                   home: str | None = None) -> int:
    """Atomically export metadata CSV, replacing home-directory prefixes with {HOME}."""
    home = os.path.abspath(home or os.path.expanduser("~"))
    with _atomic_file(target, encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(("time", "original_path", "identity", "reason", "result", "detail", "trash_destination"))
        for record in records:
            status = "unknown" if record.outcome.status == "approved" else record.outcome.status
            detail = "approved only; final outcome unknown" if status == "unknown" else record.outcome.detail
            writer.writerow((record.timestamp, redact_home(record.source, home), str(record.identity), record.reason,
                             status, detail,
                             redact_home(record.outcome.destination, home) if record.outcome.destination else ""))
    return len(records)


def redact_home(path: str, home: str) -> str:
    """Redact a directory prefix, preserving a similarly named sibling and paths on other volumes."""
    try:
        if os.path.normcase(os.path.commonpath((path, home))) == os.path.normcase(home):
            relative = os.path.relpath(path, home)
            return "{HOME}" if relative == "." else os.path.join("{HOME}", relative)
    except ValueError:
        return path  # A different volume has no common prefix.
    return path


@dataclass(frozen=True, slots=True)
class JournalApproval:
    """The journal and explicit reasons for one user-approved GUI selection."""

    journal: OperationJournal
    reasons: dict[Node, str]
