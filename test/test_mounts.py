"""Bind-mount boundaries use the process namespace, including names stat/ismount cannot distinguish."""

import os
import sys
import threading
from io import StringIO
from types import SimpleNamespace
from pathlib import Path

import pytest

from je_file_tree.core import mounts, scanner
from je_file_tree.core.capacity import capacity_ledger
from je_file_tree.core.cleanup import find_cleanup
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.mounts import (
    MOUNT_BOUNDARY, MountChangedError, MountSurvey, boundary_path, mount_points, parse_mountinfo,
)
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot


def _line(point):
    return f"53 29 8:1 /source {point} rw,relatime shared:1 master:2 - ext4 /dev/test rw\n"


def test_decode_unicode_whitespace_and_backslash_once():
    text = _line(r"/mnt/資料\040space\011tab\012newline\134040")
    assert parse_mountinfo(text) == frozenset({"/mnt/資料 space\ttab\nnewline\\040"})
    assert parse_mountinfo(_line("/") + _line("/mnt/nested/") + _line("/mnt/nested")) == {"/", "/mnt/nested"}
    assert parse_mountinfo(_line("//mnt/nested")) == {"/mnt/nested"}
    if os.name == "posix":
        assert boundary_path("//mnt/nested") == "/mnt/nested"


@pytest.mark.parametrize("text", ["", "broken", "1 2 8:1 / /missing rw", _line("relative"),
                                  _line(r"/unknown\999"), _line(r"/null\000"), _line("/nul\0")])
def test_malformed_tables_are_not_treated_as_no_mounts(text):
    with pytest.raises(ValueError):
        parse_mountinfo(text)


def test_mount_survey_is_fresh_and_namespace_specific(tmp_path, monkeypatch):
    table = tmp_path / "mountinfo"
    monkeypatch.setattr(mounts, "_MOUNTINFO", table)
    monkeypatch.setattr(mounts, "sys", SimpleNamespace(platform="linux"))
    table.write_text(_line("/") + _line(r"/mnt/one\040folder"), encoding="utf-8")
    assert mount_points() == {os.path.normpath("/"), os.path.normpath("/mnt/one folder")}
    table.write_text(_line("/mnt/two"), encoding="utf-8")
    assert mount_points() == {os.path.normpath("/mnt/two")}
    table.write_text("malformed", encoding="utf-8")
    with pytest.raises(OSError, match="could not be determined"):
        mount_points()
    table.unlink()  # own fixture metadata, not a scanned entry
    with pytest.raises(FileNotFoundError):
        mount_points()


def test_non_linux_does_not_open_proc(monkeypatch):
    monkeypatch.setattr(mounts, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(mounts, "_MOUNTINFO", Path("does-not-exist"))
    assert mount_points() == frozenset()


def test_same_device_mount_is_not_traversed_or_proposed_for_cleanup(tmp_path, monkeypatch):
    mounted = tmp_path / "node_modules"
    mounted.mkdir()
    (mounted / "private").write_bytes(b"do not enter")
    (tmp_path / "normal").write_bytes(b"safe")
    calls = []

    def survey():
        calls.append(True)
        return frozenset({os.path.normpath(str(mounted))})

    monkeypatch.setattr(scanner, "mount_points", survey)
    result = scan(tmp_path)
    root = result.root
    mount = next(child for child in root.children if child.name == "node_modules")
    assert len(calls) == 2  # initial boundaries and the check before publishing a completed result
    assert mount.is_link and mount.error == MOUNT_BOUNDARY and mount.children == []
    assert unpack_snapshot(mount.snapshot).device == unpack_snapshot(root.snapshot).device
    assert root.size == 4 and root.file_count == 1
    assert (str(mounted), MOUNT_BOUNDARY) in result.errors
    assert not coverage_of(root).complete and not coverage_of(root).can_clean(root)
    assert find_cleanup(root) == []
    ledger = capacity_ledger(root)
    assert ledger.mounted_folders == 1 and ledger.other_volumes_bytes is None


def test_explicit_mount_root_remains_scannable_and_prefixes_are_not_boundaries(tmp_path, monkeypatch):
    mounted = tmp_path / "mount"
    mounted.mkdir()
    (mounted / "file").write_bytes(b"x")
    similarly_named = tmp_path / "mount-more"
    similarly_named.mkdir()
    (similarly_named / "file").write_bytes(b"y")
    monkeypatch.setattr(scanner, "mount_points", lambda: frozenset({os.path.normpath(str(mounted))}))
    assert scan(mounted).root.size == 1
    assert scan(tmp_path).root.size == 1
    assert next(child for child in scan(tmp_path).root.children if child.name == "mount-more").is_link is False


def test_unknown_mount_table_stops_before_reading_children(tmp_path, monkeypatch):
    reached = []

    def unknown():
        raise OSError("No mount table")

    monkeypatch.setattr(scanner, "mount_points", unknown)
    monkeypatch.setattr(scanner, "_read_folder", lambda *_args: reached.append(True))
    with pytest.raises(OSError, match="No mount table"):
        scan(tmp_path)
    assert reached == []


@pytest.mark.skipif(os.name != "posix", reason="Ancestor symlink fixture needs POSIX")
def test_mount_points_match_a_selected_root_reached_through_an_ancestor_alias(tmp_path, monkeypatch):
    actual = tmp_path / "actual"
    root = actual / "root"
    mounted = root / "mounted"
    mounted.mkdir(parents=True)
    (mounted / "private").write_bytes(b"x")
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    monkeypatch.setattr(scanner, "mount_points", lambda: frozenset({str(mounted)}))
    result = scan(alias / "root")
    assert result.root.size == 0
    assert result.root.children[0].error == MOUNT_BOUNDARY


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Actual Linux process mount namespace")
def test_native_process_mount_table_contains_filesystem_root():
    assert "/" in mount_points()


@pytest.mark.parametrize("removed", [False, True])
def test_mount_added_or_removed_during_scan_prevents_a_completed_result(tmp_path, monkeypatch, removed):
    target = tmp_path / "mounted"
    target.mkdir()
    (target / "payload").write_bytes(b"owned")
    present, absent = frozenset({str(target)}), frozenset()
    surveys = iter([present, absent] if removed else [absent, present])
    monkeypatch.setattr(scanner, "mount_points", lambda: next(surveys))
    with pytest.raises(MountChangedError, match="scan again"):
        scan(tmp_path)


def test_mount_change_outside_selected_scope_does_not_abort_scan(tmp_path, monkeypatch):
    selected = tmp_path / "selected"
    selected.mkdir()
    (selected / "payload").write_bytes(b"owned")
    surveys = iter([frozenset(), frozenset({str(tmp_path / "selected-more")})])
    monkeypatch.setattr(scanner, "mount_points", lambda: next(surveys))
    assert scan(selected).root.size == 5


def test_mount_change_in_final_progress_callback_is_checked_before_return(tmp_path, monkeypatch):
    current = frozenset()
    monkeypatch.setattr(scanner, "mount_points", lambda: current)

    def changed(_progress):
        nonlocal current
        current = frozenset({str(tmp_path / "new-mount")})

    with pytest.raises(MountChangedError):
        scan(tmp_path, progress=changed)


@pytest.mark.parametrize("contents", ["", "mnt_id: invalid\n", "mnt_id: 2\nmnt_id: 3\n", "x" * 4097])
def test_missing_or_invalid_descriptor_mount_id_is_not_assumed_safe(monkeypatch, contents):
    monkeypatch.setattr(mounts, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(mounts, "_statx_mount", lambda _fd: None)
    monkeypatch.setattr(mounts, "open", lambda _path, **_kwargs: StringIO(contents), raising=False)
    with pytest.raises(MountChangedError):
        mounts.descriptor_mount(12)


@pytest.mark.parametrize("status, mask, value, expected", [(0, 0x1000, 42, 42), (0, 0, 42, None),
                                                           (0, 0x1000, 0, None), (-1, 0x1000, 42, None)])
def test_statx_requires_a_supported_nonzero_mount_id_and_only_queries_open_descriptor(
        monkeypatch, status, mask, value, expected):
    import ctypes

    def query(fd, path, flags, requested, result):
        assert fd == 12 and path == b"" and flags == 0x5800 and requested == 0x1000
        structure = ctypes.cast(result, ctypes.POINTER(mounts._Statx)).contents
        structure.mask, structure.mount_id = mask, value
        return status

    monkeypatch.setattr(mounts, "_statx_function", lambda: query)
    assert ctypes.sizeof(mounts._Statx) == 256 and mounts._Statx.mount_id.offset == 144
    assert mounts._statx_mount(12) == expected


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux native statx/fdinfo mount IDs")
def test_native_descriptor_backends_agree_and_fallback_preserves_guard(tmp_path, monkeypatch):
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        proc = mounts._proc_mount(fd)
        native = mounts._statx_mount(fd)
        assert native is None or native == proc
        assert mounts.descriptor_mount(fd) == proc
        monkeypatch.setattr(mounts, "_statx_function", lambda: None)
        assert mounts.descriptor_mount(fd) == proc
    finally:
        os.close(fd)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux directory descriptors")
def test_new_same_device_mount_id_is_rejected_before_reading_queued_folder(tmp_path, monkeypatch):
    target = tmp_path / "queued"
    target.mkdir()
    (target / "private").write_bytes(b"owned")
    real_mount, record = mounts.descriptor_mount, scanner._record_entries
    inspected = []
    calls = 0

    def changed(fd):
        nonlocal calls
        calls += 1
        return real_mount(fd) + int(calls == 3)  # root survey, root read, then queued folder

    def recording(folder, *args):
        inspected.append(folder.path)
        return record(folder, *args)

    monkeypatch.setattr(mounts, "descriptor_mount", changed)
    monkeypatch.setattr(scanner, "_record_entries", recording)
    with pytest.raises(MountChangedError):
        scan(tmp_path, options=scanner.ScanOptions(workers=1))
    assert str(target) not in inspected
    assert not any(thread.name.startswith("file-tree-scan-") for thread in threading.enumerate())


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux directory descriptors")
def test_pinned_directory_entries_keep_original_metadata_after_path_replacement(tmp_path):
    target, relocated = tmp_path / "target", tmp_path / "relocated"
    target.mkdir()
    (target / "payload").write_bytes(b"original")
    snapshot = stat_snapshot(str(target))
    survey = MountSurvey(str(tmp_path), stat_snapshot(str(tmp_path)), mount_points())
    with survey.listing(str(target), snapshot) as entries:
        target.rename(relocated)
        target.mkdir()
        (target / "payload").write_bytes(b"new")
        entry = next(entries)
        assert entry.path == str(target / "payload")
        assert entry.stat(follow_symlinks=False).st_size == 8
        assert entry.stat(follow_symlinks=False).st_ino == (relocated / "payload").stat().st_ino
    assert (target / "payload").read_bytes() == b"new"
    with pytest.raises(OSError, match="folder replaced"), survey.listing(str(target), snapshot):
        pytest.fail("A replaced queued directory must not be read")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux directory descriptors")
def test_unreadable_root_remains_an_incomplete_scan_without_traversal(tmp_path, monkeypatch):
    real_open = mounts.os.open

    def denied(path, *args, **kwargs):
        if path == str(tmp_path):
            raise PermissionError(13, "access denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(mounts.os, "open", denied)
    result = scan(tmp_path)
    assert result.root.error == scanner.ACCESS_DENIED and result.root.children == []
    assert not coverage_of(result.root).complete and find_cleanup(result.root) == []
