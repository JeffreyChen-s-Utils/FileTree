"""Live folder comparison is explicit about coverage, casing and content verification."""

import csv
import os
import threading

import pytest

from je_file_tree.core.live_compare import Difference, compare_folders, export_comparison, verify_pair
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core import live_compare


def _pair(tmp_path, one=b"abc", two=b"xyz"):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for folder, payload in ((left, one), (right, two)):
        target = folder / "檔案 with space.txt"
        target.write_bytes(payload)
        os.utime(target, ns=(1000000000, 1000000000))
    a, b = scan(left).root, scan(right).root
    return compare_folders(a, b).rows[0]


def test_equal_size_and_time_are_unchecked_until_requested(tmp_path):
    row = _pair(tmp_path)
    assert row.state == "unchecked"
    assert verify_pair(row).state == "different_bytes"


def test_matching_bytes_and_a_changed_scanned_file(tmp_path):
    row = _pair(tmp_path, b"same", b"same")
    assert verify_pair(row).state == "identical"
    with open(row.left.path, "wb") as stream:
        stream.write(b"changed")
    assert verify_pair(row).state == "unavailable"


def test_change_between_the_two_hashes_cannot_claim_identity(tmp_path, monkeypatch):
    row = _pair(tmp_path, b"same", b"same")
    original = live_compare.hash_unchanged
    def change_after_read(node, **kwargs):
        digest = original(node, **kwargs)
        if node is row.right:
            with open(row.left.path, "wb") as stream:
                stream.write(b"changed")
        return digest
    monkeypatch.setattr(live_compare, "hash_unchanged", change_after_read)
    assert verify_pair(row).state == "unavailable"


def test_exact_unicode_and_case_names_and_unknown_missing_paths():
    left, right = Node("left", True), Node("right", True)
    left.children = [Node("Photo.JPG", False, parent=left), Node("資料", True, parent=left)]
    right.children = [Node("photo.jpg", False, parent=right), Node("資料", True, error="access denied", parent=right)]
    left.children[1].children = [Node("test.txt", False, parent=left.children[1])]
    rows = {row.relative: row.state for row in compare_folders(left, right).rows}
    assert rows == {"Photo.JPG": "only_left", "photo.jpg": "only_right",
                    "資料": "unavailable", "資料/test.txt": "unavailable"}
    assert compare_folders(left, right).incomplete


def test_links_permissions_and_cancel_do_not_read_contents(tmp_path, monkeypatch):
    row = _pair(tmp_path)
    monkeypatch.setattr(live_compare, "hash_unchanged", lambda *_args, **_kwargs: pytest.fail("must not read"))
    row.left.is_link = True
    assert verify_pair(row) is row
    row.left.is_link = False
    row.right.error = "access denied"
    assert verify_pair(row) is row
    cancel = threading.Event()
    cancel.set()
    assert compare_folders(Node("left", True), Node("right", True), cancel=cancel) is None


def test_bounded_rows_and_formula_safe_atomic_export(tmp_path):
    left, right = Node("left", True), Node("right", True)
    left.children = [Node(f"{index}.txt", False, parent=left) for index in range(12)]
    result = compare_folders(left, right, limit=3)
    assert result.count == 12 and len(result.rows) == 3
    row = Difference("=1+1.txt", left.children[0], None, "only_left")
    target = tmp_path / "comparison.csv"
    assert export_comparison([row], str(target)) == 1
    with target.open(encoding="utf-8-sig", newline="") as stream:
        values = list(csv.reader(stream))
    assert values[1][0] == "'=1+1.txt"
    assert values[1][2] == row.left.path
    assert not list(tmp_path.glob(".file-tree-*.tmp"))
    with pytest.raises(ValueError, match="positive"):
        compare_folders(left, right, limit=0)


def test_case_and_deep_paths_never_recurse():
    left, right = Node("left", True), Node("right", True)
    parent = left
    for _ in range(1200):
        child = Node("資料", True, parent=parent)
        parent.children = [child]
        parent = child
    result = compare_folders(left, right, limit=2)
    assert result.count == 1200 and len(result.rows) == 2
