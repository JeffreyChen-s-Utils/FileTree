"""Check every member of an explicit duplicate decision before offering or moving extras."""

from __future__ import annotations

import threading
import os
from collections.abc import Sequence

from je_file_tree.core.duplicates import DuplicateGroup, DuplicateSearchCancelledError, hash_unchanged
from je_file_tree.core.node import Node
from je_file_tree.core.operations import revalidate
from je_file_tree.core.protected import Protection
from je_file_tree.core.snapshot import pack_snapshot, stat_snapshot, unpack_snapshot

_MIN_COPIES = 2


def check_group(group: DuplicateGroup, root: Node, *, places: Sequence[Protection] = (),
                cancel: threading.Event | None = None, rehash: bool = False) -> str | None:
    """Return a reason if any copy is unsafe; optionally rehash the whole group before any move.

    Hard-linked copies (including names outside the scan) are conservatively left untouched. A
    missing/changed keeper invalidates the entire decision, even if only one extra was selected.
    """
    if group.kept is None or group.kept not in group.files:
        return "duplicate_choose"
    if group.digest is None or len(group.files) < _MIN_COPIES:
        return "duplicate_unverified"
    for node in group.files:
        reason = _check_copy(node, root, places, cancel, group.proofs.get(node))
        if reason is not None:
            return reason
        if rehash:
            reason = _check_hash(node, group.digest, cancel)
            if reason is not None:
                return reason
    if rehash:
        # An earlier member can change while another large file is being read.
        for node in group.files:
            reason = _check_copy(node, root, places, cancel, group.proofs.get(node))
            if reason is not None:
                return reason
    return None


def _check_hash(node: Node, expected: bytes, cancel: threading.Event | None) -> str | None:
    try:
        digest = hash_unchanged(node, cancel=cancel)
    except DuplicateSearchCancelledError:
        return "cancelled"
    return None if digest == expected else "duplicate_content"


def _check_copy(node: Node, root: Node, places: Sequence[Protection], cancel: threading.Event | None,
                proof: bytes | None) -> str | None:
    reason = revalidate(node, root, places=places, cancel=cancel)
    if reason is not None:
        return reason
    before = unpack_snapshot(node.snapshot)
    try:
        current = stat_snapshot(node.path)
    except OSError:
        return "unreadable"
    if unpack_snapshot(current).links > 1:
        return "duplicate_hard_links"
    if current != node.snapshot or before.size != node.size:
        return "changed"
    return _check_handle(node, proof)


def _check_handle(node: Node, proof: bytes | None) -> str | None:
    if proof is None:
        return "duplicate_unverified"
    try:
        # fstat preserves the Windows change time that path-based lstat can report as birth time.
        # The no-follow path check above prevents knowingly opening cloud/link entries.
        with open(node.path, "rb") as stream:
            actual = pack_snapshot(os.fstat(stream.fileno()))
    except OSError:
        return "unreadable"
    return None if actual == proof else "changed"
