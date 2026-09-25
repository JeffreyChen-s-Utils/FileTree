"""Nodes, analysis, formatting and export."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

from file_tree.core import export
from file_tree.core.analysis import (
    CATEGORIES,
    ExtensionStat,
    category_of,
    category_stats,
    extension_of,
    extension_stats,
    largest_files,
    subtract_stats,
)
from file_tree.core.formatting import format_count, format_share, format_size, format_time
from file_tree.core.node import Node
from file_tree.core.scanner import scan


def _child(node: Node, name: str) -> Node:
    return next(child for child in node.children if child.name == name)


# --- Node -----------------------------------------------------------------


def test_share_of_parent_and_depth(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    photos = _child(root, "photos")
    assert root.share_of_parent() == 1.0
    assert photos.share_of_parent() == pytest.approx(0.25)
    assert (root.depth, photos.depth, _child(photos, "a.jpg").depth) == (0, 1, 2)
    assert Node("x", True, parent=Node("p", True)).share_of_parent() == 0.0


def test_iter_files_skips_folders_and_links(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    root.children.append(Node("link", False, is_link=True, parent=root))
    assert sorted(node.name for node in root.iter_files()) == [
        "Makefile", "a.jpg", "b.png", "big.bin", "main.py", "notes.txt"]


def test_detach_subtracts_from_every_folder_above(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    code = _child(root, "code")
    code.detach()
    assert code.parent is None
    assert code not in root.children
    assert (root.size, root.file_count, root.dir_count) == (850, 4, 1)
    photo = _child(_child(root, "photos"), "b.png")
    photo.detach()
    assert (root.size, root.file_count, _child(root, "photos").size) == (800, 3, 200)
    root.detach()  # the root has no parent: nothing happens
    assert root.size == 800


# --- analysis -------------------------------------------------------------


def test_extension_of_and_category_of() -> None:
    assert extension_of("Photo.JPG") == ".jpg"
    assert extension_of("archive.tar.gz") == ".gz"
    assert extension_of("Makefile") == ""
    assert extension_of(".bashrc") == ""
    assert extension_of("trailing.") == ""
    assert category_of(".jpg") == "images"
    assert category_of(".unknown") == "other"
    assert category_of("") == "other"


def test_largest_files(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert [node.name for node in largest_files(root, 2)] == ["big.bin", "a.jpg"]
    assert [node.size for node in largest_files(root, 10)] == [500, 200, 100, 100, 50, 50]
    assert largest_files(root, 0) == []


def test_extension_and_category_stats(sample_tree: Path) -> None:
    stats = extension_stats(scan(sample_tree).root)
    assert stats[0] == ExtensionStat(".bin", "other", 500, 1)
    assert {stat.extension for stat in stats} == {".bin", ".jpg", ".txt", ".py", ".png", ""}
    categories = {stat.category: (stat.size, stat.count) for stat in category_stats(stats)}
    assert categories == {"other": (550, 2), "images": (250, 2), "documents": (100, 1), "code": (100, 1)}
    assert set(categories) <= set(CATEGORIES)


def test_subtract_stats_after_a_deletion(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    photos = _child(root, "photos")
    remaining = subtract_stats(extension_stats(root), extension_stats(photos))
    photos.detach()
    assert remaining == extension_stats(root)


# --- formatting -----------------------------------------------------------


@pytest.mark.parametrize(("size", "unit", "text"), [
    (0, "auto", "0 B"),
    (1023, "auto", "1,023 B"),
    (1024, "auto", "1.0 KB"),
    (1536 * 1024, "auto", "1.5 MB"),
    (5 * 1024 ** 4, "auto", "5.0 TB"),
    (1024 ** 3, "MB", "1,024.0 MB"),
    (512, "KB", "0.5 KB"),
])
def test_format_size(size: int, unit: str, text: str) -> None:
    assert format_size(size, unit) == text


def test_format_size_rejects_an_unknown_unit() -> None:
    with pytest.raises(ValueError, match="unknown size unit"):
        format_size(1, "XB")


def test_format_count_share_and_time() -> None:
    assert format_count(1234567) == "1,234,567"
    assert format_share(0.4251) == "42.5 %"
    assert format_time(0) == ""
    assert len(format_time(1_700_000_000)) == len("2023-11-14 22:13")


# --- export ---------------------------------------------------------------


def _read_csv(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "CSV must start with a BOM so Excel reads it as UTF-8"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.reader(stream))


def test_export_folders_csv(sample_tree: Path, tmp_path: Path) -> None:
    root = scan(sample_tree).root
    target = tmp_path / "folders.csv"
    assert export.export_folders_csv(root, target) == 4
    rows = _read_csv(target)
    assert rows[0] == list(export.FOLDER_COLUMNS)
    assert rows[1][:5] == [str(sample_tree), "1000", "1.0", "6", "3"]
    assert [row[0] for row in rows[1:]] == [str(sample_tree), str(sample_tree / "photos"),
                                            str(sample_tree / "code"), str(sample_tree / "code" / "empty")]
    assert export.export_folders_csv(root, target, max_depth=0) == 1


def test_export_files_csv_keeps_the_given_order(sample_tree: Path, tmp_path: Path) -> None:
    root = scan(sample_tree).root
    target = tmp_path / "files.csv"
    assert export.export_files_csv(largest_files(root, 2), target) == 2
    rows = _read_csv(target)
    assert [row[:2] for row in rows[1:]] == [[str(sample_tree / "big.bin"), "500"],
                                             [str(sample_tree / "photos" / "a.jpg"), "200"]]


def test_export_json(sample_tree: Path, tmp_path: Path) -> None:
    root = scan(sample_tree).root
    target = tmp_path / "tree.json"
    export.export_json(root, target)
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["format"] == "file-tree/1"
    top = document["root"]
    assert (top["name"], top["size"], top["files"], top["folders"]) == (str(sample_tree), 1000, 6, 3)
    assert [child["name"] for child in top["children"]] == ["photos", "code"]
    assert top["children"][1]["children"][0]["name"] == "empty"
    export.export_json(root, target, max_depth=0)
    assert "children" not in json.loads(target.read_text(encoding="utf-8"))["root"]


def test_a_failed_export_leaves_no_temporary_file(sample_tree: Path, tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    root = scan(sample_tree).root
    out = tmp_path / "out"
    out.mkdir()

    def refuse(*_args: object) -> None:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(export.os, "replace", refuse)
    with pytest.raises(PermissionError):
        export.export_json(root, out / "tree.json")
    assert os.listdir(out) == []
