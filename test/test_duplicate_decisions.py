"""Duplicate decisions validate the keeper and every extra, not just selected removals."""

import os
import threading
from dataclasses import replace

import pytest

from je_file_tree.core import duplicate_decisions
from je_file_tree.core.duplicate_decisions import check_group
from je_file_tree.core.duplicates import estimate_duplicate_savings, find_duplicates
from je_file_tree.core.protected import PROGRAMS, Protection
from je_file_tree.core.scanner import scan


@pytest.fixture
def decision(tmp_path):
    for name in ("kept", "extra", "second"):
        (tmp_path / name).write_bytes(b"same contents" * 10000)
    root = scan(tmp_path).root
    group = find_duplicates(root, min_size=1).groups[0]
    keeper = next(node for node in group.files if node.name == "kept")
    return root, replace(group, kept=keeper)


def test_choices_and_proofs_are_required_and_keepers_change_estimates(decision) -> None:
    root, group = decision
    assert check_group(group, root, rehash=True) is None
    assert check_group(replace(group, kept=None), root) == "duplicate_choose"
    assert check_group(replace(group, digest=None), root) == "duplicate_unverified"
    undecided = estimate_duplicate_savings([replace(group, kept=None)], root)
    assert undecided.total.recoverable_max is None and undecided.groups[0].recoverable_max is None
    group.kept.allocated = 0
    extra = next(node for node in group.files if node is not group.kept)
    first = estimate_duplicate_savings([group], root)
    second = estimate_duplicate_savings([replace(group, kept=extra)], root)
    assert first.total.allocated > second.total.allocated


def test_changed_keeper_invalidates_the_whole_group_even_with_restored_size_and_time(decision) -> None:
    root, group = decision
    info = os.stat(group.kept.path)
    with open(group.kept.path, "wb") as stream:
        stream.write(b"other content" * 10000)
    os.utime(group.kept.path, ns=(info.st_atime_ns, info.st_mtime_ns))
    assert check_group(group, root, rehash=True) in ("changed", "duplicate_content")


def test_rehash_compares_to_original_digest_not_only_to_other_current_copies(decision) -> None:
    root, group = decision
    assert check_group(replace(group, digest=b"wrong"), root, rehash=True) == "duplicate_content"


def test_all_members_must_be_inside_unprotected_and_not_hard_linked(decision, tmp_path) -> None:
    root, group = decision
    outside = scan(tmp_path.parent).root
    assert check_group(group, outside) == "outside"
    places = [Protection(group.kept.path, PROGRAMS)]
    assert check_group(group, root, places=places) == "protected"
    extra = next(node for node in group.files if node is not group.kept)
    os.link(extra.path, tmp_path / "alias")
    assert check_group(group, root) in ("duplicate_hard_links", "changed")


def test_an_earlier_copy_changing_during_the_last_hash_is_rejected(decision, monkeypatch) -> None:
    root, group = decision
    original = duplicate_decisions.hash_unchanged

    def mutate_after_last(node, *, cancel):
        digest = original(node, cancel=cancel)
        if node is group.files[-1]:
            with open(group.files[0].path, "ab") as stream:
                stream.write(b"changed")
        return digest

    monkeypatch.setattr(duplicate_decisions, "hash_unchanged", mutate_after_last)
    assert check_group(group, root, rehash=True) == "changed"


def test_cancellation_rejects_group_before_a_move(decision) -> None:
    root, group = decision
    cancel = threading.Event()
    cancel.set()
    assert check_group(group, root, cancel=cancel, rehash=True) == "cancelled"


@pytest.mark.parametrize("failure", ["changed_keeper", "bad_hash", "selected_keeper"])
def test_trash_worker_leaves_entire_failed_group_untouched(qapp, decision, monkeypatch, failure) -> None:
    from je_file_tree.gui import file_actions
    from je_file_tree.gui.trash_worker import TrashWorker
    from je_file_tree.gui.scan_worker import wait_for
    from test_gui import _wait

    root, group = decision
    picked = [node for node in group.files if node is not group.kept]
    if failure == "changed_keeper":
        with open(group.kept.path, "ab") as stream:
            stream.write(b"changed")
    elif failure == "bad_hash":
        group = replace(group, digest=b"invalid")
    else:
        picked.append(group.kept)
    moved, results = [], []
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    worker = TrashWorker(root, picked, [], {}, decisions=[group])
    worker.done.connect(results.append)
    worker.start()
    _wait(qapp, lambda: bool(results))
    wait_for(worker)
    assert moved == [] and len(results[0].skipped) == len(picked)
    assert all(os.path.isfile(node.path) for node in group.files)


def test_pre_move_rehash_runs_on_worker_and_keeps_only_explicit_copy(qapp, decision, monkeypatch) -> None:
    from je_file_tree.gui import file_actions
    from je_file_tree.gui.trash_worker import TrashWorker
    from je_file_tree.gui.scan_worker import wait_for
    from test_gui import _wait

    root, group = decision
    original = duplicate_decisions.hash_unchanged
    threads, hashed, moved, results = [], [], [], []

    def observe(node, *, cancel):
        threads.append(threading.get_ident())
        hashed.append(node)
        return original(node, cancel=cancel)

    def move(path):
        assert set(hashed) == set(group.files), "every group member must be rehashed before its first move"
        moved.append(path)
        return True

    monkeypatch.setattr(duplicate_decisions, "hash_unchanged", observe)
    monkeypatch.setattr(file_actions, "trash_receipt", move)
    picked = [node for node in group.files if node is not group.kept]
    worker = TrashWorker(root, picked, [], {}, decisions=[group])
    worker.done.connect(results.append)
    worker.start()
    _wait(qapp, lambda: bool(results))
    wait_for(worker)
    assert set(moved) == {node.path for node in picked}
    assert group.kept.path not in moved and all(thread != threading.get_ident() for thread in threads)

