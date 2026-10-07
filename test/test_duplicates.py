"""Finding files with the same content."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from conftest import make_tree
from je_file_tree.core.duplicates import (
    HEAD_BYTES,
    DuplicateProgress,
    DuplicateSearchCancelledError,
    find_duplicates,
)
from je_file_tree.core.scanner import scan

LONG = bytes(range(256)) * 400  # 102,400 bytes: more than the head that is compared first


@pytest.fixture
def copies(tmp_path: Path) -> Path:
    """Two copies of a long file, one file that differs only after the head, and two copies of a short one."""
    assert len(LONG) > HEAD_BYTES
    root = tmp_path / "copies"
    root.mkdir()
    make_tree(root, {
        "a.bin": LONG,
        "backup": {"a-copy.bin": LONG},
        "tail-differs.bin": LONG[:-1] + b"\x00",
        "note.txt": b"hello world",
        "note-copy.txt": b"hello world",
        "note-other.txt": b"hello there",
        "empty-1": b"",
        "empty-2": b"",
    })
    return root


def _names(group) -> list[str]:
    return sorted(node.name for node in group.files)


def test_same_size_then_same_head_then_same_content(copies: Path) -> None:
    result = find_duplicates(scan(copies).root, min_size=1)
    assert [_names(group) for group in result.groups] == [["a-copy.bin", "a.bin"], ["note-copy.txt", "note.txt"]]
    assert [group.extra for group in result.groups] == [len(LONG), 11]
    assert result.extra == len(LONG) + 11
    assert result.skipped == 0
    # heads of 3 long + 3 short files, then the whole of the 3 long ones whose heads matched
    assert result.files_read == 9
    assert result.bytes_read == 3 * HEAD_BYTES + 3 * 11 + 3 * len(LONG)


def test_small_files_are_left_out_below_the_minimum(copies: Path) -> None:
    root = scan(copies).root
    assert find_duplicates(root).groups == [], "nothing here reaches the default 1 MB"
    only_long = find_duplicates(root, min_size=1000)
    assert [_names(group) for group in only_long.groups] == [["a-copy.bin", "a.bin"]]


def test_a_hard_link_is_the_same_file_not_a_copy(copies: Path) -> None:
    os.link(copies / "a.bin", copies / "a-link.bin")
    result = find_duplicates(scan(copies).root, min_size=1000)
    assert len(result.groups) == 1
    assert len(result.groups[0].files) == 2, "the link and its file count once"


def test_a_file_that_cannot_be_read_is_skipped(copies: Path) -> None:
    root = scan(copies).root
    (copies / "note-copy.txt").unlink()  # gone after the scan
    result = find_duplicates(root, min_size=1)
    assert [_names(group) for group in result.groups] == [["a-copy.bin", "a.bin"]]
    assert result.skipped == 1


def test_progress_and_stop(copies: Path) -> None:
    root = scan(copies).root
    seen: list[DuplicateProgress] = []
    result = find_duplicates(root, min_size=1, workers=1, progress=seen.append)
    assert [progress.files_read for progress in seen] == list(range(1, result.files_read + 1))
    assert seen[-1].bytes_read == seen[-1].bytes_total == result.bytes_read
    stopped = threading.Event()
    stopped.set()
    with pytest.raises(DuplicateSearchCancelledError):
        find_duplicates(root, min_size=1, cancel=stopped)


def test_a_file_changing_during_hashing_is_skipped(tmp_path, monkeypatch) -> None:
    from je_file_tree.core.duplicates import _Reader

    make_tree(tmp_path, {"first": LONG, "second": LONG})
    root = scan(tmp_path).root
    original = _Reader._read_into

    def mutate_after_read(self, hasher, stream, limit):
        amount = original(self, hasher, stream, limit)
        if os.path.basename(stream.name) == "first":
            with open(stream.name, "ab") as output:
                output.write(b"change")
        return amount

    monkeypatch.setattr(_Reader, "_read_into", mutate_after_read)
    result = find_duplicates(root, min_size=1)
    assert result.groups == [] and result.skipped == 1
