"""Native metadata feeds never authorize operations; malformed/lost events require fresh scopes."""

import os
from pathlib import Path
import struct
import sys
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import change_watch as change
from je_file_tree.core import linux_watch, windows_watch
from je_file_tree.core.scanner import scan


def _notify(name="資料\\file.bin", action=3, next_offset=0):
    encoded = name.encode("utf-16-le")
    return struct.pack("<III", next_offset, action, len(encoded)) + encoded


def _usn(*, inode=55, parent=22, reason=1, major=2, usn=100, name="資料.bin"):
    encoded = name.encode("utf-16-le")
    size = -(-(60 + len(encoded)) // 8) * 8
    row = windows_watch._USN.pack(size, major, 0, inode, parent, usn, 0, reason, 0, 0, 0, len(encoded), 60)
    return struct.pack("<q", usn + size) + row + encoded + bytes(size - 60 - len(encoded))


def test_captured_scope_is_physical_complete_and_retains_shared_parent_identity(tmp_path):
    source = tmp_path / "owned"
    source.mkdir()
    (source / "branch").mkdir()
    (source / "branch" / "file").write_bytes(b"kept")
    os.link(source / "branch" / "file", source / "alias")
    root = scan(source).root
    scope = change.captured_scope(root, threading.Event())
    assert scope.folders[0].path == str(source) and len(scope.folders) == 2
    assert len(scope.shared) == 1 and set(scope.shared[0].parents) == {str(source), str(source / "branch")}
    assert scope.shared[0].inode == (source / "alias").stat().st_ino
    root.error = "owned incomplete branch"
    with pytest.raises(ValueError, match="complete scan"):
        change.captured_scope(root, threading.Event())


def test_changed_folder_and_cancellation_never_start_native_feed(tmp_path, monkeypatch):
    root = scan(tmp_path).root
    scope = change.captured_scope(root, threading.Event())
    monkeypatch.setattr(change, "stat_snapshot", lambda _path: (_ for _ in ()).throw(FileNotFoundError("moved")))
    with pytest.raises(FileNotFoundError):
        change.check_folder(scope.folders[0])
    cancel = threading.Event()
    cancel.set()
    assert not change.captured_scope(root, cancel).folders


def test_inaccessible_file_and_virtual_root_cannot_enable_monitoring(tmp_path):
    (tmp_path / "file").write_bytes(b"kept")
    root = scan(tmp_path).root
    root.children[0].error = "unreadable payload metadata"
    with pytest.raises(ValueError, match="complete scan"):
        change.captured_scope(root, threading.Event())
    root.name = ""
    with pytest.raises(ValueError, match="physical folder"):
        change.captured_scope(root, threading.Event())


def test_usn_gap_requests_full_scan_closes_handle_and_only_queries_existing_journal(monkeypatch):
    calls, batches, backends = [], [], []
    folder = change.WatchFolder("C:\\owned", 7, 22)
    kernel = SimpleNamespace(CreateFileW=lambda *_args: 42, CloseHandle=calls.append)
    replies = iter((windows_watch._JOURNAL.pack(9, 0, 100, 0, 0, 4096, 1024),
                    windows_watch._JOURNAL.pack(9, 101, 110, 101, 0, 4096, 1024)))

    def control(_kernel, _handle, code, _data=b""):
        calls.append(code)
        return next(replies)

    monkeypatch.setattr(windows_watch, "_control", control)
    monkeypatch.setattr(windows_watch, "_volume", lambda _path: ("C:\\", "{owned}"))
    monkeypatch.setattr(windows_watch, "check_folder", lambda _folder: None)
    windows_watch._watch_usn(kernel, (folder,), batches.append, threading.Event(), backends.append, ())
    assert backends == ["usn"] and batches == [change.ChangeBatch(full=True, reason="journal_changed")]
    assert calls == [windows_watch._QUERY_USN, windows_watch._QUERY_USN, 42]


def test_initial_usn_denial_falls_back_without_triggering_repeated_full_rescans(monkeypatch):
    batches, backends = [], []

    def denied(*_args):
        raise PermissionError("owned denied journal")

    def fallback(_kernel, _folders, _changed, _cancel, ready):
        ready("directory_changes")

    monkeypatch.setattr(windows_watch, "_apis", object)
    monkeypatch.setattr(windows_watch, "_watch_usn", denied)
    monkeypatch.setattr(windows_watch, "_watch_notifications", fallback)
    folders = (change.WatchFolder("C:\\owned", 7, 22),)
    windows_watch.watch_windows(folders, batches.append, threading.Event(), backends.append)
    assert not batches and backends == ["directory_changes"]
    monkeypatch.setattr(windows_watch, "_volume", lambda _path: ("C:\\", "{owned}"))
    shared = (change.WatchFile("C:\\owned\\file", 7, 55, ("C:\\owned",)),)
    with pytest.raises(ValueError, match="External hard-link"):
        windows_watch.watch_windows(folders, batches.append, threading.Event(), backends.append, shared)
    assert not batches and backends == ["directory_changes"]


def test_windows_notification_parents_are_known_and_new_descendants_use_known_ancestor():
    root = "C:\\owned"
    scopes = {root, root + "\\資料"}
    assert windows_watch.parse_notifications(_notify(), root, scopes).folders == (root + "\\資料",)
    assert windows_watch.parse_notifications(_notify("new\\deep\\file"), root, scopes).folders == (root,)
    assert windows_watch.parse_notifications(b"", root, scopes).full


@pytest.mark.parametrize("name", ["..\\escape", "C:\\foreign", "\\foreign", "x\\..\\foreign", "a\0b"])
def test_windows_event_names_cannot_become_foreign_targets(name):
    with pytest.raises(ValueError, match="Unsafe"):
        windows_watch.parse_notifications(_notify(name), "C:\\owned", {"C:\\owned"})


@pytest.mark.parametrize("payload", [b"bad", _notify(action=9), _notify(next_offset=1), _notify()[:-1]])
def test_windows_malformed_records_are_not_partial_success(payload):
    with pytest.raises(ValueError):
        windows_watch.parse_notifications(payload, "C:\\owned", {"C:\\owned"})


def test_usn_uses_captured_ids_and_external_shared_alias_changes_refresh_known_parents():
    root = "C:\\owned"
    cursor, batch = windows_watch.parse_usn(_usn(), {22: root + "\\資料"}, root, 100)
    assert cursor > 100 and batch.folders == (root + "\\資料",)
    _, outside = windows_watch.parse_usn(_usn(parent=99), {22: root}, root, 100)
    assert not outside.folders and not outside.full
    _, shared = windows_watch.parse_usn(_usn(parent=99), {22: root}, root, 100, {55: (root,)})
    assert shared.folders == (root,)
    _, aliases = windows_watch.parse_usn(_usn(reason=0x10000), {22: root}, root, 100)
    assert aliases.full and aliases.reason == "hard_links_changed"


@pytest.mark.parametrize("payload", [b"bad", _usn(major=3), _usn(usn=90), _usn()[:-1], _usn(name="..")])
def test_corrupt_unsupported_or_old_usn_records_refuse_incremental_updates(payload):
    with pytest.raises(ValueError):
        windows_watch.parse_usn(payload, {22: "C:\\owned"}, "C:\\owned", 100)


def test_inotify_shared_inode_events_and_scope_loss():
    folders = {1: ("/owned",), 2: ("/owned/a", "/owned/b")}
    payload = struct.pack("iIII", 2, 2, 0, 0)
    assert linux_watch.parse_inotify(payload, folders).folders == ("/owned/a", "/owned/b")
    assert linux_watch.parse_inotify(struct.pack("iIII", -1, 0x4000, 0, 0), folders).full
    assert linux_watch.parse_inotify(struct.pack("iIII", 1, 0x8000, 0, 0), folders).full
    with pytest.raises(ValueError):
        linux_watch.parse_inotify(payload[:-1], folders)
    assert change.changed({str(number) for number in range(change.MAX_CHANGED + 1)}).full


def test_overlapped_buffer_is_copied_after_completion_and_kernel_io_is_joined(monkeypatch):
    payload, calls, buffers = _notify("file"), [], []

    def read(_handle, buffer, *_args):
        buffers.append(buffer)
        calls.append("read")
        return 1

    def complete(*_args):
        buffers[0][:len(payload)] = payload
        calls.append("complete")
        return len(payload)

    kernel = SimpleNamespace(ResetEvent=lambda _event: None, ReadDirectoryChangesW=read,
                             CancelIoEx=lambda *_args: calls.append("cancel"),
                             GetOverlappedResult=lambda *_args: calls.append("joined") or 1)
    monkeypatch.setattr(windows_watch, "_completion", complete)
    result = windows_watch._notification(kernel, 1, windows_watch._Overlapped(), threading.Event(),
                                         lambda: calls.append("armed"))
    assert result == payload and calls == ["read", "armed", "complete", "cancel", "joined"]


@pytest.mark.skipif(not (sys.platform == "win32" or sys.platform.startswith("linux")), reason="native feed platform")
def test_native_owned_change_is_reported_and_cancellation_joins_without_source_mutation(tmp_path):
    source = tmp_path / "source"
    (source / "branch").mkdir(parents=True)
    (source / "kept").write_bytes(b"unchanged")
    root = scan(source).root
    _native_change(root, source / "branch", source / "branch" / "new", tmp_path)
    assert (source / "kept").read_bytes() == b"unchanged"


def _native_change(root, expected: Path, target: Path, scratch: Path):
    cancel, ready, arrived = threading.Event(), threading.Event(), threading.Event()
    errors, backends, batches = [], [], []

    def changed(batch):
        batches.append(batch)
        if str(expected) in batch.folders or batch.full:
            arrived.set()

    def initialized(backend):
        backends.append(backend)
        ready.set()

    def run():
        try:
            change.watch(root, changed, cancel, ready=initialized)
        except (OSError, ValueError) as error:
            errors.append(str(error))
            ready.set()

    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert ready.wait(10) and not errors, errors
        assert backends
        with target.open("wb") as stream:
            stream.write(b"owned event bytes")
            stream.flush()
            os.fsync(stream.fileno())
        assert arrived.wait(10) and not errors, (batches, errors)
        assert target.resolve().is_relative_to(scratch.resolve())
        assert target.read_bytes() == b"owned event bytes"
    finally:
        cancel.set()
        worker.join(10)
        assert not worker.is_alive(), "native feed did not join"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="native Linux external-alias feed")
def test_native_external_hard_link_write_refreshes_captured_source_parent(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "file").write_bytes(b"owned shared bytes")
    external = tmp_path / "outside-alias"
    os.link(source / "file", external)
    _native_change(scan(source).root, source, external, tmp_path)
    assert (source / "file").read_bytes() == b"owned event bytes"
