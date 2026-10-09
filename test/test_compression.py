"""Type-based compression previews do not read payloads or misclassify metadata gaps as savings."""

import stat
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import compression
from je_file_tree.core.node import Node
from je_file_tree.core.snapshot import pack_snapshot


def _node(name, *, attributes=0, mode=stat.S_IFREG, size=100):
    info = SimpleNamespace(st_mode=mode, st_dev=1, st_ino=2, st_size=size, st_mtime_ns=1,
                           st_ctime_ns=1, st_nlink=1, st_file_attributes=attributes)
    return Node(name, False, size=size, allocated=4096, snapshot=pack_snapshot(info))


def _volume(monkeypatch):
    monkeypatch.setattr(compression, "file_system", lambda _path: "NTFS")
    monkeypatch.setattr(compression, "allocation_unit", lambda _path: 4096)
    monkeypatch.setattr(compression, "sys", SimpleNamespace(platform="win32"))


def test_types_guards_unknowns_and_incomplete_allocation_bounds(monkeypatch):
    _volume(monkeypatch)
    children = [_node("a.log"), _node("b.py"), _node("c.bmp"), _node("d.jpg"), _node("e.zip"),
                _node("f.pyc"), _node("pipe.txt", mode=stat.S_IFIFO), Node("unknown.txt", False, size=10)]
    children += [_node(f"guard{flag}.txt", attributes=flag) for flag in
                 (0x2, 0x4, 0x200, 0x400, 0x800, 0x1000, 0x40000, 0x400000)]
    children += [Node("link.txt", False, is_link=True), Node("denied", True, error="denied")]
    root = Node("root", True, children=children)
    result = compression.compression_plan(root)
    assert result.ntfs and result.unit == 4096 and result.count == 3
    assert result.logical == 300 and result.allocated == 12288 and result.unknown_files == 1
    assert result.total_files == 16 and result.incomplete
    assert {node.name for node in result.rows} == {"a.log", "b.py", "c.bmp"}


def test_capped_rows_preserve_full_counts_and_cancel_drops_results(monkeypatch):
    _volume(monkeypatch)
    root = Node("root", True, children=[_node(f"file{number}.txt", size=number) for number in range(1002)])
    result = compression.compression_plan(root)
    assert len(result.rows) == 1000 and result.count == 1002 and result.total_files == 1002
    assert result.logical == sum(range(1002)) and result.allocated == 4096 * 1002
    assert result.rows[0].size == 1001
    event = threading.Event()
    event.set()
    monkeypatch.setattr(compression, "file_system", lambda _path: pytest.fail("canceled native query"))
    assert compression.compression_plan(root, cancel=event) is None


def test_unknown_or_foreign_filesystem_is_not_ntfs(monkeypatch):
    monkeypatch.setattr(compression, "allocation_unit", lambda _path: None)
    for name in (None, "exFAT"):
        monkeypatch.setattr(compression, "file_system", lambda _path, value=name: value)
        result = compression.compression_plan(Node("root", True))
        assert not result.ntfs


def test_non_windows_filesystem_query_never_reaches_native_api(monkeypatch):
    monkeypatch.setattr(compression, "sys", SimpleNamespace(platform="linux"))
    assert compression.file_system("/unused") is None


def test_restore_preview_includes_compressed_and_unflagged_executable_types(monkeypatch):
    _volume(monkeypatch)
    root = Node("root", True, children=[_node("program.exe"), _node("compressed.zip", attributes=0x800),
                                       _node("cloud.exe", attributes=0x400000), _node("sparse.log", attributes=0x200)])
    assert {node.name for node in compression.compression_plan(root).rows} == {"program.exe"}
    restored = compression.compression_plan(root, include_compressed=True)
    assert {node.name for node in restored.rows} == {"program.exe", "compressed.zip"}
