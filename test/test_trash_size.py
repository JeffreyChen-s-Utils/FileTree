"""Native Windows query layout and owned POSIX payload fixtures never empty user bins."""

import ctypes
import os
from pathlib import Path
import stat
import sys
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import allocation, trash_size as trash


def test_windows_query_layout_success_errors_and_invalid_roots(monkeypatch):
    asked = []
    def query(root, pointer):
        info = ctypes.cast(pointer, ctypes.POINTER(trash._QueryInfo)).contents
        assert info.cbSize == ctypes.sizeof(trash._QueryInfo) == 24
        assert trash._QueryInfo.size.offset == 8 and trash._QueryInfo.count.offset == 16
        info.size, info.count = 12345, 7
        asked.append(root)
        return 0
    monkeypatch.setattr(trash, "_shell32", lambda: SimpleNamespace(SHQueryRecycleBinW=query))
    assert trash._windows_usage("D:/") == trash.TrashUsage(12345, 7, True)
    for root in ("", "D:", "D:/folder", "\\\\server\\share\\"):
        assert not trash._windows_usage(root).complete
    assert asked == ["D:/"]
    monkeypatch.setattr(trash, "_shell32", lambda: SimpleNamespace(SHQueryRecycleBinW=lambda *_args: -2147467259))
    assert "80004005" in trash._windows_usage("D:/").error


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows read-only API")
def test_windows_native_recycle_bin_read_only_query():
    root = Path.home().anchor
    usage = trash.trash_usage(root)
    assert usage.complete and usage.size >= 0 and usage.count >= 0


def test_emptying_requires_one_complete_unchanged_nonempty_drive(monkeypatch):
    calls = []
    approved = trash.TrashUsage(123, 2, True)
    monkeypatch.setattr(trash.sys, "platform", "win32")
    monkeypatch.setattr(trash, "_windows_usage", lambda _root: approved)
    monkeypatch.setattr(trash, "_shell32", lambda: SimpleNamespace(
        SHEmptyRecycleBinW=lambda *args: calls.append(args) or 0))
    trash.empty_windows_bin("D:/", approved)
    assert calls == [(None, "D:/", 7)]
    for root in ("", "D:", "D:/folder", "\\\\server\\share\\"):
        with pytest.raises(ValueError, match="one Windows"):
            trash.empty_windows_bin(root, approved)
    for invalid in (trash.TrashUsage(0, 0, True), trash.TrashUsage(123, 2, False)):
        with pytest.raises(ValueError, match="approval"):
            trash.empty_windows_bin("D:/", invalid)
    monkeypatch.setattr(trash, "_windows_usage", lambda _root: trash.TrashUsage(124, 2, True))
    with pytest.raises(ValueError, match="changed"):
        trash.empty_windows_bin("D:/", approved)
    assert len(calls) == 1
    monkeypatch.setattr(trash, "_windows_usage", lambda _root: approved)
    monkeypatch.setattr(trash, "_shell32", lambda: SimpleNamespace(SHEmptyRecycleBinW=lambda *_args: -2147467259))
    with pytest.raises(OSError, match="remaining"):
        trash.empty_windows_bin("D:/", approved)


def test_payload_counts_top_entries_and_logical_contents_without_reading_files(tmp_path, monkeypatch):
    payload = tmp_path / "Trash" / "files"
    payload.mkdir(parents=True)
    (payload / "資料.txt").write_bytes(b"123")
    (payload / "folder").mkdir()
    (payload / "folder" / "nested").write_bytes(b"45678")
    original = Path.read_bytes
    def forbidden(path):
        pytest.fail("payload contents must not be opened")
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert trash._payload_usage(payload, None) == trash.TrashUsage(8, 2, True)
    monkeypatch.setattr(Path, "read_bytes", original)
    assert (payload / "folder" / "nested").read_bytes() == b"45678"


def test_missing_unreadable_and_canceled_payload_are_distinct(tmp_path, monkeypatch):
    assert trash._payload_usage(tmp_path / "absent", None).complete
    payload = tmp_path / "files"
    payload.mkdir()
    cancel = threading.Event()
    cancel.set()
    assert trash._payload_usage(payload, cancel) is None
    original = os.scandir
    def denied(path):
        if Path(path) == payload:
            raise PermissionError("owned inaccessible fixture")
        return original(path)
    monkeypatch.setattr(os, "scandir", denied)
    usage = trash._payload_usage(payload, None)
    assert not usage.complete and "inaccessible" in usage.error


def test_locations_cover_home_private_shared_and_mac_bins(tmp_path):
    home, data = tmp_path / "home", tmp_path / "data"
    home.mkdir()
    data.mkdir()
    shared = tmp_path / ".Trash"
    shared.mkdir()
    shared.chmod(shared.stat().st_mode | stat.S_ISVTX)
    paths = trash._locations(tmp_path, home, data, 42, "linux")
    assert data / "Trash" / "files" in paths and tmp_path / ".Trash-42" / "files" in paths
    if os.name != "nt":
        assert shared / "42" / "files" in paths
    paths = trash._locations(tmp_path, home, data, 42, "darwin")
    assert paths == [home / ".Trash", tmp_path / ".Trashes" / "42"]
    assert home / ".local" / "share" / "Trash" / "files" in trash._locations(tmp_path, home, Path("relative"),
                                                                            42, "linux")


@pytest.mark.skipif(os.name == "nt", reason="owned POSIX symlinks")
def test_trash_links_never_follow_payload_or_parent(tmp_path):
    outside = tmp_path / "valuable"
    outside.mkdir()
    target = outside / "valuable.txt"
    target.write_bytes(b"valuable" * 100)
    payload = tmp_path / "Trash" / "files"
    payload.mkdir(parents=True)
    (payload / "link").symlink_to(outside, target_is_directory=True)
    usage = trash._payload_usage(payload, None)
    assert usage.count == 1 and usage.size < 800 and target.read_bytes() == b"valuable" * 100
    parent_link = tmp_path / "linked-bin"
    parent_link.symlink_to(outside, target_is_directory=True)
    assert not trash._payload_usage(parent_link / "files", None).complete


def test_fragment_units_and_windows_failures_do_not_become_fallback_estimates(monkeypatch):
    monkeypatch.setattr(allocation.sys, "platform", "linux")
    monkeypatch.setattr(allocation.os, "statvfs", lambda _path: SimpleNamespace(f_frsize=4096, f_bsize=8192),
                        raising=False)
    assert allocation.allocation_unit("/owned") == 4096
    monkeypatch.setattr(allocation.sys, "platform", "win32")
    monkeypatch.setattr(allocation, "_known_cluster", lambda _path: None)
    assert allocation.allocation_unit("D:/") is None
    assert allocation.cluster_size("D:/") == allocation.DEFAULT_CLUSTER
