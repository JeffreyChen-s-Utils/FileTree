"""Experimental metadata trees retain one published root, ACL authority and ordinary fallback semantics."""

from contextlib import nullcontext
import ctypes
import errno
from itertools import count
import os
from pathlib import Path
import stat
import sys
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import mft, mft_scan, scanner
from je_file_tree.core.snapshot import pack_snapshot, unpack_snapshot
from je_file_tree.core.windows_directory import WindowsEntry


def _model(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "branch").mkdir()
    (root / "branch/keep").write_bytes(b"keep")
    (root / "visible").write_bytes(b"visible")
    (root / ".hidden").write_bytes(b"hidden")
    real = os.lstat
    def metadata(path, *args, **kwargs):
        info = real(path, *args, **kwargs)
        if Path(path).is_relative_to(root):
            fields = {name: getattr(info, name, 0) for name in mft_scan._STAT_FIELDS}
            fields.update(st_birthtime=info.st_ctime, st_birthtime_ns=info.st_ctime_ns)
            return SimpleNamespace(**fields)
        return info
    monkeypatch.setattr(mft_scan.os, "lstat", metadata)
    monkeypatch.setattr(mft_scan, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(mft_scan, "_audit", lambda _n, info, _v, _p, check: (check(), info)[1])
    closed = []
    class Reader:
        def __init__(self, path):
            assert path == str(root)
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            closed.append(True)
        def verify(self):
            return None
    monkeypatch.setattr(mft_scan, "NTFSReader", Reader)
    monkeypatch.setattr(mft_scan, "anchored_directory", lambda _stamps: nullcontext())
    monkeypatch.setattr(mft_scan, "directory_stamps", lambda path: path)
    def allocation(*_args, **_kwargs):
        return lambda _entry, info: info.st_size
    monkeypatch.setattr(mft_scan, "allocation_for", allocation)
    monkeypatch.setattr(scanner, "allocation_for", allocation)
    def listing(path, expected, check):
        assert expected.inode == real(path).st_ino
        for file in Path(path).iterdir():
            check()
            info = metadata(file)
            yield WindowsEntry(file.name, info.st_ino, info.st_size, info.st_size,
                               info.st_file_attributes, info.st_reparse_tag,
                               (info.st_ctime_ns, 0, info.st_mtime_ns, info.st_ctime_ns))
    monkeypatch.setattr(mft_scan, "directory_entries", listing)
    return root, closed


def _rows(root):
    return sorted((node.path, node.size, node.allocated, node.file_count, node.dir_count, node.error)
                  for node in root.iter_nodes())


@pytest.mark.parametrize("options", [scanner.ScanOptions(), scanner.ScanOptions(include_hidden=False),
                                    scanner.ScanOptions(exclude=("branch",)),
                                    scanner.ScanOptions(file_times=True, count_hard_links=True)])
def test_staged_native_tree_matches_options_and_adopts_into_the_same_single_published_root(
        tmp_path, monkeypatch, options):
    from dataclasses import replace  # noqa: PLC0415
    root, closed = _model(tmp_path, monkeypatch)
    ordinary = scanner.scan(root, options=options)
    published, progress = [], []
    result = scanner.scan(root, options=replace(options, experimental_mft=True),
                          on_root=published.append, progress=progress.append, progress_interval=0)
    assert result.backend == "mft" and result.root is published[0] and len(published) == 1
    assert _rows(result.root) == _rows(ordinary.root) and result.errors == ordinary.errors
    assert all(node.parent is result.root for node in result.root.children)
    assert closed == [True] and progress[-1].files == result.root.file_count


def test_corrupt_candidate_is_discarded_before_ordinary_fallback_without_second_root(tmp_path, monkeypatch):
    root, closed = _model(tmp_path, monkeypatch)
    def corrupted(*_args):
        raise mft.MFTParseError("owned raw metadata fixture")
    monkeypatch.setattr(mft_scan, "_audit", corrupted)
    published = []
    result = scanner.scan(root, options=scanner.ScanOptions(experimental_mft=True), on_root=published.append)
    assert result.backend == "ordinary" and result.root is published[0] and len(published) == 1
    assert result.root.file_count == 3 and closed == [True]


def test_permission_denied_folder_remains_incomplete_and_never_raw_visible(tmp_path, monkeypatch):
    root, closed = _model(tmp_path, monkeypatch)
    listing = mft_scan.directory_entries
    def denied(path, *args):
        if Path(path).name == "branch":
            raise PermissionError("owned denied branch")
        return listing(path, *args)
    monkeypatch.setattr(mft_scan, "directory_entries", denied)
    result = scanner.scan(root, options=scanner.ScanOptions(experimental_mft=True))
    branch = next(node for node in result.root.children if node.name == "branch")
    assert branch.error == scanner.ACCESS_DENIED and not branch.children
    assert result.errors == [(str(root / "branch"), scanner.ACCESS_DENIED)]
    assert result.backend == "mft" and closed == [True]


def test_cancellation_while_paused_keeps_the_same_partial_root_without_opening_a_reader(tmp_path, monkeypatch):
    root, closed = _model(tmp_path, monkeypatch)
    cancel, pause, published = threading.Event(), threading.Event(), []
    cancel.set()
    pause.set()
    with pytest.raises(scanner.ScanCancelledError) as captured:
        scanner.scan(root, options=scanner.ScanOptions(experimental_mft=True), on_root=published.append,
                     cancel=cancel, pause=pause)
    assert captured.value.partial.root is published[0]
    assert published[0].error == scanner.NOT_SCANNED and closed == []


def test_progress_callback_errors_are_not_interpreted_as_metadata_fallback(tmp_path, monkeypatch):
    root, closed = _model(tmp_path, monkeypatch)
    calls = []
    def failed(progress):
        calls.append(progress)
        raise ValueError("owned callback failure")
    with pytest.raises(ValueError, match="callback"):
        scanner.scan(root, options=scanner.ScanOptions(experimental_mft=True), progress=failed, progress_interval=0)
    assert len(calls) == 1 and closed == [True]


def test_stop_after_root_listing_retains_unread_branch_and_counted_partial_totals(tmp_path, monkeypatch):
    root, closed = _model(tmp_path, monkeypatch)
    ticks = count()
    monkeypatch.setattr(scanner.time, "monotonic", lambda: next(ticks) / 10)
    cancel, published = threading.Event(), []
    with pytest.raises(scanner.ScanCancelledError) as captured:
        scanner.scan(root, options=scanner.ScanOptions(experimental_mft=True, count_hard_links=True),
                     on_root=published.append, cancel=cancel, progress_interval=0,
                     progress=lambda _p: cancel.set())
    partial = captured.value.partial
    assert partial.backend == "mft" and partial.root is published[0] and closed == [True]
    assert partial.root.file_count == 2 and partial.root.size == 13 and partial.hard_links is not None
    branch = next(node for node in partial.root.children if node.name == "branch")
    assert branch.error == scanner.NOT_SCANNED and not branch.children
    assert partial.elapsed > 0


def test_denied_native_path_never_becomes_a_raw_node_and_partial_coverage_is_visible(tmp_path, monkeypatch):
    root, closed = _model(tmp_path, monkeypatch)
    metadata = mft_scan.os.lstat
    def denied(path, *args, **kwargs):
        if Path(path) == root / "visible":
            raise PermissionError(errno.EACCES, "owned denied file")
        return metadata(path, *args, **kwargs)
    listing = mft_scan.directory_entries
    # Freeze only the ordinary visible directory reply before a later per-path ACL failure.
    entries = list(listing(str(root), unpack_snapshot(scanner.stat_snapshot(str(root))), lambda: None))
    monkeypatch.setattr(mft_scan.os, "lstat", denied)
    monkeypatch.setattr(mft_scan, "directory_entries", lambda path, *args: iter(entries)
                        if Path(path) == root else listing(path, *args))
    result = scanner.scan(root, options=scanner.ScanOptions(experimental_mft=True))
    assert result.backend == "mft" and closed == [True]
    assert result.root.file_count == 2 and result.root.error == scanner.PARTIAL_FOLDER
    assert result.errors == [(str(root / "visible"), scanner.ACCESS_DENIED)]
    assert all(node.name != "visible" for node in result.root.children)


def _audit_fixture(monkeypatch):
    info = SimpleNamespace(st_dev=1, st_ino=281474976710676, st_size=7, st_mode=stat.S_IFREG | 0o666,
                           st_nlink=1, st_mtime_ns=200, st_ctime_ns=100, st_birthtime_ns=100,
                           st_mtime=0.0000002, st_ctime=0.0000001, st_atime=0.0000003,
                           st_file_attributes=0x20, st_reparse_tag=0)
    visible = WindowsEntry("keep", info.st_ino, 7, 8, 0x20, 0, (100, 300, 200, 400))
    standard = mft.StandardInformation(100, 200, 400, 300, 0x20)
    name = mft.FileName(123, 1, "keep")
    data = SimpleNamespace(kind=mft.DATA, name="", lowest_vcn=0, size=7, value=None)
    metadata = [SimpleNamespace(kind=kind, resident=True, value=b"owned metadata")
                for kind in (mft.FILE_NAME, mft.STANDARD_INFORMATION)]
    record = SimpleNamespace(in_use=True, base_reference=0, reference=info.st_ino, links=1, is_dir=False)
    native = SimpleNamespace(record=lambda ordinal: record, attributes=lambda _r, _c: (*metadata, data))
    monkeypatch.setattr(mft_scan.mft, "parse_file_name", lambda _value: name)
    monkeypatch.setattr(mft_scan.mft, "parse_standard_information", lambda _value: standard)
    return native, info, visible, record, data, metadata


def test_raw_metadata_constructs_the_same_snapshot_without_payload_or_windows_changed_date_confusion(monkeypatch):
    native, info, visible, _record, _data, _metadata = _audit_fixture(monkeypatch)
    result = mft_scan._audit(native, info, visible, 123, lambda: None)
    assert pack_snapshot(result) == pack_snapshot(info)
    assert unpack_snapshot(pack_snapshot(result)).changed_ns == 100  # Windows stat ctime is creation.


@pytest.mark.parametrize("case", ["identity", "links", "size", "payload", "nonresident", "parent"])
def test_raw_metadata_mismatches_refuse_before_nodes(case, monkeypatch):
    native, info, visible, record, data, metadata = _audit_fixture(monkeypatch)
    if case == "identity":
        record.reference += 1
    elif case == "links":
        record.links += 1
    elif case == "size":
        data.size += 1
    elif case == "payload":
        data.value = b"payload must never be retained"
    elif case == "nonresident":
        metadata[0].resident = False
    parent = 124 if case == "parent" else 123
    with pytest.raises(mft.MFTParseError):
        mft_scan._audit(native, info, visible, parent, lambda: None)


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows token fallback")
def test_actual_unelevated_windows_token_falls_back_without_another_root_or_source_change(tmp_path):
    if ctypes.WinDLL("shell32.dll", winmode=0x800).IsUserAnAdmin():
        pytest.skip("Requires an actual unelevated token; never changes process privileges")
    source = tmp_path / "keep.bin"
    source.write_bytes(b"owned unelevated fixture")
    before, published = source.stat(), []
    result = scanner.scan(tmp_path, options=scanner.ScanOptions(experimental_mft=True), on_root=published.append)
    after = source.stat()
    assert result.backend == "ordinary" and result.root is published[0] and len(published) == 1
    assert result.root.file_count == 1 and source.read_bytes() == b"owned unelevated fixture"
    assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
