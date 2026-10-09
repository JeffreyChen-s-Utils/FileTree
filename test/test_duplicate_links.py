"""Read-only hard-link previews and full comparisons use disposable owned regular-file fixtures."""

from dataclasses import replace
import hashlib
import os
import threading

import pytest

from je_file_tree.core import duplicate_links as links
from je_file_tree.core.duplicates import DuplicateGroup, find_duplicates
from je_file_tree.core.node import Node
from je_file_tree.core.protected import Protection, PROGRAMS
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import pack_snapshot, stat_snapshot


def _fixture(tmp_path, *, body=b"owned identical duplicate payload", copies=2):
    root_path = tmp_path.resolve() / "scan"
    root_path.mkdir()
    for number in range(copies):
        (root_path / f"copy{number}").write_bytes(body)
    root = scan(root_path).root
    group = find_duplicates(root, min_size=1).groups[0]
    return root, replace(group, kept=group.files[0])


def test_read_only_preview_freezes_exact_paths_and_full_hash_verification_preserves_sources(tmp_path):
    root, group = _fixture(tmp_path, copies=3)
    names = {node.path: (stat_snapshot(node.path), open_bytes(node.path)) for node in group.files}
    plan = links.prepare_links(root, [group])
    assert len(plan.pairs) == 2 and all(not pair.reason for pair in plan.pairs)
    for pair in plan.pairs:
        result = links.verify_link_pair(plan, pair)
        assert result.digest == hashlib.sha256(open_bytes(pair.keeper_path)).digest()
        assert result.bytes_read == 2 * len(open_bytes(pair.copy_path))
    assert names == {node.path: (stat_snapshot(node.path), open_bytes(node.path)) for node in group.files}
    group.files.clear()
    group.proofs.clear()
    assert len(plan.groups[0].files) == 3 and len(plan.groups[0].proofs) == 3
    assert len(os.listdir(root.path)) == 3, "preview and verification create no temp links or copies"


def open_bytes(path):
    with open(path, "rb") as stream:
        return stream.read()


@pytest.mark.parametrize("bad", ["keeper", "proof", "changed", "protected", "hardlink", "special"])
def test_unsafe_member_refuses_entire_decision_without_payload_mutation(tmp_path, monkeypatch, bad):
    root, group = _fixture(tmp_path)
    copy = next(node for node in group.files if node is not group.kept)
    if bad == "keeper":
        group = replace(group, kept=None)
    elif bad == "proof":
        group = replace(group, proofs={})
    elif bad == "changed":
        with open(copy.path, "wb") as stream:
            stream.write(b"modified data")
    elif bad == "protected":
        monkeypatch.setattr(links, "protected_places", lambda: [Protection(copy.path, PROGRAMS)])
    elif bad == "hardlink":
        os.link(copy.path, tmp_path / "outside-alias")
    else:
        copy.is_dir = True  # A folder kind in a purported file group cannot become a linking decision.
    plan = links.prepare_links(root, [group])
    assert plan.pairs and all(pair.reason for pair in plan.pairs)
    with pytest.raises(ValueError, match="refused"):
        links.verify_link_pair(plan, plan.pairs[0])
    assert all(os.path.exists(node.path) for node in group.files)


def test_overlap_and_limits_are_rejected_and_cancel_returns_no_plan(tmp_path):
    root, group = _fixture(tmp_path)
    with pytest.raises(ValueError, match="overlap"):
        links.prepare_links(root, [group, group])
    large = DuplicateGroup(1, [Node(str(number), False) for number in range(links.MAX_LINKS + 2)])
    with pytest.raises(ValueError, match="1,000"):
        links.prepare_links(root, [large])
    cancel = threading.Event()
    cancel.set()
    assert links.prepare_links(root, [group], cancel=cancel) is None


def test_cancel_during_last_group_preparation_never_publishes_a_plan(tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    cancel = threading.Event()

    def canceled(*_args, **_kwargs):
        cancel.set()
        return "cancelled"

    monkeypatch.setattr(links, "check_group", canceled)
    assert links.prepare_links(root, [group], cancel=cancel) is None


def test_cancel_after_payload_comparison_never_publishes_a_verification(tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    plan = links.prepare_links(root, [group])
    cancel = threading.Event()
    monkeypatch.setattr(links, "_attributes", lambda *_: cancel.set())
    with pytest.raises(InterruptedError):
        links.verify_link_pair(plan, plan.pairs[0], cancel=cancel)


@pytest.mark.parametrize("change", ["path", "parent", "payload", "cancel"])
def test_verification_rechecks_frozen_paths_parents_payloads_and_cancel(tmp_path, change):
    root, group = _fixture(tmp_path)
    plan = links.prepare_links(root, [group])
    pair = plan.pairs[0]
    cancel = threading.Event()
    if change == "path":
        pair.copy.name = "different"
    elif change == "parent":
        os.rename(root.path, root.path + "-retained")
        os.mkdir(root.path)
    elif change == "payload":
        with open(pair.copy_path, "wb") as stream:
            stream.write(b"changed copy")
    else:
        cancel.set()
    with pytest.raises((OSError, ValueError)):
        links.verify_link_pair(plan, pair, cancel=cancel)


def test_full_hash_refuses_differing_tail_even_with_valid_current_metadata_proofs(tmp_path, monkeypatch):
    body = bytes(range(128)) * 32
    root, group = _fixture(tmp_path, body=body)
    extra = next(node for node in group.files if node is not group.kept)
    with open(extra.path, "r+b") as stream:
        stream.seek(-1, os.SEEK_END)
        stream.write(b"X")
    current = scan(root.path).root
    files = sorted(current.children, key=lambda node: node.name)
    proofs = {}
    for node in files:
        with open(node.path, "rb") as stream:
            proofs[node] = pack_snapshot(os.fstat(stream.fileno()))
    expected = hashlib.blake2b(body, digest_size=16).digest()
    group = DuplicateGroup(len(body), files, files[0], expected, proofs)
    monkeypatch.setattr(links, "_CHUNK", 31)
    plan = links.prepare_links(current, [group])
    assert not plan.pairs[0].reason, "metadata alone is never a content proof"
    with pytest.raises(ValueError, match="complete contents differ"):
        links.verify_link_pair(plan, plan.pairs[0])
    assert all(os.path.exists(node.path) for node in files)


@pytest.mark.skipif(os.name != "nt", reason="native NTFS alternate data streams")
def test_native_owned_ads_are_fully_compared_and_different_values_are_refused(tmp_path):
    root, group = _fixture(tmp_path)
    for node in group.files:
        with open(node.path + ":owned-test-ads", "wb") as stream:
            stream.write(b"owned alternate payload")
    root = scan(root.path).root
    group = find_duplicates(root, min_size=1).groups[0]
    group = replace(group, kept=group.files[0])
    plan = links.prepare_links(root, [group])
    result = links.verify_link_pair(plan, plan.pairs[0])
    assert result.bytes_read == 2 * (group.size + len(b"owned alternate payload"))
    extra = plan.pairs[0].copy
    with open(extra.path + ":owned-test-ads", "wb") as stream:
        stream.write(b"DIFFERENT named payload")
    root = scan(root.path).root
    group = find_duplicates(root, min_size=1).groups[0]
    plan = links.prepare_links(root, [replace(group, kept=group.files[0])])
    with pytest.raises(ValueError, match="alternate-stream"):
        links.verify_link_pair(plan, plan.pairs[0])


@pytest.mark.skipif(not hasattr(os, "setxattr"), reason="native POSIX extended attributes")
def test_same_main_bytes_never_hide_different_user_attribute_payloads(tmp_path):
    root, group = _fixture(tmp_path)
    for number, node in enumerate(group.files):
        os.setxattr(node.path, "user.filetree-owned", str(number).encode("ascii"))
    root = scan(root.path).root
    group = find_duplicates(root, min_size=1).groups[0]
    plan = links.prepare_links(root, [replace(group, kept=group.files[0])])
    with pytest.raises(ValueError, match="attribute contents differ"):
        links.verify_link_pair(plan, plan.pairs[0])
