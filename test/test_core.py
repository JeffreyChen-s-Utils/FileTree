"""Nodes, analysis, formatting and export."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import pytest

from je_file_tree.core import export
from je_file_tree.core.analysis import (
    AGES,
    CATEGORIES,
    AgeStat,
    ExtensionStat,
    age_of,
    age_stats,
    category_of,
    category_stats,
    extension_of,
    extension_stats,
    largest_files,
    largest_matching,
    subtract_ages,
    subtract_stats,
    summarise,
)
from je_file_tree.core.formatting import format_count, format_share, format_size, format_time
from je_file_tree.core.node import Node, outermost
from je_file_tree.core.scanner import scan


def test_json_export_handles_folders_deeper_than_python_recursion_limit(tmp_path: Path) -> None:
    root = Node("root", True, children=[])
    parent = root
    depth = sys.getrecursionlimit() + 10
    for _ in range(depth):
        child = Node("nested", True, children=[], parent=parent)
        parent.children.append(child)
        parent = child
    target = tmp_path / "deep.json"
    export.export_json(root, target)
    text = target.read_text(encoding="utf-8")
    assert text.count('"name": "nested"') == depth
    assert text.count('"children"') == depth


def test_streaming_export_keeps_old_file_if_iteration_fails(tmp_path: Path) -> None:
    target = tmp_path / "files.csv"
    target.write_text("previous", encoding="utf-8")

    def failing_files():
        yield Node("first", False, size=1)
        raise OSError("source changed")

    with pytest.raises(OSError, match="source changed"):
        export.export_files_csv(failing_files(), target)
    assert target.read_text(encoding="utf-8") == "previous"
    assert not list(tmp_path.glob(".file-tree-*"))


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


def test_is_in_follows_the_parents_up_to_the_root(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    photos = _child(root, "photos")
    picture = _child(photos, "a.jpg")
    assert root.is_in(root)
    assert photos.is_in(root)
    assert picture.is_in(root)
    assert not root.is_in(photos)
    photos.detach()
    assert not photos.is_in(root)
    assert not picture.is_in(root), "a detached branch is out, with everything in it"
    assert picture.is_in(photos)


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


def test_outermost_keeps_each_entry_once_and_leaves_out_those_inside_another(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    photos = _child(root, "photos")
    picture = _child(photos, "a.jpg")
    big = _child(root, "big.bin")
    assert outermost([picture, big, photos, picture, big]) == [big, photos]
    assert outermost([picture, root]) == [root]
    assert outermost([]) == []


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
    assert rows[1][:6] == [str(sample_tree), "1000", str(root.allocated), "1.0", "6", "3"]
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
    assert top["allocated"] == root.allocated
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


# --- ages -----------------------------------------------------------------

_DAY = 86400.0


def test_age_groups() -> None:
    now = 1_800_000_000.0
    assert [age_of(now - days * _DAY, now) for days in (0, 30, 31, 182, 200, 365, 400, 730, 731)] == [
        "month", "month", "half_year", "half_year", "year", "year", "two_years", "two_years", "older"]
    assert age_of(now + 5 * _DAY, now) == "month", "a clock set ahead is not older"
    assert age_of(0.0, now) == "older", "no time at all goes to the oldest group"


def test_age_stats_keep_every_group_in_order_and_subtract(sample_tree: Path) -> None:
    now = 2_000_000_000.0
    for name, days in (("big.bin", 3), ("notes.txt", 100), ("photos/a.jpg", 1000)):
        stamp = now - days * _DAY
        os.utime(sample_tree / name, (stamp, stamp))
    root = scan(sample_tree).root
    stats = summarise(root, now=now).ages
    assert [stat.age for stat in stats] == list(AGES)
    by_age = {stat.age: (stat.size, stat.count) for stat in stats}
    assert by_age["month"][0] >= 500 and by_age["half_year"] == (100, 1)
    assert sum(stat.count for stat in stats) == 6
    photos = _child(root, "photos")
    removed = age_stats(list(photos.iter_files()), now)
    photos.detach()
    assert subtract_ages(stats, removed) == age_stats(list(root.iter_files()), now)
    assert AgeStat("month", 1, 1) != AgeStat("month", 1, 2)


def test_largest_matching(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    pictures = largest_matching(root, lambda node: node.name.endswith((".jpg", ".png")), 5)
    assert [node.name for node in pictures] == ["a.jpg", "b.png"]
    assert largest_matching(root, lambda node: False, 5) == []


def test_replace_with_swaps_a_rescanned_folder_in_and_corrects_the_totals(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    (sample_tree / "photos" / "c.gif").write_bytes(b"g" * 300)
    (sample_tree / "photos" / "b.png").unlink()
    (sample_tree / "photos" / "raw").mkdir()
    old = _child(root, "photos")
    fresh = scan(sample_tree / "photos").root
    old.replace_with(fresh)
    photos = _child(root, "photos")
    assert photos is fresh and photos.parent is root and photos.name == "photos"
    assert photos.path == str(sample_tree / "photos")
    assert old.parent is None
    assert (root.size, root.file_count, root.dir_count) == (1250, 6, 4)
    assert root.size == sum(child.size for child in root.children)
    root.replace_with(fresh)  # the root has no parent: nothing happens
    assert root.size == 1250
