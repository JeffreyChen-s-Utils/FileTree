"""Confirmed compression rejects stale/outside/linked scopes and retains partial cancellation results."""

import contextlib
import dataclasses
import os
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import compression_ops as ops
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import pack_snapshot


def _native(monkeypatch):
    monkeypatch.setattr(ops, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(ops, "_compact_program", lambda: "trusted-compact")
    monkeypatch.setattr(ops, "_pinned_path", lambda _path: contextlib.nullcontext())
    monkeypatch.setattr(ops, "file_system", lambda _path: "NTFS")
    monkeypatch.setattr(ops, "protected_places", lambda: [])
    monkeypatch.setattr(ops, "system_file", lambda _path: None)


def test_exact_commands_measurements_progress_and_both_restore_modes(tmp_path, monkeypatch):
    path = tmp_path / "test.log"
    path.write_text("owned contents", encoding="utf-8")
    root = scan(tmp_path).root
    _native(monkeypatch)
    commands, progress = [], []
    monkeypatch.setattr(ops, "_run", lambda program, arguments, _stop:
                        commands.append((program, arguments)) or (0, ""))
    values = iter([4096, 1024])
    monkeypatch.setattr(ops, "file_allocation", lambda *_args: next(values))
    result = ops.compress_files(root, root.children, "uncompress", progress=lambda *args: progress.append(args))
    assert commands == [("trusted-compact", ["/u", "/i", "/q", str(path)]),
                        ("trusted-compact", ["/u", "/exe", "/i", "/q", str(path)])]
    assert result.completed == 1 and (result.before, result.after, result.unknown) == (4096, 1024, 0)
    assert progress == [(1, 1)] and not result.failures
    assert ops._arguments("xpress8k") == (("/c", "/i", "/q", "/exe:xpress8k"),)


@pytest.mark.parametrize("kind", ("changed", "detached", "hardlink", "unknown", "cloud", "protected", "scope"))
def test_rejected_files_never_launch_compact(tmp_path, monkeypatch, kind):
    path = tmp_path / "test.log"
    path.write_text("owned contents", encoding="utf-8")
    root = scan(tmp_path).root
    node = root.children[0]
    _native(monkeypatch)
    monkeypatch.setattr(ops, "_run", lambda *_args: pytest.fail("rejected file command"))
    monkeypatch.setattr(ops, "file_allocation", lambda *_args: pytest.fail("rejected allocation query"))
    if kind == "changed":
        path.write_text("changed size", encoding="utf-8")
    elif kind == "detached":
        node = scan(tmp_path).root.children[0]
    elif kind == "hardlink":
        os.link(path, tmp_path / "peer.log")
        node.snapshot = pack_snapshot(os.lstat(path))
    elif kind == "unknown":
        node.snapshot = None
    elif kind == "scope":
        monkeypatch.setattr(ops, "file_system", lambda _path: "exFAT")
    elif kind == "cloud":
        info = os.lstat(path)
        fake = SimpleNamespace(**{key: getattr(info, key) for key in
                                 ("st_mode", "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")})
        fake.st_file_attributes = 0x400000
        monkeypatch.setattr(ops, "_validate_root", lambda _root: None)
        monkeypatch.setattr(ops, "os", SimpleNamespace(path=os.path, lstat=lambda _path: fake))
    else:
        monkeypatch.setattr(ops, "protection_of", lambda *_args: object())
    result = ops.compress_files(root, [node], "ntfs")
    assert result.completed == 0 and len(result.failures) == 1 and result.unknown == 1


def test_cancel_preserves_completed_counts_and_drops_remaining_files(tmp_path, monkeypatch):
    for name in ("one.log", "two.log"):
        (tmp_path / name).write_text("owned", encoding="utf-8")
    root = scan(tmp_path).root
    _native(monkeypatch)
    event = threading.Event()
    monkeypatch.setattr(ops, "file_allocation", lambda *_args: 4096)
    def run(_program, _arguments, stop):
        stop.set()
        return 1, "partial failure"
    monkeypatch.setattr(ops, "_run", run)
    result = ops.compress_files(root, root.children, "ntfs", cancel=event)
    assert result.canceled and result.attempted == 1 and result.completed == 0
    assert (result.before, result.after) == (4096, 4096) and result.failures[0][1] == "partial failure"


def test_changed_folder_identity_is_rejected(tmp_path, monkeypatch):
    (tmp_path / "test.log").write_text("owned", encoding="utf-8")
    root = scan(tmp_path).root
    recorded = ops.unpack_snapshot(root.snapshot)
    monkeypatch.setattr(ops, "unpack_snapshot", lambda _data: dataclasses.replace(recorded, inode=recorded.inode + 1))
    with pytest.raises(ValueError, match="folder changed"):
        ops._validate_root(root)


def test_cancel_terminates_and_waits_native_command(monkeypatch):
    calls = []
    class Process:
        returncode = 1
        def poll(self):
            return None
        def terminate(self):
            calls.append("terminate")
        def wait(self, **_kwargs):
            calls.append("wait")
    monkeypatch.setattr(ops.subprocess, "Popen", lambda *_args, **kwargs:
                        calls.append(kwargs) or Process())
    monkeypatch.setattr(ops.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(ops, "_kernel", lambda: SimpleNamespace(GetOEMCP=lambda: 950))
    event = threading.Event()
    event.set()
    assert ops._run("trusted-compact", ["/c", "/i", "/q", "exact-path"], event) == (1, "")
    assert calls[-2:] == ["terminate", "wait"] and not calls[0].get("shell", False)


def test_nested_folder_scope_and_path_escape_validation(tmp_path, monkeypatch):
    scope = tmp_path / "scope"
    scope.mkdir()
    (scope / "test.log").write_text("owned", encoding="utf-8")
    whole = scan(tmp_path).root
    root = whole.children[0]
    node = root.children[0]
    assert root.parent is whole and not node.is_in(root)
    _native(monkeypatch)
    monkeypatch.setattr(ops, "file_allocation", lambda *_args: 4096)
    monkeypatch.setattr(ops, "_run", lambda *_args: (0, ""))
    assert ops.compress_files(root, [node], "ntfs").completed == 1
    node.name = str(tmp_path / "outside.log")
    assert not ops._approved(root, node)
