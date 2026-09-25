"""The scanned tree: one ``Node`` per folder, file or link."""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field


@dataclass(slots=True, eq=False)
class Node:
    """One entry of a scanned tree.

    ``allocated`` is the space taken on disk (see ``file_tree.core.allocation``).
    For a folder, ``size``, ``allocated``, ``file_count``, ``dir_count`` and ``modified`` are
    totals over everything beneath it (filled in by the scanner once the whole
    tree is read), and ``children`` is a list sorted largest first. A file keeps
    the shared empty tuple instead, which saves a list per file on trees with
    millions of them. A link (symlink or Windows junction) is kept as an entry of
    size 0 and is never followed, so a loop can never make a scan run forever.

    Only the root stores a full path (as its ``name``); every other path is
    rebuilt from the names on the way up, see ``path``.
    """

    name: str
    is_dir: bool
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    modified: float = 0.0
    is_link: bool = False
    error: str | None = None
    allocated: int = 0
    children: list[Node] | tuple[()] = field(default=())
    parent: Node | None = field(default=None, repr=False)

    @property
    def path(self) -> str:
        """The full path of this entry."""
        names = []
        node: Node | None = self
        while node is not None:
            names.append(node.name)
            node = node.parent
        names.reverse()
        return os.path.join(*names)

    @property
    def depth(self) -> int:
        """How many levels below the root this entry is (0 for the root)."""
        depth = 0
        node = self.parent
        while node is not None:
            depth += 1
            node = node.parent
        return depth

    def share_of_parent(self) -> float:
        """This entry's size as a fraction (0..1) of its parent's size; 1.0 for the root."""
        if self.parent is None:
            return 1.0
        if self.parent.size <= 0:
            return 0.0
        return self.size / self.parent.size

    def iter_nodes(self) -> Iterator[Node]:
        """Every node beneath (and including) this one, parents before children."""
        stack = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    def iter_files(self) -> Iterator[Node]:
        """Every file beneath this node (links excluded)."""
        return (node for node in self.iter_nodes() if not node.is_dir and not node.is_link)

    def detach(self) -> None:
        """Take this entry out of the tree and subtract its totals from every folder above it.

        Used after the entry was deleted from disk, so the numbers stay right
        without a rescan. Does nothing for the root.
        """
        parent = self.parent
        if parent is None or not isinstance(parent.children, list):
            return
        parent.children.remove(self)
        self.parent = None
        folders = self.dir_count + (1 if self.is_dir and not self.is_link else 0)
        node: Node | None = parent
        while node is not None:
            node.size -= self.size
            node.allocated -= self.allocated
            node.file_count -= self.file_count
            node.dir_count -= folders
            node = node.parent

    def replace_with(self, new: Node) -> None:
        """Put ``new`` (a fresh scan of this same folder) in this entry's place and correct every total above it.

        ``new`` takes this entry's name, so a rescan's full-path root reads like
        the child it replaces. Does nothing for the root.
        """
        parent = self.parent
        if parent is None or not isinstance(parent.children, list):
            return
        position = next(index for index, child in enumerate(parent.children) if child is self)
        new.name = self.name
        new.parent = parent
        parent.children[position] = new
        self.parent = None
        size = new.size - self.size
        allocated = new.allocated - self.allocated
        files = new.file_count - self.file_count
        folders = new.dir_count - self.dir_count
        node: Node | None = parent
        while node is not None:
            node.size += size
            node.allocated += allocated
            node.file_count += files
            node.dir_count += folders
            node.modified = max(node.modified, new.modified)
            node = node.parent


def outermost(nodes: Iterable[Node]) -> list[Node]:
    """``nodes`` without repeats and without those inside another one of them, in the order given.

    Moving or deleting a folder takes everything in it along, so this is the set to act on when
    several entries were picked.
    """
    chosen: dict[int, Node] = {}
    for node in nodes:
        chosen.setdefault(id(node), node)
    kept: list[Node] = []
    for node in chosen.values():
        above = node.parent
        while above is not None and id(above) not in chosen:
            above = above.parent
        if above is None:
            kept.append(node)
    return kept
