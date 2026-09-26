"""Sunburst layout: rings of arcs whose angles follow the sizes."""

from __future__ import annotations

from pathlib import Path

import pytest

from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.sunburst import layout, segment_at


def test_each_ring_shares_its_parent_s_arc_by_size(sample_tree: Path) -> None:
    root = scan(sample_tree).root  # big.bin 500, photos 250 (a.jpg 200, b.png 50), code 150, notes.txt 100
    segments = layout(root)
    first = [(segment.node.name, segment.start, segment.span) for segment in segments if segment.depth == 1]
    assert [name for name, _, _ in first] == ["big.bin", "photos", "code", "notes.txt"]
    assert [span for _, _, span in first] == pytest.approx([0.5, 0.25, 0.15, 0.1])
    assert first[1][1] == pytest.approx(0.5), "arcs follow one another clockwise"
    inside = {segment.node.name: segment for segment in segments if segment.depth == 2}
    assert inside["a.jpg"].start == pytest.approx(0.5) and inside["a.jpg"].span == pytest.approx(0.2)
    assert inside["b.png"].start == pytest.approx(0.7) and inside["b.png"].span == pytest.approx(0.05)


def test_limits_keep_the_layout_small(sample_tree: Path) -> None:
    root = scan(sample_tree).root
    assert {segment.depth for segment in layout(root, max_depth=1)} == {1}
    assert [segment.node.name for segment in layout(root, min_span=0.2)] == ["big.bin", "photos", "a.jpg"]
    assert len(layout(root, max_segments=2)) == 2
    assert layout(Node("empty", True, children=[])) == []


def test_segment_at_finds_the_arc_under_an_angle(sample_tree: Path) -> None:
    segments = layout(scan(sample_tree).root)
    hit = segment_at(segments, 1, 0.6)
    assert hit is not None and hit.node.name == "photos"
    below = segment_at(segments, 2, 0.72)
    assert below is not None and below.node.name == "b.png"
    assert segment_at(segments, 2, 0.1) is None, "big.bin is a file: nothing beneath it"
    assert segment_at(segments, 5, 0.1) is None
