"""Separate once-per-observed-hard-link accounting from actual named file lengths/allocation."""

from __future__ import annotations

import os
import stat
import threading
from collections import defaultdict
from dataclasses import dataclass

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import Snapshot, unpack_snapshot

_ZERO = (0, 0)


@dataclass(frozen=True, slots=True)
class HardLinkAccounting:
    """Observed alias reductions; missing/inconsistent identities never imply duplicate data."""

    aliases: int
    logical_overcount: int
    allocation_overcount: int
    unknown: int


def account_hard_links(root: Node, *, cancel: threading.Event | None = None) -> HardLinkAccounting | None:
    """Assign deterministic once-per-identity totals using recorded stat only; no payload/OS query.

    The lexically first observed path contributes bytes, other proven names contribute zero only to
    accounting. Node.size/allocated/file_count/snapshots remain unchanged. Unknown or inconsistent
    hard-link groups retain named totals. Groups outside the observed tree are never assumed present;
    shared extents and directory metadata remain unknown. Reapply after changing this captured tree.
    Canceled surveys leave existing accounting untouched. Run whole-tree work on a worker thread.
    """
    survey = _survey(root, cancel)
    if survey is None:
        return None
    folders, groups, unknown = survey
    duplicate_ids: set[int] = set()
    logical = allocated = 0
    for group in groups.values():
        if cancel is not None and cancel.is_set():
            return None
        signatures = {(info.size, info.modified_ns, info.changed_ns, info.attributes,
                       node.size, node.allocated) for node, info in group}
        if len(signatures) != 1:
            unknown += len(group)
            continue
        ordered = sorted((node for node, _info in group), key=lambda node: (os.path.normcase(node.path), node.path))
        for node in ordered[1:]:
            duplicate_ids.add(id(node))
            logical += node.size
            allocated += node.allocated
    if cancel is not None and cancel.is_set():
        return None
    for node in root.iter_files():
        node.accounting = _ZERO if id(node) in duplicate_ids else None
    for folder in reversed(folders):
        size = sum(child.accounted_size for child in folder.children)
        allocation = sum(child.accounted_allocated for child in folder.children)
        folder.accounting = (size, allocation) if (size, allocation) != (folder.size, folder.allocated) else None
    return HardLinkAccounting(len(duplicate_ids), logical, allocated, unknown)


def _survey(root: Node, cancel: threading.Event | None) -> tuple[
        list[Node], dict[tuple[int, int], list[tuple[Node, Snapshot]]], int] | None:
    folders: list[Node] = []
    groups: dict[tuple[int, int], list[tuple[Node, Snapshot]]] = defaultdict(list)
    unknown = 0
    for node in root.iter_nodes():
        if cancel is not None and cancel.is_set():
            return None
        if node.is_dir:
            folders.append(node)
            give_way()
        elif not node.is_link:
            if node.snapshot is None or node.error:
                unknown += 1
                continue
            info = unpack_snapshot(node.snapshot)
            if not stat.S_ISREG(info.mode):
                continue
            if not info.inode or not info.links:
                unknown += 1
            elif info.links > 1:
                groups[info.identity].append((node, info))
    return folders, groups, unknown
