"""Recorded inventories distinguish generated data from policy-approved review targets."""

import threading

import pytest

from conftest import make_tree
from test_cleanup import age_tree
from je_file_tree.core.cleanup import RebuildableMatcher, find_cleanup
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting
from je_file_tree.core import coverage as coverage_module
from je_file_tree.core.node import Node
from je_file_tree.core.projects import projects
from je_file_tree.core.scanner import ScanOptions, scan


@pytest.fixture
def project_tree(tmp_path):
    make_tree(tmp_path, {
        "專案": {"pyproject.toml": b"project", "main.py": b"source",
                 ".git": {"objects": {"object": b"git" * 10}},
                 ".venv": {"pyvenv.cfg": b"python", "lib": {"package.json": b"external"}},
                 "conda-env": {"conda-meta": {"package.json": b"meta"}, "runtime": b"conda"},
                 "environment.yml": b"env",
                 "nested": {"Cargo.toml": b"rust", "src.rs": b"source",
                            "target": {"binary": b"rust output"}}},
        "jvm": {"build.gradle": b"jvm", ".gradle": {"caches": {"data": b"gradle"}}},
        ".m2": {"repository": {"private-library": b"valuable"}},
        ".gradle": {"caches": {"custom": b"valuable"}},
        "standalone-env": {"pyvenv.cfg": b"python", "lib": {"package.json": b"external"}},
        "standalone-conda": {"conda-meta": {"package.json": b"meta"}},
        "AppData": {"Local": {"Docker": {"disk.vhdx": b"database"}}},
        "notes": {"target": {"goals.txt": b"keep"}, "venv": {"custom": b"keep"}},
    })
    age_tree(tmp_path)
    return scan(tmp_path).root


def _rows(root, **options):
    result = projects(root, **options)
    assert result is not None
    return {row.node.name: row for row in result.rows}


def test_shared_evidence_breakdown_and_nested_rows(project_tree, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("project survey must not access the filesystem")
    monkeypatch.setattr("os.stat", forbidden)
    monkeypatch.setattr("os.scandir", forbidden)
    rows = _rows(project_tree)
    assert len(rows) == 8
    project = rows["專案"]
    assert project.kinds == ("conda", "git", "python") and project.git == 30
    assert project.generated == sum(node.size for node in project.reviewable.nodes)
    assert {node.name for node in project.reviewable.nodes} == {".venv", "conda-env", "target"}
    assert project.git + project.generated + project.other == project.node.size
    assert rows["nested"].generated < project.generated
    assert rows["jvm"].reviewable.nodes[0].name == ".gradle"
    for name in (".m2", ".gradle", "Docker", "standalone-env", "standalone-conda"):
        assert not rows[name].reviewable.nodes and rows[name].generated == 0
    assert "lib" not in rows and "notes" not in rows


def test_policy_age_and_stopped_scan_never_change_inventory(project_tree):
    baseline = _rows(project_tree)["專案"]
    disabled = CleanupPolicy((RuleSetting("build_output", False, 7),))
    for options in ({"policy": disabled}, {"partial": True}, {"policy": CleanupPolicy(exclusions=(".venv", "target",
                                                                                              "conda-env"))}):
        row = _rows(project_tree, **options)["專案"]
        assert row.generated == baseline.generated and not row.reviewable.nodes
    assert _rows(project_tree, partial=True)["專案"].incomplete
    venv = next(node for node in project_tree.iter_nodes() if node.name == ".venv")
    venv.modified = 4_000_000_000
    future = _rows(project_tree)["專案"]
    assert venv not in future.reviewable.nodes and future.generated == baseline.generated


def test_unreadable_generated_branch_is_incomplete_and_not_proposed(tmp_path):
    make_tree(tmp_path, {"project": {"package.json": b"{}", "node_modules": {"unread": {"secret": b"x"}}}})
    age_tree(tmp_path)
    root = scan(tmp_path, options=ScanOptions(exclude=("unread",))).root
    row = _rows(root)["project"]
    assert row.incomplete and not row.reviewable.nodes


def test_manifest_and_environment_evidence_cannot_be_directories_or_links(tmp_path):
    make_tree(tmp_path, {"false": {"pyproject.toml": {}, ".venv": {"pyvenv.cfg": b"x"}},
                         "wrong": {"pyproject.toml": b"x", ".venv": {"pyvenv.cfg": {}}}})
    age_tree(tmp_path)
    root = scan(tmp_path).root
    rows = _rows(root)
    assert "false" not in rows
    assert not rows["wrong"].generated
    false = next(node for node in root.children if node.name == "false")
    false.children[0].is_link = True
    assert not RebuildableMatcher().matches(next(child for child in false.children if child.name == ".venv"))
    assert not any(group.key == "build_output" for group in find_cleanup(root))


def test_equal_sizes_are_bounded_and_deep_paths_do_not_recurse():
    root = Node("/recorded", True, children=[])
    parent = root
    for _ in range(1200):
        child = Node("level", True, parent=parent, children=[])
        parent.children.append(child)
        parent = child
    for number in range(8):
        child = Node(str(number), True, size=2, parent=parent, children=[])
        child.children.append(Node("package.json", False, size=2, parent=child))
        parent.children.append(child)
    result = projects(root, limit=3)
    assert result.count == 8 and len(result.rows) == 3
    with pytest.raises(ValueError, match="positive"):
        projects(root, limit=0)


def test_cancellation_includes_coverage_inventory(project_tree, monkeypatch):
    cancel = threading.Event()
    calls = []
    def stop():
        calls.append(True)
        cancel.set()
    monkeypatch.setattr(coverage_module, "give_way", stop)
    assert projects(project_tree, cancel=cancel) is None
    assert len(calls) == 1


def test_review_entries_are_bounded_without_losing_total_count():
    root = Node("/recorded", True, size=1002, modified=1_600_000_000, children=[])
    root.children.append(Node("package.json", False, parent=root))
    for number in range(1002):
        project = Node(str(number), True, size=1, modified=1_600_000_000, parent=root, children=[])
        manifest = Node("Cargo.toml", False, parent=project)
        target = Node("target", True, size=1, modified=1_600_000_000, parent=project, children=[])
        target.children.append(Node("output", False, size=1, parent=target))
        project.children.extend((manifest, target))
        root.children.append(project)
    result = projects(root, limit=1)
    assert result.count == 1003
    assert result.rows[0].node is root
    assert result.rows[0].reviewable.count == 1002 and len(result.rows[0].reviewable.nodes) == 1000
