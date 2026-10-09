"""Space per recorded file owner, retaining unavailable identities as an explicit separate group."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import threading

from je_file_tree.core.node import Node
from je_file_tree.core.owner_id import OwnerID, owner_identifier, owner_name
from je_file_tree.core.pacing import give_way

_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class OwnerStat:
    """One owner's named-file logical/allocation totals; hard links remain counted by name."""

    owner: OwnerID | None
    name: str
    identifier: str
    size: int
    allocated: int
    files: int
    share: float


@dataclass(frozen=True, slots=True)
class OwnerInventory:
    """Largest owner groups, complete group/file/byte totals and explicit unknown-owner counts."""

    rows: list[OwnerStat]
    count: int
    files: int
    size: int
    unknown_files: int
    unknown_size: int
    incomplete: bool


def owner_stats(root: Node, *, cancel: threading.Event | None = None) -> OwnerInventory | None:
    """Aggregate recorded entries off the GUI thread; never reread files or infer a missing owner.

    Directory ownership contributes no descendant bytes. Only non-link recorded files count;
    file ownership does not prove which account created, used or can remove data. Names can require
    an OS account lookup; cancellation is checked before/after each lookup and canceled results vanish.
    """
    totals: dict[OwnerID | None, list[int]] = {}
    files = size = unknown_files = unknown_size = 0
    incomplete = False
    for node in root.iter_nodes():
        if cancel is not None and cancel.is_set():
            return None
        if node.is_dir:
            give_way()
        incomplete |= bool(node.error)
        if node.is_dir or node.is_link:
            continue
        row = totals.setdefault(node.owner, [0, 0, 0])
        row[0] += node.size
        row[1] += node.allocated
        row[2] += 1
        files += 1
        size += node.size
        if node.owner is None:
            unknown_files += 1
            unknown_size += node.size
    largest = heapq.nlargest(_LIMIT, totals.items(), key=lambda pair: pair[1][0])
    rows = []
    for owner, (logical, allocated, count) in largest:
        if cancel is not None and cancel.is_set():
            return None
        rows.append(OwnerStat(owner, owner_name(owner), owner_identifier(owner), logical, allocated, count,
                              logical / size if size else 0.0))
    if cancel is not None and cancel.is_set():
        return None
    return OwnerInventory(rows, len(totals), files, size, unknown_files, unknown_size, incomplete)
