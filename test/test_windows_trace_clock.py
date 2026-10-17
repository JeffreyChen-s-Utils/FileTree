"""Timing metadata cannot invent process identity or alter native helper outcomes."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import subprocess
from types import SimpleNamespace

import pytest

from tools import windows_child_observer as native
from tools import windows_share_probe as probe
from tools.windows_trace_clock import trace_clock

_PREFIX = "FILETREE_SMB_CLOCK "
_ORIGIN = {"pid": 123, "before_filetime_100ns": 1001000, "after_filetime_100ns": 1001100}
_OBSERVATION = {"status": "observed", "child_pid": 123,
                "records": [{"event": "identity", "pid": 123, "cpu": {"created_100ns": 1000000}}]}


def _line(value):
    return _PREFIX + json.dumps(value)


def test_same_owned_pid_creation_and_clock_bracket_are_retained_as_integer_offsets():
    result = trace_clock(_line(_ORIGIN), _PREFIX, _OBSERVATION)
    assert result["status"] == "aligned-origin"
    assert result["origin"] == _ORIGIN and result["process_created_filetime_100ns"] == 1000000
    assert result["creation_to_origin_100ns"] == [1000, 1100]
    assert result["assumption"] == "stable host UTC"


@pytest.mark.parametrize("payload", ["broken", "[]", "{}", '[' * 1500,
                                    json.dumps({**_ORIGIN, "pid": True}),
                                    json.dumps({**_ORIGIN, "before_filetime_100ns": -1}),
                                    json.dumps({**_ORIGIN, "after_filetime_100ns": 100}),
                                    json.dumps({**_ORIGIN, "after_filetime_100ns": 1 << 64}),
                                    json.dumps({**_ORIGIN, "unexpected": 1})])
def test_malformed_clock_has_no_alignment(payload):
    result = trace_clock(_PREFIX + payload, _PREFIX, _OBSERVATION)
    assert result["status"] == "invalid" and "creation_to_origin_100ns" not in result


def test_missing_and_duplicate_origins_never_select_a_convenient_clock():
    assert trace_clock("no origin", _PREFIX, _OBSERVATION) == {"status": "missing"}
    result = trace_clock(_line(_ORIGIN) + "\n" + _line(_ORIGIN), _PREFIX, _OBSERVATION)
    assert result == {"status": "ambiguous", "record_count": 2}


@pytest.mark.parametrize("variant", ["missing", "different-child", "different-identity", "bad-created",
                                     "two-identities", "bad-records", "not-a-record", "boolean-pid",
                                     "boolean-identity"])
def test_unavailable_or_inconsistent_process_identity_keeps_origin_only(variant):
    observation = deepcopy(_OBSERVATION)
    origin = dict(_ORIGIN)
    if variant == "missing":
        observation["status"] = "not-sampled"
    elif variant == "different-child":
        observation["child_pid"] += 1
    elif variant == "different-identity":
        observation["records"][0]["pid"] += 1
    elif variant == "bad-created":
        observation["records"][0]["cpu"]["created_100ns"] = True
    elif variant == "two-identities":
        observation["records"] *= 2
    elif variant == "bad-records":
        observation["records"] = None
    elif variant == "boolean-pid":
        origin["pid"] = observation["records"][0]["pid"] = 1
        observation["child_pid"] = True
    elif variant == "boolean-identity":
        origin["pid"] = observation["child_pid"] = 1
        observation["records"][0]["pid"] = True
    else:
        observation = None
    result = trace_clock(_line(origin), _PREFIX, observation)
    assert result["status"] == "origin-only" and result["origin"] == origin
    assert "creation_to_origin_100ns" not in result


def test_origin_before_creation_is_unknown_rather_than_negative_startup_duration():
    observation = deepcopy(_OBSERVATION)
    observation["records"][0]["cpu"]["created_100ns"] = 1002000
    result = trace_clock(_line(_ORIGIN), _PREFIX, observation)
    assert result["status"] == "inconsistent" and "creation_to_origin_100ns" not in result


@pytest.mark.parametrize("timeout", [False, True])
def test_bad_clock_does_not_mask_the_actual_exit_timeout_or_existing_step_completion(timeout):
    step = 'FILETREE_SMB_STEP {"sequence":1,"step":"helper-complete","event":"completed","elapsed_ms":1}\n'
    stderr = (step + _PREFIX + "{bad").encode()
    result = (subprocess.TimeoutExpired(["owned"], 20, stderr=stderr) if timeout else
              subprocess.CompletedProcess(["owned"], 0, b"", stderr))
    record = probe._helper_record(result, 0)
    assert record["outcome"] == ("timeout" if timeout else "completed")
    assert record["returncode"] == (None if timeout else 0)
    assert record["trace_complete"] and record["clock"]["status"] == "invalid"


def test_filetime_epoch_and_emission_use_integer_utc_without_mutating_input(monkeypatch, capsys):
    epoch_days = (datetime(1970, 1, 1) - datetime(1601, 1, 1)).days
    assert epoch_days * 86400 * 10000000 == native._UNIX_EPOCH_FILETIME
    monkeypatch.setattr(native.time, "time_ns", lambda: 123456789)
    expected = native._UNIX_EPOCH_FILETIME + 1234567
    assert native._filetime() == expected
    record = {"event": "owned"}
    native._emit(record)
    assert record == {"event": "owned"}
    assert json.loads(capsys.readouterr().out) == {**record, "emitted_filetime_100ns": expected}


def test_wait_query_has_utc_bracket_without_changing_wct_flags_or_node_limits(monkeypatch):
    ticks = iter([1000, 1100])
    calls = []
    monkeypatch.setattr(native, "_filetime", lambda: next(ticks))

    def wait(session, context, flags, tid, count, nodes, cycle):
        calls.append((session, context, flags, tid, count._obj.value, len(nodes)))
        count._obj.value = 0
        cycle._obj.value = False
        return True

    result = native._wait(SimpleNamespace(wait=wait), 5, 9)
    assert calls == [(5, 0, 0, 9, 16, 16)]
    assert result["complete"] and not result["nodes"] and not result["cycle"]
    assert result["query_before_filetime_100ns"] == 1000 and result["query_after_filetime_100ns"] == 1100
