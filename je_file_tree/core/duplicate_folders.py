"""Recognize matching folder trees from verified duplicate-file hashes without reading contents."""

from __future__ import annotations

import hashlib
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

if TYPE_CHECKING:
    from je_file_tree.core.duplicates import DuplicateGroup


@dataclass(frozen=True, slots=True)
class DuplicateFolderGroup:
    """Nonempty folder trees with the same relative names, sizes, hashes and empty-folder structure."""

    folders: list[Node]
    size: int
    files: int


def find_duplicate_folders(root: Node, groups: list[DuplicateGroup], *,
                           cancel: threading.Event | None = None) -> list[DuplicateFolderGroup] | None:
    """Build bottom-up signatures only where every nonempty file already has a verified full hash.

    No filesystem reads occur. Links, errors and unverified files invalidate their ancestors. Empty
    files have a known empty-content hash, but wholly empty folder trees are not listed. Results
    describe the search snapshot and are read-only comparisons, never authorization to remove folders.
    """
    hashes = {node: group.digest for group in groups if group.digest is not None for node in group.files}
    folders: list[Node] = []
    for node in root.iter_nodes():
        if cancel is not None and cancel.is_set():
            return None
        if node.is_dir:
            give_way()
            folders.append(node)
    signatures: dict[Node, bytes | None] = {}
    matches: dict[bytes, list[Node]] = defaultdict(list)
    for folder in reversed(folders):
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        signature = _signature(folder, signatures, hashes)
        signatures[folder] = signature
        if signature is not None and folder is not root and folder.file_count > 0:
            matches[signature].append(folder)
    candidates = [sorted(same, key=lambda node: (node.depth, node.path)) for same in matches.values() if len(same) > 1]
    candidates.sort(key=lambda same: (-same[0].size, same[0].depth, same[0].path))
    return _outer_matches(candidates)


def _signature(folder: Node, signatures: dict[Node, bytes | None], hashes: dict[Node, bytes | None]) -> bytes | None:
    if folder.is_link or folder.error is not None:
        return None
    digest = hashlib.blake2b(digest_size=16)
    for node in sorted(folder.children, key=lambda child: child.name):
        if node.is_link or node.error is not None:
            return None
        value = (signatures.get(node) if node.is_dir else
                 hashlib.blake2b(b"", digest_size=16).digest() if node.size == 0 else hashes.get(node))
        if value is None:
            return None
        name = node.name.encode("utf-8", errors="surrogatepass")
        digest.update(b"d" if node.is_dir else b"f")
        digest.update(len(name).to_bytes(4, "little"))
        digest.update(name)
        digest.update(node.size.to_bytes(8, "little"))
        digest.update(value)
    return digest.digest()


def _outer_matches(candidates: list[list[Node]]) -> list[DuplicateFolderGroup]:
    claimed: set[Node] = set()
    result = []
    for same in candidates:
        remaining = [folder for folder in same if not _below(folder, claimed)]
        covered = [folder for folder in same if folder not in remaining]
        if covered and remaining:
            remaining.insert(0, covered[0])  # Keep one reference for an uncovered third copy.
        if len(remaining) > 1:
            first = remaining[0]
            result.append(DuplicateFolderGroup(remaining, first.size, first.file_count))
            claimed.update(remaining)
    return result


def _below(node: Node, claimed: set[Node]) -> bool:
    above = node.parent
    while above is not None:
        if above in claimed:
            return True
        above = above.parent
    return False
