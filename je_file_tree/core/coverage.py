"""Account for scan coverage without inferring emptiness from missing children."""

from __future__ import annotations

from dataclasses import dataclass
import threading

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.scanner import EXCLUDED, HIDDEN_OMITTED, NOT_SCANNED


@dataclass(frozen=True, slots=True)
class Coverage:
    """Known logical bytes and folder counts; bytes in omitted branches are unknown, never zero."""

    known_bytes: int
    known_folders: int
    skipped_folders: int
    inaccessible_folders: int
    pending_folders: int
    unsafe: frozenset[Node]

    @property
    def complete(self) -> bool:
        """Whether every discovered branch and entry was read."""
        return not (self.skipped_folders or self.inaccessible_folders or self.pending_folders)

    def can_clean(self, node: Node) -> bool:
        """Whether this snapshot contains complete coverage of the proposed entry."""
        return node.error is None and not node.is_link and node not in self.unsafe


def coverage_of(root: Node, *, cancel: threading.Event | None = None) -> Coverage | None:
    """Survey omitted scopes and their ancestors; return None only when an explicit event cancels."""
    known = skipped = inaccessible = pending = 0
    folders: list[Node] = []
    unsafe: set[Node] = set()
    stack = [root]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        folder = stack.pop()
        folders.append(folder)
        if folder.error in (EXCLUDED, HIDDEN_OMITTED):
            skipped += 1
        elif folder.error == NOT_SCANNED:
            pending += 1
        elif folder.error is not None:
            inaccessible += 1
        elif folder.path is not None:
            known += 1
        if folder.error is not None or any(child.error is not None for child in folder.children):
            unsafe.add(folder)
        stack.extend(child for child in folder.children if child.is_dir and not child.is_link)
    for folder in reversed(folders):
        if cancel is not None and cancel.is_set():
            return None
        if folder in unsafe and folder.parent is not None:
            unsafe.add(folder.parent)
    return Coverage(root.size, known, skipped, inaccessible, pending, frozenset(unsafe))
