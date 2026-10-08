"""Dated recurring observations and expiry checks; metadata never authorizes a source operation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import hashlib
import heapq
import json
import os
import re
import threading

from je_file_tree.core.background import MonitorConfig, ScanAttempt
from je_file_tree.core.cleanup import DETAILS, RULES, find_cleanup
from je_file_tree.core.cleanup_policy import CleanupPolicy
from je_file_tree.core.compare import SavedScan, folder_key
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import stable_snapshot, unpack_snapshot

MAX_ROWS = 100
MAX_BYTES = 48 * 1024
_MAX_INTEGER = 2**63 - 1
_MAX_PATH = 1024
_SECONDS_PER_HOUR = 3600
_COVERAGE_FIELDS = 5
_MAX_DATE = 64
_MAX_DEVICE = 2**64 - 1
_MAX_INODE = 2**128 - 1
_IDENTITY_FIELDS = 2
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class ProposalCancelledError(Exception):
    """The caller canceled observation preparation or validation; no proposal is published."""


def _check(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise ProposalCancelledError


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def _hash(value: str | None, *, optional: bool = False) -> None:
    if not (optional and value is None) and (not isinstance(value, str) or not _HASH.fullmatch(value)):
        raise ValueError("Invalid recurring observation fingerprint")


def _integer(value: int) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_INTEGER:
        raise ValueError("Invalid recurring observation total")


def _path_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def policy_version(policy: CleanupPolicy) -> str:
    """Fingerprint built-in definitions and effective overrides, including disabled/empty-folder rules."""
    effective = [asdict(policy.setting(key)) for key in sorted(DETAILS)]
    return _digest({"format": 1, "definitions": [asdict(rule) for rule in RULES],
                    "details": {key: asdict(value) for key, value in DETAILS.items()},
                    "effective": effective, "exclusions": policy.exclusions})


@dataclass(frozen=True, slots=True)
class Candidate:
    """A bounded observed rule/path/size and metadata fingerprint, never a loaded operation target."""

    path: str
    rule: str
    size: int
    signature: str | None

    def __post_init__(self) -> None:
        if (not isinstance(self.path, str) or not os.path.isabs(self.path) or len(self.path) > _MAX_PATH
                or any(char in self.path for char in ("\0", "\n", "\r"))
                or not isinstance(self.rule, str) or self.rule not in DETAILS):
            raise ValueError("Invalid recurring candidate")
        _integer(self.size)
        _hash(self.signature, optional=True)


@dataclass(frozen=True, slots=True)
class Baseline:
    """Bounded historical observations; partial candidate inventories never prove a path is new."""

    root: str
    created_at: float
    policy: str
    signature: str | None
    identity: tuple[int, int] | None
    coverage: tuple[int, int, int, int, int]
    candidates: tuple[Candidate, ...]
    candidate_count: int
    size: int
    saved: str = ""

    def __post_init__(self) -> None:
        ScanAttempt(self.root, self.created_at, self.policy)
        _hash(self.signature, optional=True)
        if self.identity is not None:
            if (not isinstance(self.identity, tuple) or len(self.identity) != _IDENTITY_FIELDS
                    or any(type(value) is not int for value in self.identity)
                    or not 0 <= self.identity[0] <= _MAX_DEVICE or not 0 < self.identity[1] <= _MAX_INODE):
                raise ValueError("Invalid recurring root identity")
        elif self.signature is not None:
            raise ValueError("Known recurring signature requires a root identity")
        if not isinstance(self.coverage, tuple) or len(self.coverage) != _COVERAGE_FIELDS:
            raise ValueError("Invalid recurring coverage")
        for value in (*self.coverage, self.candidate_count, self.size):
            _integer(value)
        if (not isinstance(self.candidates, tuple) or len(self.candidates) > MAX_ROWS
                or self.candidate_count < len(self.candidates) or not isinstance(self.saved, str)):
            raise ValueError("Invalid recurring inventory")
        if self.saved and (len(self.saved) > _MAX_DATE or datetime.fromisoformat(self.saved).tzinfo is None):
            raise ValueError("Invalid recurring history date")
        keys = set()
        root_key = _path_key(self.root)
        for candidate in self.candidates:
            if not isinstance(candidate, Candidate):
                raise ValueError("Invalid recurring candidate type")
            key = _path_key(candidate.path)
            if key in keys or os.path.commonpath((key, root_key)) != root_key or key == root_key:
                raise ValueError("Recurring candidate is ambiguous or outside its root")
            keys.add(key)

    @property
    def complete(self) -> bool:
        """All scopes and file errors are included, independently of identity availability."""
        return not any(self.coverage[1:])

    @property
    def inventory_complete(self) -> bool:
        """Every observed candidate must be captured before absence can mean a new candidate."""
        return self.complete and self.candidate_count == len(self.candidates)


@dataclass(frozen=True, slots=True)
class ProposalContext:
    """One specific durable schedule claim and preparation date; validity ends at the next due time."""

    attempt: ScanAttempt
    interval_hours: int
    prepared_at: float

    def __post_init__(self) -> None:
        config = MonitorConfig(True, interval_hours=self.interval_hours, roots=(self.attempt.root,))
        ScanAttempt(self.attempt.root, self.prepared_at, self.attempt.schedule_id)
        if self.attempt.state not in ("claimed", "complete") or self.prepared_at < self.attempt.claimed_at:
            raise ValueError("Invalid recurring schedule context")
        ScanAttempt(self.attempt.root, self.attempt.claimed_at + config.interval_hours * _SECONDS_PER_HOUR,
                    self.attempt.schedule_id)

    @property
    def expires_at(self) -> float:
        """Missed schedules expire the old proposal instead of silently renewing it."""
        return self.attempt.claimed_at + self.interval_hours * _SECONDS_PER_HOUR


@dataclass(frozen=True, slots=True)
class Growth:
    """One observed folder growth; None before denotes a newly observed folder, never estimated savings."""

    path: str
    before: int | None
    after: int

    @property
    def change(self) -> int:
        """Logical growth relative to the explicitly matched historical scan."""
        return self.after - (self.before or 0)


@dataclass(frozen=True, slots=True)
class RecurringProposal:
    """Informational bounded rows from an actual current scan; constructing it performs no actions."""

    baseline: Baseline
    context: ProposalContext
    new_junk: tuple[Candidate, ...]
    growth: tuple[Growth, ...]
    comparison_complete: bool
    previous_saved: str


def tree_signature(root: Node, *, cancel: threading.Event | None = None) -> str | None:
    """Order-independent digest over every captured entry; no stat, payload read or Node field is added."""
    if root.path is None:
        raise ValueError("Recurring observations require an individual physical root")
    count = total = 0
    known = True
    stack = [(root, "")]
    while stack:
        _check(cancel)
        node, relative = stack.pop()
        if node.is_dir:
            give_way()
        signature = None
        if node.snapshot is not None:
            info = unpack_snapshot(node.snapshot)
            if info.inode:
                signature = stable_snapshot(node.snapshot).hex()
        known = known and signature is not None
        total = (total + int(_digest((relative, signature, node.size, node.allocated, node.error)), 16)) % (1 << 256)
        count += 1
        stack.extend((child, f"{relative}/{child.name}" if relative else child.name) for child in node.children)
    return _digest((_path_key(root.path), count, total)) if known else None


def _candidates(root: Node, policy: CleanupPolicy, now: float, cancel) -> tuple[tuple[Candidate, ...], int]:
    groups = find_cleanup(root, policy=policy, now=now, cancel=cancel)
    if groups is None:
        raise ProposalCancelledError
    heap, count = [], 0
    for group in groups:
        for node in group.nodes:
            _check(cancel)
            count += 1
            if node.path is None or len(node.path) > _MAX_PATH or any(char in node.path for char in ("\0", "\n", "\r")):
                continue  # Still counted: omitted candidate paths cannot turn absence into evidence.
            signature = hashlib.sha256(stable_snapshot(node.snapshot)).hexdigest() if node.snapshot else None
            row = Candidate(node.path, group.key, node.size, signature)
            heapq.heappush(heap, (row.size, row.path, row))
            if len(heap) > MAX_ROWS:
                heapq.heappop(heap)
    return tuple(item[2] for item in sorted(heap, reverse=True)), count


def capture(root: Node, policy: CleanupPolicy, now: float, *, cancel: threading.Event | None = None) -> Baseline:
    """Capture bounded review observations on a worker; no virtual root or source operation is accepted."""
    if root.path is None or not root.is_dir or root.is_link:
        raise ValueError("Recurring observations require an ordinary individual physical root")
    version = policy_version(policy)
    ScanAttempt(root.path, now, version)
    coverage = coverage_of(root, cancel=cancel)
    _check(cancel)
    candidates, count = _candidates(root, policy, now, cancel)
    info = unpack_snapshot(root.snapshot) if root.snapshot else None
    identity = info.identity if info is not None and info.inode else None
    result = Baseline(root.path, now, version, tree_signature(root, cancel=cancel), identity,
                      (coverage.known_folders, coverage.skipped_folders, coverage.inaccessible_folders,
                       coverage.pending_folders, len(coverage.unsafe)), candidates, count, root.size)
    while len(dump_baseline(result)) > MAX_BYTES:
        result = replace(result, candidates=result.candidates[:-1])
    return result


def _comparison(previous: Baseline | None, current: Baseline, saved: SavedScan | None) -> bool:
    return (previous is not None and previous.inventory_complete and current.inventory_complete
            and previous.signature is not None and current.signature is not None
            and previous.identity == current.identity and current.identity is not None
            and previous.policy == current.policy and previous.created_at <= current.created_at
            and _path_key(previous.root) == _path_key(current.root)
            and saved is not None and saved.root == previous.root and bool(previous.saved)
            and saved.saved == previous.saved)


def _growth(root: Node, saved: SavedScan, cancel) -> tuple[Growth, ...]:
    heap, ordinal = [], 0
    stack = [(root, "")]
    while stack:
        _check(cancel)
        give_way()
        folder, relative = stack.pop()
        before = saved.folders.get(folder_key(relative))
        row = Growth(folder.path, before.size if before else None, folder.size)
        if row.change > 0:
            heapq.heappush(heap, (row.change, ordinal, row))
            if len(heap) > MAX_ROWS:
                heapq.heappop(heap)
        ordinal += 1
        stack.extend((child, f"{relative}/{child.name}" if relative else child.name)
                     for child in folder.children if child.is_dir and not child.is_link)
    return tuple(item[2] for item in sorted(heap, reverse=True))


def prepare(root: Node, policy: CleanupPolicy, context: ProposalContext, *, previous: Baseline | None = None,
            saved: SavedScan | None = None, cancel: threading.Event | None = None) -> RecurringProposal:
    """Combine a current scan, policy and explicitly bound history; unknown baselines stay unknown."""
    if root.path is None or _path_key(root.path) != context.attempt.key:
        raise ValueError("Recurring schedule root does not match the current scan")
    baseline = capture(root, policy, context.prepared_at, cancel=cancel)
    comparable = _comparison(previous, baseline, saved)
    old = {(_path_key(row.path), row.rule) for row in previous.candidates} if comparable else set()
    fresh = (tuple(row for row in baseline.candidates if (_path_key(row.path), row.rule) not in old)
             if comparable else ())
    growth = _growth(root, saved, cancel) if comparable else ()
    return RecurringProposal(baseline, context, fresh, growth, comparable, previous.saved if comparable else "")


def proposal_status(proposal: RecurringProposal, root: Node, policy: CleanupPolicy, config: MonitorConfig,
                    attempt: ScanAttempt | None, now: float, *, cancel: threading.Event | None = None) -> str | None:
    """Return an expiry reason or None for current observations; even None grants no operation authority."""
    baseline, context = proposal.baseline, proposal.context
    ScanAttempt(baseline.root, now, baseline.policy)
    if now < context.prepared_at or now >= context.expires_at:
        return "expired"
    if (not config.enabled or config.schedule_id != context.attempt.schedule_id
            or config.interval_hours != context.interval_hours
            or _path_key(baseline.root) not in {_path_key(path) for path in config.roots}):
        return "schedule_changed"
    if (attempt != replace(context.attempt, state="complete") or baseline.created_at != context.prepared_at
            or _path_key(baseline.root) != context.attempt.key):
        return "stale_scan"
    if policy_version(policy) != baseline.policy:
        return "rule_changed"
    if not baseline.complete or baseline.signature is None:
        return "incomplete"
    if root.path != baseline.root or tree_signature(root, cancel=cancel) != baseline.signature:
        status = "paths_changed"
    else:
        status = None
    return status


def dump_baseline(baseline: Baseline) -> str:
    """Serialize scalar observations only; callers must cap the payload before persisting it."""
    return json.dumps({"version": 1, **asdict(baseline)}, ensure_ascii=True, separators=(",", ":"))


def load_baseline(text: str) -> Baseline:
    """Strict bounded metadata load; action/approval fields, duplicates and malformed rows are refused."""
    if not isinstance(text, str) or len(text) > MAX_BYTES:
        raise ValueError("Recurring baseline exceeds its size limit")
    try:
        value = json.loads(text, object_pairs_hook=_unique)
        fields = {"version", "root", "created_at", "policy", "signature", "identity", "coverage", "candidates",
                  "candidate_count", "size", "saved"}
        if (not isinstance(value, dict) or set(value) != fields or type(value["version"]) is not int
                or value["version"] != 1):
            raise ValueError("Invalid recurring baseline fields")
        if not isinstance(value["coverage"], list) or not isinstance(value["candidates"], list):
            raise ValueError("Invalid recurring baseline rows")
        if value["identity"] is not None and not isinstance(value["identity"], list):
            raise ValueError("Invalid recurring root identity")
        rows = []
        for row in value["candidates"]:
            if not isinstance(row, dict) or set(row) != {"path", "rule", "size", "signature"}:
                raise ValueError("Invalid recurring candidate fields")
            rows.append(Candidate(**row))
        identity = tuple(value["identity"]) if value["identity"] is not None else None
        return Baseline(value["root"], value["created_at"], value["policy"], value["signature"], identity,
                        tuple(value["coverage"]), tuple(rows), value["candidate_count"], value["size"], value["saved"])
    except (RecursionError, UnicodeError, TypeError, OverflowError) as error:
        raise ValueError("Invalid recurring baseline encoding/nesting") from error


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate recurring baseline fields")
    return result
