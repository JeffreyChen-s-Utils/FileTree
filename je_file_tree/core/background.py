"""Bounded opt-in background schedules and capacity warnings, without source operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
import re

MAX_ROOTS = 32
MAX_VOLUMES = 256
MAX_CONFIG_BYTES = 65536
MAX_ATTEMPT_BYTES = 131072
_MAX_ROOT_LENGTH = 1024
_MAX_HOURS = 720
_MAX_THRESHOLD = 50
_MAX_EPOCH = 253402300799  # 9999-12-31 23:59:59 UTC; never overflow a displayed timestamp.
_SECONDS_PER_HOUR = 3600
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
_ATTEMPT_STATES = frozenset({"claimed", "complete", "failed", "canceled"})


def _root(path: str) -> str:
    if (not isinstance(path, str) or not path or len(path) > _MAX_ROOT_LENGTH
            or any(character in path for character in ("\0", "\r", "\n")) or not os.path.isabs(path)):
        raise ValueError("Background roots must be bounded literal absolute paths")
    return os.path.normcase(os.path.normpath(path))


def _epoch(value: float) -> None:
    if (isinstance(value, bool) or not isinstance(value, (float, int)) or value < 0
            or value > _MAX_EPOCH or not math.isfinite(value)):
        raise ValueError("Invalid background schedule timestamp")


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate background configuration keys")
    return result


@dataclass(frozen=True, slots=True)
class MonitorConfig:
    """Default-off monitoring; scheduled scans use only explicitly chosen roots, never clean up."""

    enabled: bool = False
    threshold: int = 10
    interval_hours: int = 24
    roots: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (type(self.enabled) is not bool or type(self.threshold) is not int
                or not 1 <= self.threshold <= _MAX_THRESHOLD or type(self.interval_hours) is not int
                or not 1 <= self.interval_hours <= _MAX_HOURS):
            raise ValueError("Invalid background monitoring options")
        if not isinstance(self.roots, tuple) or len(self.roots) > MAX_ROOTS:
            raise ValueError("Background monitoring supports at most 32 selected roots")
        normalized = [_root(path) for path in self.roots]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Duplicate background scan roots")
        if len(json.dumps(self.roots, ensure_ascii=True)) > MAX_CONFIG_BYTES - 1024:
            raise ValueError("Oversized background root configuration")

    def dumps(self) -> str:
        """Bounded versioned metadata; no executable commands or action permissions are stored."""
        value = {"version": 1, "enabled": self.enabled, "threshold": self.threshold,
                 "interval_hours": self.interval_hours, "roots": self.roots}
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))

    @property
    def schedule_id(self) -> str:
        """Fingerprint the explicit schedule; changing it invalidates old recurring proposals."""
        value = {"version": 1, "interval_hours": self.interval_hours, "roots": [_root(path) for path in self.roots]}
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def load_config(text: str) -> MonitorConfig:
    """Strictly read opt-in metadata; unknown fields, duplicate keys and excessive nesting fail closed."""
    if not isinstance(text, str):
        raise ValueError("Oversized background configuration")
    try:
        if len(text.encode("utf-8")) > MAX_CONFIG_BYTES:
            raise ValueError("Oversized background configuration")
        value = json.loads(text, object_pairs_hook=_unique)
    except (RecursionError, UnicodeError) as error:
        raise ValueError("Invalid background configuration encoding/nesting") from error
    fields = {"version", "enabled", "threshold", "interval_hours", "roots"}
    if (not isinstance(value, dict) or set(value) != fields or type(value["version"]) is not int
            or value["version"] != 1 or not isinstance(value["roots"], list)):
        raise ValueError("Invalid background configuration document")
    return MonitorConfig(value["enabled"], value["threshold"], value["interval_hours"], tuple(value["roots"]))


@dataclass(frozen=True, slots=True)
class ScanAttempt:
    """Claim before scanning, including failed/canceled attempts; no missed-period backlog is replayed."""

    root: str
    claimed_at: float
    schedule_id: str
    state: str = "claimed"

    def __post_init__(self) -> None:
        _root(self.root)
        _epoch(self.claimed_at)
        if (not isinstance(self.schedule_id, str) or not _FINGERPRINT.fullmatch(self.schedule_id)
                or not isinstance(self.state, str) or self.state not in _ATTEMPT_STATES):
            raise ValueError("Invalid background attempt receipt")

    @property
    def key(self) -> str:
        """Canonical metadata map key; normalization grants no filesystem identity or authority."""
        return _root(self.root)


def dump_attempts(attempts: Mapping[str, ScanAttempt]) -> str:
    """Serialize at most 32 validated claims; metadata never contains filesystem action permissions."""
    if len(attempts) > MAX_ROOTS:
        raise ValueError("Too many background attempt receipts")
    rows = []
    for key, attempt in sorted(attempts.items()):
        if not isinstance(attempt, ScanAttempt) or key != attempt.key:
            raise ValueError("Background receipt does not match its selected root")
        rows.append({"root": attempt.root, "claimed_at": attempt.claimed_at,
                     "schedule_id": attempt.schedule_id, "state": attempt.state})
    text = json.dumps({"version": 1, "attempts": rows}, ensure_ascii=True, separators=(",", ":"))
    if len(text) > MAX_ATTEMPT_BYTES:
        raise ValueError("Oversized background attempt receipts")
    return text


def load_attempts(text: str) -> dict[str, ScanAttempt]:
    """Strictly load bounded scalar receipts; malformed state fails closed rather than becoming due."""
    if not isinstance(text, str) or len(text) > MAX_ATTEMPT_BYTES:
        raise ValueError("Oversized background attempt receipts")
    try:
        value = json.loads(text, object_pairs_hook=_unique)
    except RecursionError as error:
        raise ValueError("Invalid background attempt nesting") from error
    if (not isinstance(value, dict) or set(value) != {"version", "attempts"}
            or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["attempts"], list) or len(value["attempts"]) > MAX_ROOTS):
        raise ValueError("Invalid background attempt document")
    result = {}
    for row in value["attempts"]:
        if not isinstance(row, dict) or set(row) != {"root", "claimed_at", "schedule_id", "state"}:
            raise ValueError("Invalid background attempt fields")
        attempt = ScanAttempt(row["root"], row["claimed_at"], row["schedule_id"], row["state"])
        if attempt.key in result:
            raise ValueError("Duplicate background attempt roots")
        result[attempt.key] = attempt
    return result


def due_roots(config: MonitorConfig, attempts: Mapping[str, ScanAttempt], now: float) -> tuple[str, ...]:
    """Return each due selected root once; disabled/future-clock/same-period claims cannot run again."""
    _epoch(now)
    if not config.enabled:
        return ()
    result = []
    for path in config.roots:
        key = _root(path)
        attempt = attempts.get(key)
        if attempt is not None:
            if not isinstance(attempt, ScanAttempt) or _root(attempt.root) != key:
                raise ValueError("Background receipt does not match its selected root")
            if now < attempt.claimed_at:
                continue
            if (attempt.schedule_id == config.schedule_id
                    and now - attempt.claimed_at < config.interval_hours * _SECONDS_PER_HOUR):
                continue
        result.append(path)
    return tuple(result)


def claim_scan(config: MonitorConfig, root: str, now: float) -> ScanAttempt:
    """Prepare a scalar claim for one selected root; callers must persist/serialize before dispatch."""
    if not config.enabled or _root(root) not in {_root(path) for path in config.roots}:
        raise ValueError("Scheduled scan root was not explicitly enabled")
    return ScanAttempt(root, now, config.schedule_id)


@dataclass(frozen=True, slots=True)
class CapacityObservation:
    """Copied OS available capacity; unknown values cannot be converted into low-space warnings."""

    root: str
    total: int
    available: int | None

    def __post_init__(self) -> None:
        _root(self.root)
        if (type(self.total) is not int or self.total <= 0 or self.available is not None
                and (type(self.available) is not int or not 0 <= self.available <= self.total)):
            raise ValueError("Invalid observed OS capacity")


class SpaceWarnings:
    """Warn once per low-space crossing; unknown observations do not falsely reset the latch."""

    def __init__(self) -> None:
        self.low: set[str] = set()

    def observe(self, rows: Sequence[CapacityObservation], threshold: int = 10) -> tuple[CapacityObservation, ...]:
        """Bound mounted observations; warnings are informational and never source-operation proposals."""
        if type(threshold) is not int or not 1 <= threshold <= _MAX_THRESHOLD or len(rows) > MAX_VOLUMES:
            raise ValueError("Invalid background warning scope")
        warnings, seen, low = [], set(), self.low.copy()
        for row in rows:
            if not isinstance(row, CapacityObservation):
                raise ValueError("Invalid background capacity observation")
            key = _root(row.root)
            if key in seen:
                raise ValueError("Duplicate background capacity scopes")
            seen.add(key)
            if row.available is None:
                continue
            if row.available * 100 < row.total * threshold:
                if key not in low:
                    warnings.append(row)
                low.add(key)
            else:
                low.discard(key)
        self.low = low & seen
        return tuple(warnings)
