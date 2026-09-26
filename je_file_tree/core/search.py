"""Find entries anywhere in a scanned tree: by name, and by size, age, type and kind."""

from __future__ import annotations

import fnmatch
import heapq
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from je_file_tree.core.analysis import category_of, extension_of
from je_file_tree.core.node import Node, outermost
from je_file_tree.core.pacing import give_way

WILDCARDS = frozenset("*?[")
ANY, FILES, FOLDERS = "any", "files", "folders"
KINDS = (ANY, FILES, FOLDERS)


@dataclass(frozen=True, slots=True)
class Query:
    """What to look for; every condition given must hold.

    ``text`` is read by ``name_matcher``. Sizes are in bytes. ``changed_within`` and ``unchanged_for``
    are spans in seconds counted back from the moment of the search, so a saved query stays meaningful.
    ``category`` (a key of ``analysis.CATEGORIES``) matches files of that type only; ``kind`` is one of
    ``KINDS``.
    """

    text: str = ""
    min_size: int | None = None
    max_size: int | None = None
    changed_within: float | None = None
    unchanged_for: float | None = None
    category: str | None = None
    kind: str = ANY


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


def search(root: Node, query: Query | str, limit: int = 1000,
           cancel: threading.Event | None = None, *, now: float | None = None) -> SearchResult | None:
    """Every entry beneath ``root`` (files and folders, not ``root`` itself) that ``query`` accepts.

    A plain string is a name query. The matches are listed largest first; a query with no condition
    finds nothing. Returns None when ``cancel`` is set before the search is done (checked once per
    folder). ``now`` (a POSIX time) is what the age conditions count back from.
    """
    query = Query(text=query) if isinstance(query, str) else query
    if query == Query(text=query.text):  # a name alone: test the names directly, the common and fastest case
        matcher = name_matcher(query.text)
        found = None if matcher is None else _collect(root, matcher, cancel, by_name=True)
    else:
        test = accepts(query, time.time() if now is None else now)
        found = None if test is None else _collect(root, test, cancel, by_name=False)
    if found is None:
        return None if cancel is not None and cancel.is_set() else SearchResult([], 0, 0)
    size = sum(node.size for node in outermost(found))
    largest = heapq.nlargest(limit, found, key=_size) if limit > 0 else []
    return SearchResult(largest, len(found), size)


def _collect(root: Node, test: Callable[..., object], cancel: threading.Event | None, *,
             by_name: bool) -> list[Node] | None:
    """Every entry beneath ``root`` that ``test`` accepts (given its name, or the node); None when cancelled."""
    found: list[Node] = []
    stack = [root]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        for child in stack.pop().children:
            if test(child.name if by_name else child):
                found.append(child)
            if child.children:
                stack.append(child)
    return found


def accepts(query: Query, now: float) -> Callable[[Node], bool] | None:
    """The test of an entry against every condition of ``query``; None when it has no condition at all."""
    name = name_matcher(query.text)
    kind = _kind_test(query)
    kept = _kept_by_size_and_age(query, now)
    if name is None and kind is None and kept is None:
        return None

    def test(node: Node) -> bool:
        if name is not None and name(node.name) is None:
            return False
        if kind is not None and not kind(node):
            return False
        return kept is None or kept(node)

    return test


def _kind_test(query: Query) -> Callable[[Node], bool] | None:
    """One test for the kind and the file type of ``query`` (None when it asks for neither)."""
    category = query.category
    if category is not None:
        if query.kind == FOLDERS:
            return lambda node: False  # a file type with folders only: every condition must hold, none can
        return lambda node: not node.is_dir and category_of(extension_of(node.name)) == category
    if query.kind == FILES:
        return lambda node: not node.is_dir
    if query.kind == FOLDERS:
        return lambda node: node.is_dir and not node.is_link
    return None


def _kept_by_size_and_age(query: Query, now: float) -> Callable[[Node], bool] | None:
    """One test for the size and age conditions of ``query`` (None when it has none)."""
    least = query.min_size if query.min_size is not None else -1
    most = query.max_size if query.max_size is not None else float("inf")
    since = now - query.changed_within if query.changed_within is not None else float("-inf")
    before = now - query.unchanged_for if query.unchanged_for is not None else None
    if (query.min_size, query.max_size, query.changed_within, before) == (None, None, None, None):
        return None
    if before is None:
        return lambda node: least <= node.size <= most and node.modified >= since
    return lambda node: least <= node.size <= most and since <= node.modified <= before and node.modified > 0


def _size(node: Node) -> int:
    return node.size
