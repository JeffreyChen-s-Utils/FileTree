"""Clean-up suggestions: the rules against a built tree, and empty folders."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from conftest import make_tree
from je_file_tree.core.cleanup import EMPTY_FOLDERS, Rule, empty_folders, find_cleanup
from je_file_tree.core.scanner import EXCLUDED, ScanOptions, scan

OLD = 1_600_000_000  # far more than 90 days before the tests run


@pytest.fixture
def home(tmp_path: Path) -> Path:
    root = tmp_path / "me"
    root.mkdir()
    make_tree(root, {
        "AppData": {"Local": {
            "Temp": {"setup.tmp": b"t" * 300},
            "Google": {"Chrome": {"User Data": {"Default": {"Cache": {"data_1": b"c" * 200}, "Bookmarks": b"b"}}}},
            "CrashDumps": {"app.dmp": b"d" * 50},
            "pip": {"Cache": {"wheel": b"w" * 70}},
        }},
        "Projects": {
            "site": {"package.json": b"{}", "node_modules": {"lib": {"index.js": b"j" * 40, "empty": {}}},
                     "dist": {"bundle.js": b"x" * 30}},
            "tool": {"Cargo.toml": b"", "target": {"debug": {"tool.exe": b"e" * 60}}},
            "notes": {"target": {"goals.txt": b"g" * 5}},  # no Cargo.toml or pom.xml: someone's own folder
        },
        "Downloads": {"old.msi": b"m" * 400, "new.msi": b"n" * 10, "report.pdf": b"p" * 20},
        "memory.dmp": b"d" * 25,
        "Empty": {"a": {"b": {}}, "c": {}},
        "Kept": {"x": {}, "file.txt": b"f"},
    })
    os.utime(root / "Downloads" / "old.msi", (OLD, OLD))
    return root


def _groups(root: Path) -> dict[str, list[str]]:
    result = find_cleanup(scan(root).root)
    assert result is not None
    return {group.key: sorted(node.name for node in group.nodes) for group in result}


def test_each_rule_finds_its_places(home: Path) -> None:
    groups = _groups(home)
    assert groups["temp"] == ["Temp"]
    assert groups["browser_cache"] == ["Cache"]
    assert groups["crash_dumps"] == ["CrashDumps", "memory.dmp"], "a dump folder, and a dump file anywhere"
    assert groups["package_caches"] == ["Cache"]
    assert groups["build_output"] == ["dist", "node_modules", "target"], "notes/target has no Cargo.toml"
    assert groups["old_installers"] == ["old.msi"], "new.msi was changed lately, report.pdf is no installer"
    assert groups[EMPTY_FOLDERS] == ["Empty", "x"], "the outermost empty folder; the one in node_modules is its group's"


def test_groups_come_largest_first_with_their_totals(home: Path) -> None:
    result = find_cleanup(scan(home).root)
    assert result is not None
    assert [group.size for group in result] == sorted((group.size for group in result), reverse=True)
    temp = next(group for group in result if group.key == "temp")
    assert temp.size == 300


def test_an_anchored_rule_matches_at_the_root_only(tmp_path: Path) -> None:
    make_tree(tmp_path, {"inner": {"tmp": {"x": b"x"}}})
    rules = (Rule("temp", folders=("/inner",)), Rule("other", folders=("/tmp",)))  # noqa: S108 - a pattern
    result = find_cleanup(scan(tmp_path).root, rules=rules)
    assert result is not None
    assert [group.key for group in result] == [], "/inner is not at the file-system root, nor is inner/tmp"


def test_folders_not_known_to_be_empty(tmp_path: Path) -> None:
    make_tree(tmp_path, {"skipped": {}, "plain": {}})
    root = scan(tmp_path, options=ScanOptions(exclude=("skipped",))).root
    skipped = next(child for child in root.children if child.name == "skipped")
    assert skipped.error == EXCLUDED
    assert [node.name for node in empty_folders(root)] == ["plain"], "a skipped folder was never read"
    assert empty_folders(scan(tmp_path / "plain").root) == [], "the scanned folder itself is not suggested"
