"""Scan history stays compatible, bounded, cancellable and separate from recorded source paths."""

import json
import os
import threading
from pathlib import Path

import pytest

from je_file_tree.core import history
from je_file_tree.core.compare import load_saved
from je_file_tree.core.history import HistoryCancelledError, ScanHistory, load_history, root_key
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanOptions, scan


def test_saved_history_is_compatible_and_records_incomplete_coverage(sample_tree, tmp_path):
    store = ScanHistory(tmp_path / "history")
    root = scan(sample_tree).root
    first = store.save(root)
    assert first.size == 1000 and not first.incomplete
    assert first.path.parent.name == root_key(str(sample_tree))
    assert load_saved(first.path) == load_history(first)
    partial = scan(sample_tree, options=ScanOptions(exclude=("code",))).root
    second = store.save(partial)
    assert second.incomplete
    read = store.read(str(sample_tree), limit=1)
    assert read.count == 2 and read.entries == [second] and read.invalid == 0


def test_global_retention_drops_oldest_metadata_across_roots_and_preserves_foreign_files(tmp_path):
    roots = []
    for name in ("first", "second", "third"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "user-file").write_bytes(b"preserve")
        roots.append(scan(folder).root)
    store = ScanHistory(tmp_path / "history")
    first = store.save(roots[0])
    second = store.save(roots[1])
    foreign = first.path.parent / "notes.json"
    foreign.write_text("preserve", encoding="utf-8")
    malformed = first.path.parent / ("scan-" + "0" * 20 + "-" + "0" * 32 + ".json")
    malformed.write_text('{"not-owned":true}', encoding="utf-8")
    store.max_bytes = first.disk_bytes + second.disk_bytes + 10
    third = store.save(roots[2])
    assert not first.path.exists() and second.path.exists() and third.path.exists()
    assert sum(entry.disk_bytes for entry in store._entries(None)[0]) <= store.max_bytes
    assert foreign.read_text(encoding="utf-8") == "preserve" and malformed.exists()
    assert store.read(roots[0].path).invalid == 1
    assert all((Path(root.path) / "user-file").read_bytes() == b"preserve" for root in roots)


def test_oversized_and_canceled_writes_keep_prior_complete_history(sample_tree, tmp_path, monkeypatch):
    store = ScanHistory(tmp_path / "history")
    root = scan(sample_tree).root
    first = store.save(root)
    store.max_bytes = 10
    with pytest.raises(ValueError, match="byte limit"):
        store.save(root)
    store.max_bytes = history.DEFAULT_LIMIT
    cancel = threading.Event()
    original = history._folder_json

    def stopped(tree, depth):
        for chunk in original(tree, depth):
            cancel.set()
            yield chunk

    monkeypatch.setattr(history, "_folder_json", stopped)
    with pytest.raises(HistoryCancelledError):
        store.save(root, cancel=cancel)
    assert store.read(root.path).entries == [first]
    assert not list(first.path.parent.glob(".file-tree-*"))


def test_deep_history_load_is_iterative_and_matches_nested_folder_sizes(tmp_path):
    root = Node(str(tmp_path / "source"), True, size=7, children=[])
    current = root
    for number in range(1200):
        child = Node(str(number), True, size=7, parent=current, children=[])
        current.children.append(child)
        current = child
    store = ScanHistory(tmp_path / "history")
    entry = store.save(root)
    saved = load_history(entry)
    assert len(saved.folders) == 1201 and saved.size == 7
    assert saved.folders[folder_key_for_test(current)].size == 7


def folder_key_for_test(node):
    parts = []
    while node.parent is not None:
        parts.append(node.name)
        node = node.parent
    return "/".join(reversed(parts))


def test_changed_truncated_and_canceled_history_is_refused(sample_tree, tmp_path):
    store = ScanHistory(tmp_path / "history")
    entry = store.save(scan(sample_tree).root)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(HistoryCancelledError):
        load_history(entry, cancel=cancel)
    content = entry.path.read_text(encoding="utf-8")
    entry.path.write_text(content[:-2], encoding="utf-8")
    refreshed = store.read(str(sample_tree)).entries[0]
    with pytest.raises(ValueError, match="Truncated"):
        load_history(refreshed)
    with pytest.raises(ValueError, match="changed"):
        load_history(entry)


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink fixture")
def test_alias_history_root_and_bucket_cannot_write_or_trigger_retention(sample_tree, tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(external, target_is_directory=True)
    with pytest.raises(OSError, match="link"):
        ScanHistory(alias).save(scan(sample_tree).root)
    store = ScanHistory(tmp_path / "history")
    store.directory.mkdir()
    bucket = store.directory / root_key(str(sample_tree))
    bucket.symlink_to(external, target_is_directory=True)
    with pytest.raises(OSError, match="link"):
        store.save(scan(sample_tree).root)
    assert list(external.iterdir()) == []


def test_history_does_not_open_or_stat_scanned_source_files(sample_tree, tmp_path, monkeypatch):
    tree = scan(sample_tree).root
    original = os.open

    def metadata_only(path, *args, **kwargs):
        assert not Path(path).is_relative_to(sample_tree)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", metadata_only)
    entry = ScanHistory(tmp_path / "history").save(tree)
    assert load_history(entry).size == 1000
    document = json.loads(entry.path.read_text(encoding="utf-8"))
    assert document["history"]["root"] == str(sample_tree)


@pytest.mark.skipif(os.name != "nt", reason="Native Windows directory sharing")
def test_native_windows_retention_pins_directory_against_rename(tmp_path):
    directory = tmp_path / "owned"
    directory.mkdir()
    with history._pinned_directory(directory), pytest.raises(PermissionError):
        directory.rename(tmp_path / "renamed")
    directory.rename(tmp_path / "renamed")
    assert (tmp_path / "renamed").is_dir()


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor-relative retention")
def test_retention_uses_anchored_bucket_when_path_is_replaced(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    root = scan(source).root
    store = ScanHistory(tmp_path / "history")
    first = store.save(root)
    store.max_bytes = first.disk_bytes + 10
    original, relocated = os.unlink, store.directory / "relocated-owned-bucket"
    swapped = []

    def replace_parent(name, *, dir_fd=None):
        if dir_fd is not None and not swapped:
            first.path.parent.rename(relocated)
            first.path.parent.mkdir()
            (first.path.parent / first.path.name).write_text("foreign; preserve", encoding="utf-8")
            swapped.append(True)
        return original(name, dir_fd=dir_fd)

    monkeypatch.setattr(os, "unlink", replace_parent)
    with pytest.raises(FileNotFoundError):
        store.save(root)  # new entry moved away with the bucket; error stays visible
    assert swapped == [True]
    assert first.path.read_text(encoding="utf-8") == "foreign; preserve"
    assert not (relocated / first.path.name).exists()
