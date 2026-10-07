"""Exclusive duplicate replacements use only fresh owned regular files, never existing user data."""

import os
import threading
from dataclasses import replace

import pytest

from test_duplicate_links import _fixture, open_bytes
from je_file_tree.core import duplicate_link_ops as ops
from je_file_tree.core import duplicate_links
from je_file_tree.core.duplicates import find_duplicates
from je_file_tree.core.scanner import scan


def test_native_multiple_copies_become_same_identity_without_artifacts_or_content_loss(tmp_path):
    root, group = _fixture(tmp_path, copies=3)
    plan = duplicate_links.prepare_links(root, [group])
    before = {node.path: open_bytes(node.path) for node in group.files}
    result = ops.execute_links(plan)
    assert len(result.outcomes) == 2 and all(item.linked and not item.error and not item.retained
                                           for item in result.outcomes)
    assert len({os.stat(path).st_ino for path in before}) == 1
    assert all(os.stat(path).st_nlink == 3 and open_bytes(path) == data for path, data in before.items())
    assert len(os.listdir(root.path)) == 3 and not result.canceled


def test_changed_content_and_cancel_leave_original_independent_copies(tmp_path):
    root, group = _fixture(tmp_path)
    plan = duplicate_links.prepare_links(root, [group])
    extra = plan.pairs[0].copy_path
    with open(extra, "wb") as stream:
        stream.write(b"changed owned payload")
    result = ops.execute_links(plan)
    assert not result.outcomes[0].linked and result.outcomes[0].error
    assert open_bytes(extra) == b"changed owned payload" and len(os.listdir(root.path)) == 2
    cancel = threading.Event()
    cancel.set()
    result = ops.execute_links(plan, cancel=cancel)
    assert result.canceled and not result.outcomes[0].linked and len(os.listdir(root.path)) == 2


@pytest.mark.parametrize("phase", ["backup", "publish", "retire"])
def test_native_failures_preserve_original_or_truthful_published_alias_and_backup(tmp_path, monkeypatch, phase):
    root, group = _fixture(tmp_path)
    plan = duplicate_links.prepare_links(root, [group])
    pair = plan.pairs[0]
    original = open_bytes(pair.copy_path)
    native = ops.rename_no_replace

    def rename(source, target, old, new):
        if phase == "backup" and target.endswith(".bak") or phase == "publish" and source.endswith(".tmp"):
            raise PermissionError("owned native failure")
        native(source, target, old, new)

    def retire(*_args):
        raise PermissionError("owned retirement failure")

    monkeypatch.setattr(ops, "rename_no_replace", rename)
    if phase == "retire":
        monkeypatch.setattr(ops, "_retire_backup", retire)
    result = ops.execute_links(plan)
    item = result.outcomes[0]
    assert item.error and open_bytes(pair.copy_path) == original
    if phase == "retire":
        assert item.linked and len(item.retained) == 1 and open_bytes(item.retained[0]) == original
    else:
        assert not item.linked and not item.retained and len(os.listdir(root.path)) == 2
        assert os.stat(pair.copy_path).st_ino != os.stat(pair.keeper_path).st_ino


def test_arrival_at_publication_is_never_overwritten_and_backup_remains_visible(tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    plan = duplicate_links.prepare_links(root, [group])
    pair, native = plan.pairs[0], ops.rename_no_replace

    def arrival(source, target, old, new):
        if source.endswith(".tmp"):
            with open(target, "xb") as stream:
                stream.write(b"preserved arrival")
        native(source, target, old, new)

    monkeypatch.setattr(ops, "rename_no_replace", arrival)
    result = ops.execute_links(plan)
    item = result.outcomes[0]
    assert not item.linked and "rollback" in item.error and len(item.retained) == 1
    assert open_bytes(pair.copy_path) == b"preserved arrival"
    assert open_bytes(item.retained[0]) == open_bytes(pair.keeper_path)


def test_cancel_after_exclusive_backup_rolls_back_without_deleting_original_payload(tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    plan = duplicate_links.prepare_links(root, [group])
    cancel, native = threading.Event(), ops.rename_no_replace

    def cancel_after_backup(source, target, old, new):
        native(source, target, old, new)
        if target.endswith(".bak"):
            cancel.set()

    monkeypatch.setattr(ops, "rename_no_replace", cancel_after_backup)
    result = ops.execute_links(plan, cancel=cancel)
    item = result.outcomes[0]
    assert result.canceled and not item.linked and item.error and not item.retained
    assert len(os.listdir(root.path)) == 2 and os.stat(plan.pairs[0].copy_path).st_nlink == 1


def test_change_after_publication_retains_old_bytes_and_reports_actual_linked_state(tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    plan = duplicate_links.prepare_links(root, [group])
    pair, native = plan.pairs[0], ops.rename_no_replace
    original = open_bytes(pair.copy_path)

    def modify_published(source, target, old, new):
        native(source, target, old, new)
        if source.endswith(".tmp"):
            with open(target, "wb") as stream:
                stream.write(b"new shared data")

    monkeypatch.setattr(ops, "rename_no_replace", modify_published)
    item = ops.execute_links(plan).outcomes[0]
    assert item.linked and item.error and len(item.retained) == 1
    assert open_bytes(pair.copy_path) == open_bytes(pair.keeper_path) == b"new shared data"
    assert open_bytes(item.retained[0]) == original


def test_cancel_after_publication_keeps_shared_name_and_original_backup(tmp_path, monkeypatch):
    root, group = _fixture(tmp_path, copies=3)
    plan = duplicate_links.prepare_links(root, [group])
    cancel, native = threading.Event(), ops.rename_no_replace

    def cancel_after_publish(source, target, old, new):
        native(source, target, old, new)
        if source.endswith(".tmp"):
            cancel.set()

    monkeypatch.setattr(ops, "rename_no_replace", cancel_after_publish)
    result = ops.execute_links(plan, cancel=cancel)
    first, second = result.outcomes
    assert result.canceled and first.linked and first.error and len(first.retained) == 1
    assert not second.linked and second.error and not second.retained
    assert open_bytes(first.retained[0]) == open_bytes(first.pair.keeper_path)
    assert os.stat(first.pair.copy_path).st_ino == os.stat(first.pair.keeper_path).st_ino
    assert os.stat(second.pair.copy_path).st_nlink == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows native named streams")
def test_native_ads_are_preserved_and_verified_while_retiring_delete_handle(tmp_path):
    root, _group = _fixture(tmp_path)
    stream_name, payload = ":owned-stream:$DATA", b"owned named payload" * 4096
    for name in os.listdir(root.path):
        with open(os.path.join(root.path, name) + stream_name, "wb") as stream:
            stream.write(payload)
    root = scan(root.path).root
    group = find_duplicates(root, min_size=1).groups[0]
    plan = duplicate_links.prepare_links(root, [replace(group, kept=group.files[0])])
    item = ops.execute_links(plan).outcomes[0]
    assert item.linked and not item.error and not item.retained
    assert open_bytes(item.pair.keeper_path + stream_name) == open_bytes(item.pair.copy_path + stream_name) == payload
    assert len(os.listdir(root.path)) == 2


def test_completed_callback_can_stop_after_actual_success_without_losing_outcomes(tmp_path):
    root, group = _fixture(tmp_path, copies=3)
    cancel, observed = threading.Event(), []

    def completed(outcome):
        observed.append(outcome)
        if outcome.linked:
            cancel.set()

    result = ops.execute_links(duplicate_links.prepare_links(root, [group]), cancel=cancel, completed=completed)
    assert observed == result.outcomes and result.canceled
    assert observed[0].linked and not observed[1].linked
    assert len(os.listdir(root.path)) == 3


def test_unsupported_native_link_reports_refusal_and_preserves_copies(tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)

    def unavailable(*_args, **_kwargs):
        raise NotImplementedError("no native link API")

    monkeypatch.setattr(os, "link", unavailable)
    item = ops.execute_links(duplicate_links.prepare_links(root, [group])).outcomes[0]
    assert not item.linked and "unavailable" in item.error and not item.retained
    assert len(os.listdir(root.path)) == 2 and all(os.stat(node.path).st_nlink == 1 for node in group.files)
