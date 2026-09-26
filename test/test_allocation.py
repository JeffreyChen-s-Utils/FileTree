"""Size on disk: the platform rules, and the totals the scan keeps."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from je_file_tree.core import allocation
from je_file_tree.core.allocation import allocation_for, blocks_allocation, windows_allocation
from je_file_tree.core.scanner import scan

ENTRY = SimpleNamespace(path="C:\\x\\file")


def _windows(size: int, attributes: int = 0) -> SimpleNamespace:
    return SimpleNamespace(st_size=size, st_file_attributes=attributes)


def test_windows_rounds_ordinary_files_up_to_whole_clusters() -> None:
    allocated = windows_allocation(4096)
    assert [allocated(ENTRY, _windows(size)) for size in (0, 1, 4096, 4097)] == [0, 4096, 4096, 8192]
    assert allocated(ENTRY, _windows(10 * 2**30 + 1)) == 10 * 2**30 + 4096
    assert allocated(ENTRY, _windows(1)) is allocated(ENTRY, _windows(4000)), "small sizes share one int"


def test_windows_counts_files_kept_elsewhere_as_nothing_without_opening_them(monkeypatch: pytest.MonkeyPatch) -> None:
    def never(_path: str) -> int:
        raise AssertionError("a file whose data is elsewhere must not be opened")

    monkeypatch.setattr(allocation, "compressed_size", never)
    allocated = windows_allocation(4096)
    for attributes in (0x1000, 0x40000, 0x400000, 0x400000 | 0x200):  # offline, recall on open / on data access
        assert allocated(ENTRY, _windows(5_000_000, attributes)) == 0


def test_windows_asks_the_system_only_for_compressed_and_sparse_files(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    monkeypatch.setattr(allocation, "compressed_size", lambda path: asked.append(path) or 1234)
    allocated = windows_allocation(4096)
    assert allocated(ENTRY, _windows(9000, 0x800)) == 1234
    assert allocated(ENTRY, _windows(9000, 0x200)) == 1234
    assert allocated(ENTRY, _windows(9000)) == 12288
    assert asked == [ENTRY.path, ENTRY.path]
    monkeypatch.setattr(allocation, "compressed_size", lambda _path: None)
    assert allocated(ENTRY, _windows(9000, 0x800)) == 12288, "rounded when the system cannot say"


def test_posix_counts_512_byte_blocks() -> None:
    allocated = blocks_allocation()
    assert allocated(ENTRY, SimpleNamespace(st_blocks=8)) == 4096
    assert allocated(ENTRY, SimpleNamespace(st_blocks=10**6)) == 512 * 10**6


def test_the_scan_stores_and_adds_up_the_space_on_disk(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    rule = allocation_for(str(sample_tree))
    expected = {}
    for top, _folders, names in os.walk(sample_tree):
        with os.scandir(top) as entries:
            expected.update({entry.path: rule(entry, entry.stat(follow_symlinks=False))
                             for entry in entries if entry.name in names})
    assert {node.path: node.allocated for node in root.iter_files()} == expected
    assert root.allocated == sum(expected.values()) >= root.size
    code = next(child for child in root.children if child.name == "code")
    before = root.allocated
    code.detach()
    assert root.allocated == before - code.allocated


@pytest.mark.skipif(sys.platform != "win32", reason="Windows system calls")
def test_the_windows_calls_answer(tmp_path: Path) -> None:
    cluster = allocation.cluster_size(str(tmp_path))
    assert cluster >= 512 and cluster & (cluster - 1) == 0
    target = tmp_path / "plain.bin"
    target.write_bytes(b"x" * 5000)
    assert allocation.compressed_size(str(target)) == 5000, "an ordinary file: its size"
    assert allocation.compressed_size(str(tmp_path / "missing")) is None
