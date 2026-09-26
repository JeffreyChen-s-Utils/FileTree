"""Comparing a scan with one saved earlier."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from je_file_tree.core import export
from je_file_tree.core.compare import SavedScanError, compare, folder_key, load_saved
from je_file_tree.core.formatting import format_change
from je_file_tree.core.scanner import scan


def _saved(tmp_path: Path, folder: Path) -> Path:
    target = tmp_path / "before.json"
    export.export_json(scan(folder).root, target)
    return target


def test_a_saved_scan_reads_back(sample_tree: Path, tmp_path: Path) -> None:
    saved = load_saved(_saved(tmp_path, sample_tree))
    assert saved.root == str(sample_tree)
    assert saved.saved[:2] == "20", "when it was saved, as an ISO date"
    assert saved.size == 1000
    assert {folder.path for folder in saved.folders.values()} == {"", "photos", "code", "code/empty"}


def test_growth_new_and_gone_folders(sample_tree: Path, tmp_path: Path) -> None:
    saved = load_saved(_saved(tmp_path, sample_tree))
    (sample_tree / "photos" / "c.jpg").write_bytes(b"j" * 300)
    (sample_tree / "music").mkdir()
    (sample_tree / "music" / "song.mp3").write_bytes(b"m" * 700)
    shutil.rmtree(sample_tree / "code" / "empty")
    (sample_tree / "notes.txt").unlink()
    changes = compare(scan(sample_tree).root, saved)
    summary = [(change.path, change.before, change.after) for change in changes]
    assert summary == [
        ("", 1000, 1900),         # +900
        ("music", None, 700),      # new
        ("photos", 250, 550),      # +300
        ("code/empty", 0, None),   # gone
    ]
    assert [change.change for change in changes] == [900, 700, 300, 0]
    assert changes[1].node is not None and changes[1].node.name == "music"
    assert changes[3].node is None


def test_nothing_changed_lists_nothing(sample_tree: Path, tmp_path: Path) -> None:
    saved = load_saved(_saved(tmp_path, sample_tree))
    assert compare(scan(sample_tree).root, saved) == []


def test_folder_keys_ignore_the_separator_and_trailing_slashes() -> None:
    assert folder_key("a\\b/") == folder_key("a/b") == folder_key("/a/b")


@pytest.mark.parametrize(("content", "reason"), [
    ("not json", "Expecting value"),
    (json.dumps({"format": "other", "root": {}}), "not a FileTree scan"),
    (json.dumps({"format": "file-tree/1"}), "no root folder"),
    (json.dumps({"format": "file-tree/1", "root": {"name": "C:\\x", "size": "big"}}), "no valid size"),
    (json.dumps({"format": "file-tree/1", "root": {"name": "C:\\x", "size": True}}), "no valid size"),
    (json.dumps({"format": "file-tree/1", "root": {"name": "C:\\x", "size": -1}}), "no valid size"),
    (json.dumps({"format": "file-tree/1", "root": {"name": "C:\\x", "size": 1, "children": {}}}), "invalid children"),
    (json.dumps({"format": "file-tree/1", "root": {"name": "C:\\x", "size": 1, "children": [{"size": 1}]}}),
     "without a name"),
])
def test_what_is_not_a_saved_scan_is_refused_with_the_reason(tmp_path: Path, content: str, reason: str) -> None:
    target = tmp_path / "scan.json"
    target.write_text(content, encoding="utf-8")
    with pytest.raises(SavedScanError, match=reason):
        load_saved(target)


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SavedScanError):
        load_saved(tmp_path / "missing.json")


def test_format_change_shows_the_sign() -> None:
    assert (format_change(1536), format_change(-1536), format_change(0)) == ("+1.5 KB", "−1.5 KB", "0 B")
