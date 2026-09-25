"""Find entries by name anywhere in a scanned tree."""

from __future__ import annotations

import fnmatch
import heapq
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass

from file_tree.core.node import Node, outermost

WILDCARDS = frozenset("*?[")


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What a search found: the ``limit`` largest matches, and the count and size of all of them.

    ``size`` counts an entry inside a matching folder once (with the folder).
    """

    matches: list[Node]
    count: int
    size: int


def name_matcher(query: str) -> Callable[[str], object] | None:
    """A test for names (truthy when one matches), from what the user typed; None when there is nothing to look for.

    Case never matters. Several patterns are separated by ``;``. A pattern with ``*``, ``?``
    or ``[...]`` must match the whole name (``*.mp4``); plain text matches anywhere in it (``backup``).
    """
    parts = [part.strip() for part in query.split(";") if part.strip()]
    if not parts:
        return None
    expressions = [fnmatch.translate(part) if WILDCARDS & set(part) else rf"(?s:.*{re.escape(part)}.*)\Z"
                   for part in parts]
    pattern = re.compile("|".join(f"(?:{expression})" for expression in expressions), re.IGNORECASE)
    return pattern.match


def search(root: Node, query: str, limit: int = 1000, cancel: threading.Event | None = None) -> SearchResult | None:
    """Every entry beneath ``root`` (files and folders, not ``root`` itself) whose name matches ``query``.

    See ``name_matcher`` for how ``query`` is read. The matches are listed largest first. Returns None
    when ``cancel`` is set before the search is done (it is checked once per folder).
    """
    matches = name_matcher(query)
    if matches is None:
        return SearchResult([], 0, 0)
    found: list[Node] = []
    stack = [root]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        for child in stack.pop().children:
            if matches(child.name):
                found.append(child)
            if child.children:
                stack.append(child)
    size = sum(node.size for node in outermost(found))
    largest = heapq.nlargest(limit, found, key=_size) if limit > 0 else []
    return SearchResult(largest, len(found), size)


def _size(node: Node) -> int:
    return node.size
