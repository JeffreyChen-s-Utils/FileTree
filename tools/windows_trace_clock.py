"""Correlate diagnostic stopwatch origins with an already observed owned child."""

from __future__ import annotations

import json

_MAX_TIME = (1 << 63) - 1
_MAX_PID = (1 << 31) - 1
_CLOCK_KEYS = {"pid", "before_filetime_100ns", "after_filetime_100ns"}


def _origin(stderr: str, prefix: str) -> dict:
    lines = [line.rpartition(prefix)[2] for line in stderr.splitlines() if prefix in line]
    if not lines:
        return {"status": "missing"}
    if len(lines) != 1:
        return {"status": "ambiguous", "record_count": len(lines)}
    try:
        origin = json.loads(lines[0])
    except (ValueError, RecursionError):
        return {"status": "invalid", "reason": "invalid-json"}
    if (not isinstance(origin, dict) or set(origin) != _CLOCK_KEYS
            or any(type(value) is not int for value in origin.values())
            or not 0 < origin["pid"] <= _MAX_PID
            or not 0 < origin["before_filetime_100ns"] <= origin["after_filetime_100ns"] <= _MAX_TIME):
        return {"status": "invalid", "reason": "invalid-origin"}
    return {"status": "origin-only", "origin": origin, "assumption": "stable host UTC"}


def trace_clock(stderr: str, prefix: str, observation: object) -> dict:
    """Keep missing/invalid clock data diagnostic-only; never change an operation outcome.

    Origins bracket Stopwatch.StartNew in the child's UTC clock. Creation offsets assume a
    stable host UTC clock; they are not monotonic durations or proof of a blocking operation.
    """
    record = _origin(stderr, prefix)
    if record["status"] != "origin-only":
        return record
    origin = record["origin"]
    if not isinstance(observation, dict):
        return record
    entries = observation.get("records", [])
    if not isinstance(entries, list):
        return record
    identities = [item for item in entries if isinstance(item, dict) and item.get("event") == "identity"]
    if observation.get("status") != "observed" or len(identities) != 1:
        return record
    identity = identities[0]
    cpu = identity.get("cpu")
    created = cpu.get("created_100ns") if isinstance(cpu, dict) else None
    if (type(observation.get("child_pid")) is not int or type(identity.get("pid")) is not int
            or observation["child_pid"] != origin["pid"] or identity["pid"] != origin["pid"]
            or type(created) is not int or not 0 < created <= _MAX_TIME):
        record["reason"] = "process-identity-unavailable-or-different"
        return record
    record["process_created_filetime_100ns"] = created
    if origin["before_filetime_100ns"] < created:
        record.update(status="inconsistent", reason="origin-before-process-creation")
    else:
        record.update(status="aligned-origin", creation_to_origin_100ns=[
            origin["before_filetime_100ns"] - created, origin["after_filetime_100ns"] - created])
    return record
