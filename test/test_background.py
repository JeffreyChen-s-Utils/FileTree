"""Background metadata defaults, missed-period coalescing and truthful capacity warning transitions."""

from dataclasses import replace
import json
import os

import pytest

from je_file_tree.core.background import (
    CapacityObservation, MAX_CONFIG_BYTES, MAX_ROOTS, MAX_VOLUMES, MonitorConfig,
    ScanAttempt, SpaceWarnings, claim_scan, due_roots, dump_attempts, load_attempts, load_config,
)


def test_default_off_config_round_trip_and_explicit_literal_roots(tmp_path):
    root = str(tmp_path / "中文資料夾")
    config = MonitorConfig(roots=(root,))
    assert load_config(config.dumps()) == config
    assert not due_roots(config, {}, 1000)
    with pytest.raises(ValueError, match="explicitly enabled"):
        claim_scan(config, root, 1000)
    enabled = replace(config, enabled=True)
    assert due_roots(enabled, {}, 1000) == (root,)
    with pytest.raises(ValueError, match="explicitly enabled"):
        claim_scan(enabled, str(tmp_path / "foreign"), 1000)


@pytest.mark.parametrize("field,value", [("enabled", "true"), ("threshold", True), ("threshold", 0),
                                         ("threshold", 51), ("interval_hours", 0), ("interval_hours", 721),
                                         ("roots", []), ("roots", ("relative",)), ("roots", ("",))])
def test_invalid_configuration_never_implies_opt_in(field, value):
    with pytest.raises(ValueError):
        MonitorConfig(**{field: value})


def test_unknown_duplicate_oversized_or_malformed_json_fails_closed(tmp_path):
    config = MonitorConfig(roots=(str(tmp_path),))
    value = json.loads(config.dumps())
    value["remove_files"] = True
    with pytest.raises(ValueError):
        load_config(json.dumps(value))
    duplicate = config.dumps().replace('"enabled":false', '"enabled":false,"enabled":true')
    for text in (duplicate, "[" * 5000, "\ud800", " " * (MAX_CONFIG_BYTES + 1), "false"):
        with pytest.raises(ValueError):
            load_config(text)
    with pytest.raises(ValueError, match="Duplicate"):
        MonitorConfig(roots=(str(tmp_path), str(tmp_path / "child" / "..")))
    with pytest.raises(ValueError):
        MonitorConfig(roots=tuple(str(tmp_path / str(number)) for number in range(MAX_ROOTS + 1)))


@pytest.mark.parametrize("state", ["claimed", "complete", "failed", "canceled"])
def test_attempts_claim_before_dispatch_and_missed_periods_never_replay_backlog(tmp_path, state):
    root = str(tmp_path)
    config = MonitorConfig(True, interval_hours=1, roots=(root,))
    receipt = replace(claim_scan(config, root, 1000), state=state)
    attempts = {os.path.normcase(root): receipt}
    assert not due_roots(config, attempts, 4599)
    assert due_roots(config, attempts, 4600) == (root,)
    assert due_roots(config, attempts, 1000000) == (root,)
    assert not due_roots(config, attempts, 999)
    new = replace(config, interval_hours=2)
    assert new.schedule_id != config.schedule_id and due_roots(new, attempts, 1001) == (root,)
    assert replace(config, threshold=20).schedule_id == config.schedule_id


def test_corrupt_receipts_and_clock_values_cannot_dispatch(tmp_path):
    root = str(tmp_path)
    config = MonitorConfig(True, roots=(root,))
    for now in (True, -1, float("nan"), float("inf"), "now", 10 ** 4000):
        with pytest.raises(ValueError):
            due_roots(config, {}, now)
    for state in ("remove", {}, False):
        with pytest.raises(ValueError):
            ScanAttempt(root, 1000, config.schedule_id, state)
    foreign = claim_scan(MonitorConfig(True, roots=(str(tmp_path / "foreign"),)), str(tmp_path / "foreign"), 1000)
    with pytest.raises(ValueError, match="does not match"):
        due_roots(config, {os.path.normcase(root): foreign}, 1001)


def test_capacity_warning_only_on_below_threshold_crossing_and_unknown_never_means_zero(tmp_path):
    root = str(tmp_path)
    state = SpaceWarnings()
    normal = CapacityObservation(root, 1000, 100)
    low = replace(normal, available=99)
    unknown = replace(normal, available=None)
    assert not state.observe((normal, unknown)[:1])
    assert state.observe((low,)) == (low,)
    assert not state.observe((low,)) and not state.observe((unknown,))
    assert not state.observe((low,))
    assert not state.observe((normal,))
    assert state.observe((low,)) == (low,)
    state.observe(())
    assert not state.low and state.observe((low,)) == (low,)


def test_invalid_capacity_batch_does_not_consume_warning_latch(tmp_path):
    root = str(tmp_path)
    state = SpaceWarnings()
    low = CapacityObservation(root, 1000, 50)
    for rows in ((low, low), (low, "invalid"), (low,) * (MAX_VOLUMES + 1)):
        with pytest.raises(ValueError):
            state.observe(rows)
        assert not state.low
    assert state.observe((low,)) == (low,)
    for amount in (-1, 1001, True):
        with pytest.raises(ValueError):
            CapacityObservation(root, 1000, amount)


def test_attempt_serialization_rejects_duplicate_or_unknown_authority_fields(tmp_path):
    config = MonitorConfig(True, roots=(str(tmp_path),))
    attempt = claim_scan(config, str(tmp_path), 1000)
    assert load_attempts(dump_attempts({attempt.key: attempt})) == {attempt.key: attempt}
    value = json.loads(dump_attempts({attempt.key: attempt}))
    value["attempts"].append(value["attempts"][0].copy())
    with pytest.raises(ValueError, match="Duplicate"):
        load_attempts(json.dumps(value))
    value["attempts"] = value["attempts"][:1]
    value["attempts"][0]["approved_removal"] = True
    with pytest.raises(ValueError, match="fields"):
        load_attempts(json.dumps(value))
    with pytest.raises(ValueError, match="does not match"):
        dump_attempts({"foreign": attempt})
    with pytest.raises(ValueError):
        load_attempts('{"version":1,"version":1,"attempts":[]}')
