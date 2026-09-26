"""Finding entries by name anywhere in a scanned tree."""

from __future__ import annotations

import threading
from pathlib import Path

from je_file_tree.core.scanner import scan
from je_file_tree.core.search import SearchResult, name_matcher, search


def _names(result: SearchResult | None) -> list[str]:
    assert result is not None
    return [node.name for node in result.matches]


def test_plain_text_matches_anywhere_in_a_name_and_case_never_matters(sample_tree: Path) -> None:
    result = search(scan(sample_tree).root, "MAKE")
    assert _names(result) == ["Makefile"]
    assert result is not None and (result.count, result.size) == (1, 50)


def test_a_pattern_matches_whole_names_and_several_are_separated_by_semicolons(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert _names(search(root, "*.jpg; *.png")) == ["a.jpg", "b.png"]
    assert _names(search(root, "?.jpg")) == ["a.jpg"]
    assert _names(search(root, "*.jp")) == [], "a pattern must match the whole name"
    assert _names(search(root, "(")) == [], "plain text is taken literally"


def test_folders_match_too_and_what_is_inside_a_match_counts_once(sample_tree: Path) -> None:
    root = scan(sample_tree).root  # the root, "sample", is never a match of its own search
    result = search(root, "p")
    assert sorted(_names(result)) == ["a.jpg", "b.png", "empty", "main.py", "photos"]
    assert result is not None and (result.count, result.size) == (5, 350)


def test_only_the_largest_are_listed_but_all_are_counted(sample_tree: Path) -> None:
    result = search(scan(sample_tree).root, "*", limit=2)
    assert _names(result) == ["big.bin", "photos"]
    assert result is not None and (result.count, result.size) == (9, 1000)


def test_nothing_to_look_for_and_a_stopped_search(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert name_matcher(" ; ") is None
    assert search(root, " ") == SearchResult([], 0, 0)
    stopped = threading.Event()
    stopped.set()
    assert search(root, "*", cancel=stopped) is None
