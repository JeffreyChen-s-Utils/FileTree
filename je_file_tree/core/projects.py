"""Recorded project/source/generated inventories using the same conservative clean-up evidence."""

from __future__ import annotations

import heapq
import threading
from dataclasses import dataclass, field
from pathlib import PurePath

from je_file_tree.core.cleanup import RebuildableMatcher, find_cleanup
from je_file_tree.core.cleanup_policy import CleanupPolicy
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

_MANIFESTS = {"pyproject.toml": "python", "setup.py": "python", "requirements.txt": "python",
              "package.json": "node", "cargo.toml": "rust", "pom.xml": "jvm", "build.gradle": "jvm",
              "build.gradle.kts": "jvm", "environment.yml": "conda", "environment.yaml": "conda"}
_MARKERS = {"pyvenv.cfg": "python_environment", "conda-meta": "conda_environment"}
_REVIEW_LIMIT = 1000
_MARKER_NAMES = set(_MANIFESTS) | set(_MARKERS) | {".git", "repository", "caches"}


@dataclass(frozen=True, slots=True)
class ReviewEntries:
    """At most 1,000 policy-eligible entries per row, with the complete eligible count."""

    nodes: tuple[Node, ...]
    count: int


@dataclass(frozen=True, slots=True)
class Project:
    """One project or managed store; nested projects overlap and are never summed globally."""

    node: Node
    kinds: tuple[str, ...]
    git: int
    generated: int
    other: int
    reviewable: ReviewEntries
    incomplete: bool


@dataclass(frozen=True, slots=True)
class Projects:
    """The bounded largest project/store rows and the full recognized count."""

    rows: list[Project]
    count: int


@dataclass(slots=True)
class _Account:
    node: Node
    kinds: tuple[str, ...]
    sequence: int
    git: int = 0
    generated: int = 0
    reviewable: list[Node] = field(default_factory=list)
    review_count: int = 0
    incomplete: bool = False


def _kinds(node: Node) -> tuple[str, ...]:
    children = {child.name.casefold(): child for child in node.children
                if child.name.casefold() in _MARKER_NAMES and not child.is_link and not child.error}
    kinds = {_MANIFESTS[name] for name, child in children.items() if name in _MANIFESTS and not child.is_dir}
    kinds.update(_MARKERS[name] for name, child in children.items()
                 if name in _MARKERS and child.is_dir == (name == "conda-meta"))
    if ".git" in children:
        kinds.add("git")
    if not kinds:
        name = node.name.casefold()
        if name == ".m2" and "repository" in children and children["repository"].is_dir:
            kinds.add("maven_store")
        if name == ".gradle" and "caches" in children and children["caches"].is_dir:
            kinds.add("gradle_store")
        if name == "docker":
            parts = tuple(part.casefold() for part in PurePath(node.path).parts)
            if parts[-3:] in (("appdata", "local", "docker"), (".local", "share", "docker")) \
                    or parts[-4:] == ("/", "var", "lib", "docker"):
                kinds.add("docker_store")
    return tuple(sorted(kinds))


def _retain(account: _Account, parent: _Account | None, heap: list, limit: int) -> None:
    row = Project(account.node, account.kinds, account.git, account.generated,
                  max(0, account.node.size - account.git - account.generated),
                  ReviewEntries(tuple(account.reviewable), account.review_count), account.incomplete)
    item = (account.node.size, account.sequence, row)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item[:2] > heap[0][:2]:
        heapq.heapreplace(heap, item)
    if parent is not None:
        parent.git += account.git
        parent.generated += account.generated
        parent.review_count += account.review_count
        parent.reviewable.extend(account.reviewable[:_REVIEW_LIMIT - len(parent.reviewable)])
        parent.incomplete |= account.incomplete


def _generated(owner: _Account, node: Node, eligible: set[Node]) -> None:
    owner.generated += node.size
    if node in eligible:
        owner.review_count += 1
        if len(owner.reviewable) < _REVIEW_LIMIT:
            owner.reviewable.append(node)


def projects(root: Node, *, policy: CleanupPolicy | None = None, partial: bool = False, limit: int = 1000,
             cancel: threading.Event | None = None) -> Projects | None:
    """Survey recorded nodes without filesystem reads, skipping generated/store internals.

    Only aged, policy-eligible rebuildable clean-up nodes become reviewable. Standalone environments,
    unscoped Gradle/Maven stores and Docker data are never presumed disposable. Nested rows overlap.
    ``other`` includes source and unclassified data, not a claim that every byte is source code.
    """
    if limit < 1:
        raise ValueError("Project row limit must be positive")
    coverage = coverage_of(root, cancel=cancel)
    if coverage is None:
        return None
    groups = find_cleanup(root, policy=policy, cancel=cancel, coverage=coverage)
    if groups is None:
        return None
    eligible = {node for group in groups if group.details.rebuildable for node in group.nodes} if not partial else set()
    matcher = RebuildableMatcher()
    heap, count, stack = [], 0, [(root, None, None, False)]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        node, owner, previous, finishing = stack.pop()
        if finishing:
            _retain(owner, previous, heap, limit)
            continue
        if not node.is_dir or node.is_link:
            continue
        give_way()
        if owner is not None:
            owner.incomplete |= node in coverage.unsafe
            if node.name.casefold() == ".git":
                owner.git += node.size
                continue
            if matcher.matches(node):
                _generated(owner, node, eligible)
                continue
        kinds = _kinds(node)
        if kinds:
            count += 1
            account = _Account(node, kinds, count, incomplete=partial or node in coverage.unsafe)
            account.git = sum(child.size for child in node.children if child.name.casefold() == ".git"
                               and not child.is_dir and not child.is_link and not child.error)
            stack.append((node, account, owner, True))
            owner = account
            if any(kind.endswith("_store") or kind.endswith("_environment") for kind in kinds):
                continue
        stack.extend((child, owner, None, False) for child in node.children if child.is_dir and not child.is_link)
    return Projects([item[2] for item in sorted(heap, reverse=True)], count)
