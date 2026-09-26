"""Finding entries by name anywhere in a scanned tree."""

from __future__ import annotations

import threading
from pathlib import Path

from je_file_tree.core.scanner import scan
from je_file_tree.core.search import Query, SearchResult, name_matcher, search


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


def test_conditions_on_size_age_type_and_kind(sample_tree: Path) -> None:
    # big.bin 500, notes.txt 100, photos/{a.jpg 200, b.png 50}, code/{main.py 100, Makefile 50, empty/}
    root = scan(sample_tree).root
    for node in root.iter_nodes():
        node.modified = 1_000_000.0  # every entry last changed at the same time
    by_name = {node.name: node for node in root.iter_nodes()}
    by_name["a.jpg"].modified = 1_990_000.0  # changed recently
    now = 2_000_000.0

    def names(**conditions: object) -> list[str]:
        return sorted(_names(search(root, Query(**conditions), now=now)))  # type: ignore[arg-type]

    assert names(min_size=200) == ["a.jpg", "big.bin", "photos"]
    assert names(min_size=100, max_size=200) == ["a.jpg", "code", "main.py", "notes.txt"]
    assert names(min_size=100, kind="files") == ["a.jpg", "big.bin", "main.py", "notes.txt"]
    assert names(kind="folders") == ["code", "empty", "photos"]
    assert names(category="images") == ["a.jpg", "b.png"]
    assert names(changed_within=100_000.0) == ["a.jpg"]
    assert "a.jpg" not in names(unchanged_for=100_000.0)
    assert names(text="*.p*", min_size=60) == ["main.py"], "the name and the size together"
    assert search(root, Query(), now=now) == SearchResult([], 0, 0), "no condition finds nothing"


def test_a_name_alone_is_the_same_as_a_plain_string(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert _names(search(root, Query(text="*.jpg"))) == _names(search(root, "*.jpg")) == ["a.jpg"]
