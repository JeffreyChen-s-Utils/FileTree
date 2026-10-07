"""Bind-mount boundaries use the process namespace, including names stat/ismount cannot distinguish."""

import os
import sys
from pathlib import Path

import pytest

from je_file_tree.core import mounts, scanner
from je_file_tree.core.capacity import capacity_ledger
from je_file_tree.core.cleanup import find_cleanup
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.mounts import MOUNT_BOUNDARY, boundary_path, mount_points, parse_mountinfo
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import unpack_snapshot


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
    monkeypatch.setattr(mounts.sys, "platform", "linux")
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
    monkeypatch.setattr(mounts.sys, "platform", "win32")
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
    assert len(calls) == 1
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
