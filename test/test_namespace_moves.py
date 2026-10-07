"""Exclusive namespace operations use only owned fixtures and never overwrite arrivals."""

from pathlib import Path
import os
import threading

import pytest

from je_file_tree.core import namespace_moves as moves
from je_file_tree.core import no_replace
from je_file_tree.core.protected import PROGRAMS, Protection
from je_file_tree.core.scanner import scan


def _fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(moves, "protected_places", lambda: ())
    source, target = tmp_path.resolve() / "source", tmp_path.resolve() / "target"
    source.mkdir()
    target.mkdir()
    for name in ("one.txt", "two.txt"):
        (source / name).write_bytes(name.encode())
    root = scan(source).root
    return root, source, target


def test_native_move_and_both_parent_paths(tmp_path, monkeypatch):
    root, source, target = _fixture(tmp_path, monkeypatch)
    plan = moves.prepare_namespace(root, root.children, directory=str(target))
    assert all(not item.reason for item in plan.items)
    assert len(list(source.iterdir())) == 2 and not list(target.iterdir())
    result = moves.execute_namespace(plan)
    assert len(result.moved) == 2 and not result.failed
    assert result.parents == {str(source), str(target)}
    assert not list(source.iterdir())
    for name in ("one.txt", "two.txt"):
        assert (target / name).read_bytes() == name.encode()


def test_native_arriving_collision_never_overwrites(tmp_path, monkeypatch):
    root, source, target = _fixture(tmp_path, monkeypatch)
    plan = moves.prepare_namespace(root, [root.children[0]], directory=str(target))
    item = plan.items[0]
    native = moves.rename_no_replace

    def arrival(old, new, old_fd, new_fd):
        Path(new).write_bytes(b"arrival")
        native(old, new, old_fd, new_fd)

    monkeypatch.setattr(moves, "rename_no_replace", arrival)
    result = moves.execute_namespace(plan)
    assert len(result.failed) == 1 and not result.moved
    assert Path(item.destination).read_bytes() == b"arrival"
    assert Path(item.source).read_bytes() == Path(item.source).name.encode()


def test_explicit_collision_suffix_is_previewed_not_rechosen(tmp_path, monkeypatch):
    root, source, target = _fixture(tmp_path, monkeypatch)
    node = root.children[0]
    (target / node.name).write_bytes(b"existing")
    skipped = moves.prepare_namespace(root, [node], directory=str(target))
    assert skipped.items[0].reason == "collision"
    plan = moves.prepare_namespace(root, [node], directory=str(target), collision="rename")
    assert plan.items[0].destination.endswith(" (2).txt")
    Path(plan.items[0].destination).write_bytes(b"later")
    assert len(moves.execute_namespace(plan).failed) == 1
    assert (source / node.name).exists()


def test_literals_patterns_and_multiple_reserved_names(tmp_path, monkeypatch):
    root, source, _ = _fixture(tmp_path, monkeypatch)
    plan = moves.prepare_namespace(root, root.children, pattern="{n}-{stem}{ext}")
    assert {Path(item.destination).name for item in plan.items} == {"1-one.txt", "2-two.txt"}
    assert len(moves.execute_namespace(plan).moved) == 2
    root = scan(source).root
    plan = moves.prepare_namespace(root, root.children, pattern="same.txt")
    assert [item.reason for item in plan.items] == ["", "collision"]
    for pattern in ("../escape", "{unknown}", "", "a\0b", "x" * 256):
        bad = moves.prepare_namespace(root, root.children, pattern=pattern)
        assert all(item.reason == "error" for item in bad.items)


def test_changed_source_and_replaced_target_parent_are_refused(tmp_path, monkeypatch):
    root, source, target = _fixture(tmp_path, monkeypatch)
    plan = moves.prepare_namespace(root, root.children, directory=str(target))
    (source / root.children[0].name).write_bytes(b"changed")
    target.rename(target.with_name("old-target"))
    target.mkdir()
    result = moves.execute_namespace(plan)
    assert len(result.failed) == 2 and not result.moved
    assert not list(target.iterdir()) and len(list(source.iterdir())) == 2


def test_descendant_protected_and_nested_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(moves, "protected_places", lambda: ())
    source = tmp_path.resolve()
    folder = source / "folder"
    folder.mkdir()
    (folder / "child").write_bytes(b"data")
    root = scan(source).root
    node = root.children[0]
    plan = moves.prepare_namespace(root, [node, node.children[0]], directory=str(folder))
    assert len(plan.items) == 1 and plan.items[0].reason == "descendant"
    guarded = source / "guarded"
    guarded.mkdir()
    monkeypatch.setattr(moves, "protected_places", lambda: (Protection(str(guarded), PROGRAMS),))
    plan = moves.prepare_namespace(root, [node], directory=str(guarded))
    assert plan.items[0].reason == "protected_destination"


def test_cancel_between_items_preserves_remaining_sources(tmp_path, monkeypatch):
    root, source, target = _fixture(tmp_path, monkeypatch)
    cancel = threading.Event()
    plan = moves.prepare_namespace(root, root.children, directory=str(target))
    result = moves.execute_namespace(plan, cancel=cancel, progress=lambda _n, _total: cancel.set())
    assert result.canceled and len(result.moved) == 1
    assert len(list(source.iterdir())) == 1 and len(list(target.iterdir())) == 1
    assert moves.prepare_namespace(root, root.children, pattern="new-{name}", cancel=cancel) is None


def test_hardlink_names_and_alias_inside_other_selected_folder(tmp_path, monkeypatch):
    root, source, target = _fixture(tmp_path, monkeypatch)
    alias = source / "folder"
    alias.mkdir()
    os.link(source / "one.txt", alias / "alias.txt")
    root = scan(source).root
    nodes = sorted(root.children, key=lambda node: node.is_dir)
    plan = moves.prepare_namespace(root, nodes, directory=str(target))
    result = moves.execute_namespace(plan)
    assert len(result.moved) == 3 and not result.failed
    assert os.path.samefile(target / "one.txt", target / "folder" / "alias.txt")


def test_payload_replacement_at_syscall_boundary_is_rolled_back(tmp_path, monkeypatch):
    root, source, target = _fixture(tmp_path, monkeypatch)
    plan = moves.prepare_namespace(root, [root.children[0]], directory=str(target))
    native = moves.rename_no_replace
    calls = []

    def replace_source(old, new, old_fd, new_fd):
        if not calls:
            Path(old).rename(source / "retained-original")
            Path(old).write_bytes(b"unexpected")
        calls.append(old)
        native(old, new, old_fd, new_fd)

    monkeypatch.setattr(moves, "rename_no_replace", replace_source)
    result = moves.execute_namespace(plan)
    assert len(result.failed) == 1 and len(calls) == 2
    assert Path(plan.items[0].source).read_bytes() == b"unexpected"
    assert not Path(plan.items[0].destination).exists()
    assert (source / "retained-original").read_bytes() == root.children[0].name.encode()


def test_linked_target_and_invalid_scope_are_refused(tmp_path, monkeypatch):
    root, _, target = _fixture(tmp_path, monkeypatch)
    linked = target.with_name("linked")
    try:
        linked.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"owned symlink unavailable: {exc}")
    plan = moves.prepare_namespace(root, root.children, directory=str(linked))
    assert all(item.reason == "error" for item in plan.items)
    with pytest.raises(ValueError):
        moves.prepare_namespace(root, [], pattern="x")
    with pytest.raises(ValueError):
        moves.prepare_namespace(root, root.children, directory=str(target), pattern="x")


def test_unavailable_native_interface_has_no_unsafe_fallback(monkeypatch):
    monkeypatch.setattr(no_replace.ctypes, "CDLL", lambda *_args, **_kwargs: object())
    with pytest.raises(OSError, match="unavailable"):
        no_replace._native(1, "source", 2, "target")


def test_deep_folder_change_after_preview_preserves_source(tmp_path, monkeypatch):
    root, source, target = _fixture(tmp_path, monkeypatch)
    folder = source / "folder"
    folder.mkdir()
    (folder / "deep").write_bytes(b"before")
    root = scan(source).root
    node = next(node for node in root.children if node.is_dir)
    plan = moves.prepare_namespace(root, [node], directory=str(target))
    (folder / "deep").write_bytes(b"after")
    result = moves.execute_namespace(plan)
    assert len(result.failed) == 1 and not result.moved
    assert (folder / "deep").read_bytes() == b"after" and not (target / "folder").exists()
