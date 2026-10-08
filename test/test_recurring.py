"""Recurring observations stay bounded, source-preserving and unable to renew stale action proposals."""

from dataclasses import replace
import hashlib
import json
import os
import threading
import time

import pytest

from je_file_tree.core import recurring
from je_file_tree.core.background import MonitorConfig, claim_scan
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting
from je_file_tree.core.history import ScanHistory, load_history, load_recurring
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ACCESS_DENIED, ScanOptions, scan


@pytest.fixture
def observations(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "old.dmp").write_bytes(b"owned old payload")
    policy = CleanupPolicy((RuleSetting("crash_dumps", True, 0),))
    store = ScanHistory(tmp_path / "history")
    root = scan(source).root
    previous = recurring.capture(root, policy, time.time())
    entry = store.save(root, baseline=previous)
    return source, policy, store, load_recurring(entry), load_history(entry)


def _proposal(source, policy, previous=None, saved=None):
    root = scan(source).root
    now = time.time()
    config = MonitorConfig(True, interval_hours=1, roots=(str(source),))
    attempt = claim_scan(config, str(source), now - 1)
    context = recurring.ProposalContext(attempt, config.interval_hours, now)
    proposal = recurring.prepare(root, policy, context, previous=previous, saved=saved)
    return root, config, replace(attempt, state="complete"), proposal


def test_new_junk_and_growth_are_bound_to_complete_history_and_preserve_payloads(observations):
    source, policy, _store, previous, saved = observations
    (source / "new.dmp").write_bytes(b"owned new payload" * 10)
    (source / "old.dmp").write_bytes(b"old larger payload" * 20)
    proof = {path.name: (path.stat().st_ino, hashlib.sha256(path.read_bytes()).hexdigest())
             for path in source.iterdir()}
    root, config, attempt, proposal = _proposal(source, policy, previous, saved)
    assert proposal.comparison_complete and proposal.previous_saved == saved.saved
    assert [row.path for row in proposal.new_junk] == [str(source / "new.dmp")]
    assert proposal.growth[0].path == str(source) and proposal.growth[0].change == root.size - saved.size
    assert recurring.proposal_status(proposal, root, policy, config, attempt, proposal.context.prepared_at) is None
    assert proof == {path.name: (path.stat().st_ino, hashlib.sha256(path.read_bytes()).hexdigest())
                     for path in source.iterdir()}


def test_missed_schedule_changed_rule_or_new_receipt_cannot_renew_old_proposal(observations):
    source, policy, _store, previous, saved = observations
    root, config, attempt, proposal = _proposal(source, policy, previous, saved)
    now = proposal.context.prepared_at
    assert recurring.proposal_status(proposal, root, policy, config, attempt, proposal.context.expires_at) == "expired"
    assert recurring.proposal_status(proposal, root, policy, config, attempt, now - 1) == "expired"
    changed = CleanupPolicy((RuleSetting("crash_dumps", False, 0),))
    assert recurring.proposal_status(proposal, root, changed, config, attempt, now) == "rule_changed"
    for changed_config in (replace(config, enabled=False), replace(config, interval_hours=2)):
        assert recurring.proposal_status(proposal, root, policy, changed_config, attempt, now) == "schedule_changed"
    for current in (None, replace(attempt, state="failed"), replace(attempt, state="canceled"),
                    replace(attempt, claimed_at=now + 1)):
        assert recurring.proposal_status(proposal, root, policy, config, current, now) == "stale_scan"


def test_descendant_change_rename_or_arrival_expires_the_whole_proposal(observations):
    source, policy, _store, previous, saved = observations
    nested = source / "nested"
    nested.mkdir()
    target = nested / "kept.bin"
    target.write_bytes(b"kept")
    _root, config, attempt, proposal = _proposal(source, policy, previous, saved)
    target.write_bytes(b"different same-size metadata")
    current = scan(source).root
    assert recurring.proposal_status(proposal, current, policy, config, attempt,
                                     proposal.context.prepared_at + 1) == "paths_changed"
    target.rename(nested / "renamed.bin")
    current = scan(source).root
    assert recurring.proposal_status(proposal, current, policy, config, attempt,
                                     proposal.context.prepared_at + 1) == "paths_changed"


def test_legacy_missing_mismatched_and_partial_baselines_remain_unknown(observations):
    source, policy, _store, previous, saved = observations
    assert not _proposal(source, policy)[3].comparison_complete
    wrong = replace(saved, saved="2000-01-01T00:00:00+00:00")
    assert not _proposal(source, policy, previous, wrong)[3].comparison_complete
    assert not _proposal(source, policy, replace(previous, policy="0" * 64), saved)[3].comparison_complete
    replaced_root = replace(previous, identity=(previous.identity[0], previous.identity[1] + 1))
    assert not _proposal(source, policy, replaced_root, saved)[3].comparison_complete
    partial = replace(previous, candidate_count=previous.candidate_count + 1)
    report = _proposal(source, policy, partial, saved)[3]
    assert not report.comparison_complete and not report.new_junk and not report.growth


def test_directory_and_file_errors_and_missing_identity_never_become_actionable(observations):
    source, policy, store, _previous, _saved = observations
    root, config, attempt, proposal = _proposal(source, policy)
    root.children[0].error = ACCESS_DENIED
    partial = recurring.prepare(root, policy, proposal.context)
    assert not partial.baseline.complete and partial.baseline.coverage[-1] > 0
    entry = store.save(root, baseline=partial.baseline)
    assert entry.incomplete and not load_recurring(entry).complete
    assert recurring.proposal_status(partial, root, policy, config, attempt,
                                     partial.context.prepared_at) == "incomplete"
    root.children[0].error = None
    root.children[0].snapshot = None
    unknown = recurring.prepare(root, policy, proposal.context)
    assert unknown.baseline.complete and unknown.baseline.signature is None
    assert recurring.proposal_status(unknown, root, policy, config, attempt,
                                     unknown.context.prepared_at) == "incomplete"
    nested = source / "excluded"
    nested.mkdir()
    current = scan(source, options=ScanOptions(exclude=("excluded",))).root
    report = recurring.prepare(current, policy, proposal.context)
    assert not report.baseline.complete and report.baseline.coverage[1] == 1


def test_observation_and_digest_read_only_captured_nodes_and_ignore_child_order(observations, monkeypatch):
    source, policy, _store, previous, saved = observations
    (source / "second.bin").write_bytes(b"captured")
    root, _config, _attempt, proposal = _proposal(source, policy, previous, saved)
    signature = recurring.tree_signature(root)
    root.children.reverse()
    assert recurring.tree_signature(root) == signature
    with monkeypatch.context() as no_reads:
        no_reads.setattr("builtins.open", lambda *_a, **_kw: pytest.fail("Payload/filesystem read"))
        no_reads.setattr(recurring.os, "stat", lambda *_a, **_kw: pytest.fail("Filesystem stat"))
        no_reads.setattr(recurring.os, "lstat", lambda *_a, **_kw: pytest.fail("Filesystem lstat"))
        assert recurring.prepare(root, policy, proposal.context).baseline.signature == signature


def test_candidate_rows_are_bounded_and_omitted_inventory_never_proves_new(observations):
    source, policy, _store, _previous, _saved = observations
    for index in range(130):
        (source / f"dump-{index}.dmp").write_bytes(b"owned" * (index + 1))
    baseline = recurring.capture(scan(source).root, policy, time.time())
    assert baseline.candidate_count == 131 and len(baseline.candidates) == recurring.MAX_ROWS
    assert not baseline.inventory_complete and len(recurring.dump_baseline(baseline)) <= recurring.MAX_BYTES
    assert recurring.load_baseline(recurring.dump_baseline(baseline)) == baseline


def test_history_summary_is_bound_to_owned_header_and_old_history_still_loads(observations):
    source, _policy, store, previous, saved = observations
    assert previous.saved == saved.saved
    entry = store.save(scan(source).root)
    assert load_recurring(entry) is None and load_history(entry).root == str(source)
    with pytest.raises(ValueError, match="match"):
        store.save(scan(source).root, baseline=replace(previous, size=previous.size + 1))


def test_long_cjk_metadata_is_shrunk_before_history_publication(observations):
    source, policy, store, _previous, _saved = observations
    root = scan(source).root
    template = root.children[0]
    root.children = [Node("字" * 500 + f"-{index}.dmp", False, size=template.size, modified=template.modified,
                          snapshot=template.snapshot, parent=root) for index in range(100)]
    root.size = template.size * len(root.children)
    baseline = recurring.capture(root, policy, time.time())
    assert baseline.candidate_count == 100 and len(baseline.candidates) < 100
    assert len(recurring.dump_baseline(baseline)) <= recurring.MAX_BYTES and not baseline.inventory_complete
    entry = store.save(root, baseline=baseline)
    assert load_recurring(entry).candidate_count == 100
    assert load_history(entry).size == root.size


def test_deep_observation_digest_is_iterative_and_does_not_add_node_fields(observations):
    source, policy, _store, _previous, _saved = observations
    root = scan(source).root
    root.children = []
    current = root
    for _index in range(1200):
        child = Node("deep", True, parent=current, children=[], snapshot=root.snapshot)
        current.children.append(child)
        current = child
    before = tuple(Node.__slots__)
    assert recurring.tree_signature(root) is not None
    assert tuple(Node.__slots__) == before and "recurring" not in before


@pytest.mark.skipif(os.name != "nt", reason="Windows lexical drive case/slash aliases")
def test_windows_schedule_and_candidate_case_aliases_do_not_invent_new_junk(observations):
    source, policy, _store, previous, saved = observations
    alias = str(source).swapcase().replace("\\", "/")
    root = scan(alias).root
    now = time.time()
    config = MonitorConfig(True, interval_hours=1, roots=(alias,))
    attempt = claim_scan(config, alias, now - 1)
    context = recurring.ProposalContext(attempt, config.interval_hours, now)
    proposal = recurring.prepare(root, policy, context, previous=previous, saved=saved)
    assert proposal.comparison_complete and not proposal.new_junk and not proposal.growth
    assert recurring.proposal_status(proposal, root, policy, config, replace(attempt, state="complete"), now) is None


@pytest.mark.parametrize("mutation", ["approved", "outside", "boolean", "unknown_rule", "unknown_row", "duplicate"])
def test_loaded_metadata_rejects_action_fields_or_invalid_inventory(observations, mutation):
    source, _policy, _store, previous, _saved = observations
    data = json.loads(recurring.dump_baseline(previous))
    if mutation == "approved":
        data["approved"] = True
    elif mutation == "outside":
        data["candidates"][0]["path"] = str(source.parent / "foreign.dmp")
    elif mutation == "boolean":
        data["candidate_count"] = True
    elif mutation == "unknown_rule":
        data["candidates"][0]["rule"] = "run-command"
    elif mutation == "unknown_row":
        data["candidates"][0]["action"] = "trash"
    else:
        data["candidates"].append(data["candidates"][0])
        data["candidate_count"] += 1
    with pytest.raises(ValueError):
        recurring.load_baseline(json.dumps(data))


def test_cancellation_virtual_roots_and_unbounded_metadata_are_refused(observations):
    source, policy, _store, previous, _saved = observations
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(recurring.ProposalCancelledError):
        recurring.capture(scan(source).root, policy, time.time(), cancel=cancel)
    with pytest.raises(ValueError, match="physical"):
        recurring.capture(Node("", True), policy, time.time())
    with pytest.raises(ValueError, match="size limit"):
        recurring.load_baseline(" " * (recurring.MAX_BYTES + 1))
    text = recurring.dump_baseline(previous).replace('"version":1', '"version":1,"version":1', 1)
    with pytest.raises(ValueError, match="Duplicate"):
        recurring.load_baseline(text)
