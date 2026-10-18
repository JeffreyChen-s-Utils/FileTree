"""Duplicate members keep the exact (modified, path) order with paths built only for ties (U-20261017-77)."""

import random

import pytest

from je_file_tree.core.node import Node
from je_file_tree.gui.duplicates_panel import oldest_first


def _tree(root_name):
    root = Node(root_name, True, children=[])
    folders = [root]
    for name in ("a", "a b", "a\u00e9", "b", "資料夾"):
        parent = random.choice(folders)  # noqa: S311 - test data shape
        folder = Node(name, True, children=[], parent=parent)
        parent.children.append(folder)
        folders.append(folder)
    files = []
    for _ in range(200):
        parent = random.choice(folders)  # noqa: S311
        name = random.choice(["copy.bin", "Copy.bin", "copy (2).bin", "z.bin", "檔案.bin"])  # noqa: S311
        node = Node(name, False, modified=random.choice([1.0, 2.0, 2.0, 3.5]), parent=parent)  # noqa: S311
        parent.children.append(node)
        files.append(node)
    return files


@pytest.mark.parametrize("root_name", ["C:\\owned", "/owned", ""])
@pytest.mark.parametrize("seed", range(5))
def test_order_matches_the_modified_then_path_key(root_name, seed):
    random.seed(seed)
    files = _tree(root_name)
    random.shuffle(files)
    expected = sorted(files, key=lambda file: (file.modified, file.path or ""))
    assert oldest_first(files) == expected
    assert [id(node) for node in oldest_first(files)] == [id(node) for node in expected]


def test_unique_times_never_build_paths(monkeypatch):
    files = [Node(f"f{number}", False, modified=float(number)) for number in range(5)]
    monkeypatch.setattr(Node, "path", property(lambda _self: pytest.fail("Built a path without a tie")))
    assert oldest_first(list(reversed(files))) == files
