"""Read-only relative-path comparisons; metadata equality never proves matching contents."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from collections.abc import Iterable
from itertools import chain

from je_file_tree.core.duplicates import hash_unchanged
from je_file_tree.core.export import export_table_csv
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import stat_snapshot


@dataclass(frozen=True, slots=True)
class Difference:
    """One exact, case-sensitive relative path and its two recorded entries."""

    relative: str
    left: Node | None
    right: Node | None
    state: str


@dataclass(frozen=True, slots=True)
class FolderComparison:
    """A bounded displayed list plus the complete row count and incomplete-coverage flag."""

    rows: list[Difference]
    count: int
    incomplete: bool


def _inventory(root: Node, cancel: threading.Event | None) -> dict[str, Node] | None:
    entries, stack = {"": root}, [(root, "")]
    while stack:
        node, relative = stack.pop()
        if cancel is not None and cancel.is_set():
            return None
        if node.is_dir:
            give_way()
        if node.is_link:
            continue
        for child in node.children:
            path = relative + "/" + child.name if relative else child.name
            entries[path] = child
            stack.append((child, path))
    return entries


def _missing_is_unknown(path: str, entries: dict[str, Node]) -> bool:
    parent = path
    while True:
        node = entries.get(parent)
        if node is not None and (node.error or node.is_link):
            return True
        if not parent:
            return False
        parent = parent.rpartition("/")[0]


def _state(left: Node | None, right: Node | None) -> str:
    if any(node is not None and node.error for node in (left, right)):
        return "unavailable"
    if any(node is not None and node.is_link for node in (left, right)):
        return "link"
    if left is None or right is None:
        return "only_right" if left is None else "only_left"
    if left.is_dir != right.is_dir:
        return "different_kind"
    if left.is_dir:
        return "folder"
    return _file_state(left, right)


def _file_state(left: Node, right: Node) -> str:
    if left.size != right.size:
        return "different_size"
    return "different_time" if left.modified != right.modified else "unchecked"


def compare_folders(left: Node, right: Node, *, limit: int = 10000,
                    cancel: threading.Event | None = None) -> FolderComparison | None:
    """Compare recorded entries without reading contents; omitted/unreadable paths stay unknown.

    Names are compared exactly, including Unicode and case, independently of host filesystem casing.
    At most ``limit`` rows are retained; the full count explicitly reports any truncation.
    """
    if limit < 1:
        raise ValueError("Comparison row limit must be positive")
    one, two = _inventory(left, cancel), _inventory(right, cancel)
    if one is None or two is None:
        return None
    rows, count = [], 0
    for path in sorted((one.keys() | two.keys()) - {""}):
        if cancel is not None and cancel.is_set():
            return None
        a, b = one.get(path), two.get(path)
        state = _state(a, b)
        if (a is None and _missing_is_unknown(path, one)) or (b is None and _missing_is_unknown(path, two)):
            state = "unavailable"
        count += 1
        if len(rows) < limit:
            rows.append(Difference(path, a, b, state))
    incomplete = any(node.error for node in chain(one.values(), two.values()))
    return FolderComparison(rows, count, incomplete)


def verify_pair(row: Difference, *, cancel: threading.Event | None = None) -> Difference:
    """Hash only a requested pair; reject links, changed snapshots and inaccessible/cloud contents."""
    left, right = row.left, row.right
    if left is None or right is None or any(node.is_dir or node.is_link or node.error for node in (left, right)):
        return row
    a, b = hash_unchanged(left, cancel=cancel), hash_unchanged(right, cancel=cancel)
    try:
        unchanged = stat_snapshot(left.path) == left.snapshot and stat_snapshot(right.path) == right.snapshot
    except OSError:
        unchanged = False
    state = "unavailable" if a is None or b is None or not unchanged else "identical" if a == b else "different_bytes"
    return replace(row, state=state)


def export_comparison(rows: Iterable[Difference], target: str) -> int:
    """Atomically export retained comparison rows as formula-escaped UTF-8/BOM CSV."""
    header = ("relative_path", "state", "left_path", "right_path", "left_size", "right_size",
              "left_modified", "right_modified")
    def values(row: Difference) -> list[str]:
        return [row.relative, row.state, row.left.path if row.left else "", row.right.path if row.right else "",
                *(str(getattr(node, name)) if node else "" for name in ("size", "modified")
                  for node in (row.left, row.right))]
    return export_table_csv(header, (values(row) for row in rows), target)
