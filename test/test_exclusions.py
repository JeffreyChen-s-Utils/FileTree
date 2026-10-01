"""Folders skipped while scanning: name patterns and whole paths."""

from __future__ import annotations

from pathlib import Path

from je_file_tree.core.exclusions import exclusion_test, is_path
from je_file_tree.core.scanner import EXCLUDED, ScanOptions, scan


def test_nothing_to_exclude() -> None:
    assert exclusion_test([]) is None
    assert exclusion_test(["", "  "]) is None


def test_name_patterns_match_folder_names_whatever_the_case() -> None:
    excluded = exclusion_test(["node_modules", "*.cache", "build?"])
    assert excluded is not None
    assert excluded("node_modules", "/p/node_modules")
    assert excluded("Node_Modules", "/p/Node_Modules")
    assert excluded("pip.cache", "/p/pip.cache")
    assert excluded("build2", "/p/build2")
    assert not excluded("build", "/p/build"), "? stands for exactly one character"
    assert not excluded("modules", "/p/modules")


def test_a_path_skips_that_one_folder(tmp_path: Path) -> None:
    target = tmp_path / "backup"
    excluded = exclusion_test([str(target)])
    assert excluded is not None
    assert excluded("backup", str(target))
    assert not excluded("backup", str(tmp_path / "elsewhere" / "backup")), "a path is not a name pattern"


def test_what_counts_as_a_path() -> None:
    assert is_path("C:\\Backups")
    assert is_path("/mnt/backup")
    assert is_path("photos/raw")
    assert not is_path("node_modules")
    assert not is_path("*.cache")


def test_a_skipped_folder_is_listed_but_not_read(sample_tree: Path) -> None:
    result = scan(sample_tree, options=ScanOptions(exclude=("code",)))
    root = result.root
    code = next(child for child in root.children if child.name == "code")
    assert code.error == EXCLUDED
    assert code.children == []
    assert (code.size, code.file_count) == (0, 0)
    assert (root.size, root.file_count) == (850, 4), "big.bin, notes.txt and photos only"
    assert root.dir_count == 1, "photos; the skipped folder is not counted"
    assert result.errors == [], "skipping is not a problem"


def test_the_scanned_folder_itself_is_never_skipped(sample_tree: Path) -> None:
    root = scan(sample_tree, options=ScanOptions(exclude=(sample_tree.name, str(sample_tree)))).root
    assert root.error is None
    assert root.size == 1000
