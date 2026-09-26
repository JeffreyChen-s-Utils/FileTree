"""The scanner: totals, order, links, unreadable folders, hidden files, progress and cancelling."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from je_file_tree.core import scanner
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanCancelledError, ScanOptions, ScanProgress, scan


def _child(node: Node, name: str) -> Node:
    return next(child for child in node.children if child.name == name)


@pytest.mark.parametrize("workers", [1, 4])
def test_totals_add_up(sample_tree: Path, workers: int) -> None:
    result = scan(sample_tree, options=ScanOptions(workers=workers))
    root = result.root
    assert (root.size, root.file_count, root.dir_count) == (1000, 6, 3)
    code = _child(root, "code")
    assert (code.size, code.file_count, code.dir_count) == (150, 2, 1)
    assert _child(code, "empty").size == 0
    assert result.errors == []


def test_the_root_keeps_its_full_path_and_children_rebuild_theirs(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert root.name == str(sample_tree)
    assert _child(_child(root, "photos"), "a.jpg").path == str(sample_tree / "photos" / "a.jpg")


def test_children_are_sorted_largest_first_then_by_name(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert [child.name for child in root.children] == ["big.bin", "photos", "code", "notes.txt"]
    code = _child(root, "code")
    assert [child.name for child in code.children] == ["main.py", "Makefile", "empty"]


def test_a_folder_takes_the_newest_time_beneath_it(sample_tree: Path) -> None:
    os.utime(sample_tree / "photos" / "a.jpg", (2_000_000_000, 2_000_000_000))
    root = scan(sample_tree).root
    assert _child(root, "photos").modified == 2_000_000_000
    assert root.modified == 2_000_000_000


def test_scanning_a_file_or_a_missing_path_raises(tmp_path: Path) -> None:
    file = tmp_path / "file.txt"
    file.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        scan(file)
    with pytest.raises(NotADirectoryError):
        scan(tmp_path / "missing")


def test_an_unreadable_folder_is_recorded_and_the_scan_goes_on(sample_tree: Path,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    locked = str(sample_tree / "photos")
    real_scandir = os.scandir

    def scandir(path: str):
        if path == locked:
            raise PermissionError(13, "存取被拒。")  # the OS words it in the system's language
        return real_scandir(path)

    monkeypatch.setattr(scanner.os, "scandir", scandir)
    result = scan(sample_tree)
    assert result.errors == [(locked, scanner.ACCESS_DENIED)]
    photos = _child(result.root, "photos")
    assert photos.error == scanner.ACCESS_DENIED
    assert (photos.size, result.root.size, result.root.file_count) == (0, 750, 4)


def test_hidden_entries_can_be_left_out(sample_tree: Path) -> None:
    (sample_tree / ".cache").mkdir()
    (sample_tree / ".cache" / "blob").write_bytes(b"h" * 300)
    everything = scan(sample_tree).root
    visible = scan(sample_tree, options=ScanOptions(include_hidden=False)).root
    assert everything.size == 1300
    assert visible.size == 1000
    assert all(child.name != ".cache" for child in visible.children)


def _make_symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as error:  # Windows without developer mode or admin rights
        pytest.skip(f"cannot create symlinks here: {error}")


def test_a_symlinked_folder_is_listed_but_not_followed(sample_tree: Path) -> None:
    _make_symlink(sample_tree / "loop", sample_tree)
    root = scan(sample_tree).root
    loop = _child(root, "loop")
    assert loop.is_link and loop.is_dir
    assert (loop.size, loop.children, root.size) == (0, (), 1000)


@pytest.mark.skipif(sys.platform != "win32", reason="junctions exist on Windows only")
def test_a_junction_is_listed_but_not_followed(sample_tree: Path) -> None:
    import _winapi  # noqa: PLC0415 - Windows-only module

    _winapi.CreateJunction(str(sample_tree), str(sample_tree / "junction"))
    root = scan(sample_tree).root
    junction = _child(root, "junction")
    assert junction.is_link
    assert root.size == 1000


def test_progress_is_reported_from_the_calling_thread_and_ends_with_the_totals(sample_tree: Path) -> None:
    calls: list[tuple[ScanProgress, threading.Thread]] = []
    scan(sample_tree, progress=lambda update: calls.append((update, threading.current_thread())),
         progress_interval=0.001)
    assert calls
    assert {thread for _, thread in calls} == {threading.current_thread()}
    last = calls[-1][0]
    assert (last.files, last.folders, last.size) == (6, 3, 1000)


def test_setting_cancel_stops_the_scan(sample_tree: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ScanCancelledError) as stopped:
        scan(sample_tree, cancel=cancel, progress_interval=0.001)
    partial = stopped.value.partial
    assert partial is not None
    assert partial.root.error == scanner.NOT_SCANNED
    assert (partial.root.size, partial.root.children) == (0, [])


def _slow_reads(monkeypatch: pytest.MonkeyPatch, delay: float) -> None:
    real = scanner._read_folder

    def slow(*args: object):
        time.sleep(delay)
        return real(*args)

    monkeypatch.setattr(scanner, "_read_folder", slow)


def test_a_stopped_scan_hands_back_what_it_read(sample_tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _slow_reads(monkeypatch, 0.05)
    cancel = threading.Event()
    with pytest.raises(ScanCancelledError) as stopped:
        scan(sample_tree, options=ScanOptions(workers=1), cancel=cancel, progress_interval=0.01,
             progress=lambda _update: cancel.set())
    root = stopped.value.partial.root
    assert root.error is None, "the root was read before the stop"
    assert root.size == sum(child.size for child in root.children)
    assert [child.name for child in root.children][0] == "big.bin", "children are sorted like a finished scan"
    unread = [node for node in root.iter_nodes() if node.error == scanner.NOT_SCANNED]
    assert unread and all(node.is_dir and node.size == 0 for node in unread)


def test_totals_grow_while_the_scan_runs(sample_tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _slow_reads(monkeypatch, 0.02)
    roots: list[Node] = []
    seen: list[tuple[int, int, int]] = []

    def watch(_update: ScanProgress) -> None:
        root = roots[0]
        seen.append((root.size, root.file_count, root.dir_count))

    result = scan(sample_tree, options=ScanOptions(workers=1), progress=watch, progress_interval=0.005,
                  on_root=roots.append)
    assert roots == [result.root]
    assert seen[0] < seen[-1] == (1000, 6, 3)
    assert seen == sorted(seen), "running totals only ever grow"


def test_an_unexpected_error_in_a_worker_reaches_the_caller(sample_tree: Path,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_args: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(scanner, "_read_folder", broken)
    with pytest.raises(RuntimeError, match="boom"):
        scan(sample_tree)


def test_a_deep_tree_does_not_hit_the_recursion_limit(tmp_path: Path) -> None:
    folder = tmp_path
    for _ in range(40):
        folder = folder / "d"
    folder.mkdir(parents=True)
    (folder / "leaf.txt").write_bytes(b"x" * 7)
    root = scan(tmp_path / "d").root
    assert (root.size, root.dir_count) == (7, 39)
