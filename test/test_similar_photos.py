"""Difference hashes produce review candidates, never exact-duplicate proofs or file mutations."""

from __future__ import annotations

import hashlib
import os
import threading
import random

import pytest
from PIL import Image

from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.similar_photos import PhotoSearchCancelledError, PhotoSignature, group_similar
from je_file_tree.photo_reader import find_similar_photos


def _photos(tmp_path):
    image = Image.new("RGB", (180, 120))
    pixels = image.load()
    for y in range(120):
        for x in range(180):
            pixels[x, y] = ((x * 7 + y * 3) % 256, x % 256, y % 256)
    image.save(tmp_path / "original.png")
    image.resize((90, 60)).save(tmp_path / "resized.jpg", quality=85)
    image.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(tmp_path / "different.png")
    return scan(tmp_path).root


def test_real_resize_reencode_thumbnails_and_source_preservation(tmp_path):
    root = _photos(tmp_path)
    before = {p.name: hashlib.sha256(p.read_bytes()).digest() for p in tmp_path.iterdir()}
    result = find_similar_photos(root, min_size=1, distance=4)
    assert result.files_read == 3
    assert len(result.groups) == 1
    group = result.groups[0]
    assert {node.name for node in group.files} == {"original.png", "resized.jpg"}
    assert max(group.distances) <= 4
    assert len(result.thumbnails) == 2
    assert all(data.startswith(b"\x89PNG") for data in result.thumbnails.values())
    assert before == {p.name: hashlib.sha256(p.read_bytes()).digest() for p in tmp_path.iterdir()}
    assert root.file_count == 3


def test_groups_do_not_follow_transitive_similarity_chains():
    nodes = [Node(f"{n}.png", False, size=10) for n in range(3)]
    signatures = [PhotoSignature(node, value) for node, value in zip(nodes, (0, 3, 15), strict=True)]
    groups = group_similar(signatures, distance=2)
    assert len(groups) == 1
    assert groups[0].files == nodes[:2]
    assert groups[0].distances == [0, 2]
    with pytest.raises(ValueError):
        group_similar(signatures, distance=17)
    with pytest.raises(ValueError):
        group_similar([PhotoSignature(nodes[0], 1 << 64)])


def test_stop_changed_unsupported_and_hardlink_aliases(tmp_path):
    root = _photos(tmp_path)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(PhotoSearchCancelledError):
        find_similar_photos(root, min_size=1, cancel=cancel)
    with pytest.raises(PhotoSearchCancelledError):
        group_similar([], cancel=cancel)
    (tmp_path / "original.png").write_bytes(b"changed")
    result = find_similar_photos(root, min_size=1)
    assert result.skipped == 1
    assert result.files_read == 2
    (tmp_path / "broken.jpg").write_bytes(b"not an image")
    (tmp_path / "unsupported.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    os.link(tmp_path / "resized.jpg", tmp_path / "alias.jpg")
    root = scan(tmp_path).root
    result = find_similar_photos(root, min_size=1)
    assert result.files_read == 2
    assert result.skipped == 3


def test_input_and_pixel_caps_are_visible_without_decoding(tmp_path, monkeypatch):
    root = _photos(tmp_path)
    monkeypatch.setattr("je_file_tree.photo_reader.MAX_PIXELS", 1)
    result = find_similar_photos(root, min_size=1)
    assert (result.files_read, result.skipped, result.groups) == (0, 3, [])
    with pytest.raises(ValueError):
        find_similar_photos(root, min_size=0)


def test_index_preserves_first_representative_and_scores_across_thresholds():
    rng = random.Random(41)  # noqa: S311 - reproducible signature-index regression, not secrets
    nodes = [Node(f"{n}.png", False, size=1000 - n) for n in range(300)]
    values = [rng.getrandbits(64) for _ in range(30)]
    values += [values[rng.randrange(30)] ^ ((1 << rng.randrange(16)) - 1) for _ in range(270)]
    signatures = [PhotoSignature(node, value) for node, value in zip(nodes, values, strict=True)]
    for threshold in (0, 2, 4, 8, 16):
        anchors, files, scores = [], [], []
        for signature in signatures:
            first = next((i for i, anchor in enumerate(anchors)
                          if (signature.value ^ anchor).bit_count() <= threshold), None)
            if first is None:
                anchors.append(signature.value)
                files.append([signature.node])
                scores.append([0])
            else:
                files[first].append(signature.node)
                scores[first].append((signature.value ^ anchors[first]).bit_count())
        expected = {tuple(n.name for n in group): tuple(score)
                    for group, score in zip(files, scores, strict=True) if len(group) > 1}
        actual = {tuple(n.name for n in group.files): tuple(group.distances)
                  for group in group_similar(signatures, threshold)}
        assert actual == expected
