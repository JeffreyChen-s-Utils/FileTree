"""Folder matches require every relative file hash and do not read contents again."""

import threading

from conftest import make_tree
from je_file_tree.core.duplicate_folders import find_duplicate_folders
from je_file_tree.core.duplicates import find_duplicates
from je_file_tree.core.scanner import ScanOptions, scan


def test_matching_unicode_trees_include_empty_structure_and_no_extra_reads(tmp_path, monkeypatch) -> None:
    spec = {"照片.jpg": b"picture", "nested": {"data.bin": b"data", "empty": {}}, "zero": b""}
    make_tree(tmp_path, {"original": spec, "copy": spec})
    root = scan(tmp_path).root
    result = find_duplicates(root, min_size=1)
    assert [[folder.name for folder in group.folders] for group in result.folders] == [["copy", "original"]]
    assert result.folders[0].files == 3 and result.folders[0].size == 11

    def no_read(*args, **kwargs):
        raise AssertionError("folder matching must reuse verified hashes")

    monkeypatch.setattr("builtins.open", no_read)
    assert find_duplicate_folders(root, result.groups) == result.folders


def test_different_names_sizes_unhashed_files_and_empty_structure_do_not_match(tmp_path) -> None:
    make_tree(tmp_path, {
        "base": {"a": b"abc", "empty": {}},
        "different_name": {"b": b"abc", "empty": {}},
        "different_size": {"a": b"abcd", "empty": {}},
        "different_structure": {"a": b"abc"},
        "unhashed": {"a": b"abc", "unique": b"only here", "empty": {}},
        "empty_tree1": {"empty": {}}, "empty_tree2": {"empty": {}},
    })
    root = scan(tmp_path).root
    assert find_duplicates(root, min_size=1).folders == []
    assert find_duplicates(root, min_size=1000).folders == []


def test_excluded_and_link_branches_invalidate_their_ancestors(tmp_path) -> None:
    make_tree(tmp_path, {"one": {"a": b"same", "skipped": {"private": b"x"}},
                         "two": {"a": b"same", "skipped": {"private": b"x"}}})
    root = scan(tmp_path, options=ScanOptions(exclude=("skipped",))).root
    result = find_duplicates(root, min_size=1)
    assert result.folders == []
    for folder in root.children:
        next(node for node in folder.children if node.name == "skipped").is_link = True
    assert find_duplicate_folders(root, result.groups) == []


def test_nested_pair_is_suppressed_but_an_uncovered_third_copy_is_shown(tmp_path) -> None:
    spec = {"outer.txt": b"outer", "nested": {"data": b"inside"}}
    make_tree(tmp_path, {"one": spec, "two": spec, "third": {"data": b"inside"}})
    result = find_duplicates(scan(tmp_path).root, min_size=1)
    assert len(result.folders) == 2
    names = [[folder.name for folder in group.folders] for group in result.folders]
    assert names[0] == ["one", "two"] and set(names[1]) == {"nested", "third"}


def test_folder_walk_cancels_without_emitting_partial_matches(tmp_path) -> None:
    cancel = threading.Event()
    cancel.set()
    assert find_duplicate_folders(scan(tmp_path).root, [], cancel=cancel) is None


def test_deep_folder_signatures_are_iterative() -> None:
    from je_file_tree.core.node import Node
    from je_file_tree.core.duplicates import DuplicateGroup

    root = Node("root", True, children=[])
    files = []
    for name in ("one", "two"):
        folder = Node(name, True, size=3, file_count=1, parent=root, children=[])
        root.children.append(folder)
        for _ in range(1100):
            child = Node("n", True, size=3, file_count=1, parent=folder, children=[])
            folder.children.append(child)
            folder = child
        leaf = Node("file", False, size=3, file_count=1, parent=folder)
        folder.children.append(leaf)
        files.append(leaf)
    groups = [DuplicateGroup(3, files, digest=b"known digest")]
    matches = find_duplicate_folders(root, groups)
    assert len(matches) == 1 and [folder.name for folder in matches[0].folders] == ["one", "two"]


def test_gui_places_read_only_lines_above_file_groups_and_discards_after_tree_edits(qapp, tmp_path) -> None:
    from je_file_tree.gui.duplicates_panel import DuplicatesPanel
    from test_gui import _wait

    make_tree(tmp_path, {"one": {"a": b"same"}, "two": {"a": b"same"}})
    root = scan(tmp_path).root
    panel = DuplicatesPanel()
    try:
        panel.set_root(root)
        panel._show_result(find_duplicates(root, min_size=1))
        _wait(qapp, lambda: not panel.running)
        assert panel.folder_matches.count() == 1
        assert " = " in panel.folder_matches.item(0).text()
        assert "matching search snapshot" in panel.folder_matches.item(0).text()
        assert "not a clean-up approval" in panel.folder_matches.toolTip()
        panel.prune()
        _wait(qapp, lambda: not panel.running)
        assert panel.folder_matches.count() == 0
    finally:
        panel.stop(wait=True)
        panel.close()
