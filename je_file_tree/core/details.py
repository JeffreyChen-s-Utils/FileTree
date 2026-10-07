"""Small, cancellable distributions for a selected subtree, without copying its files."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass

from je_file_tree.core.analysis import AGES, CATEGORIES, age_of, category_of, extension_of
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way


@dataclass(frozen=True, slots=True)
class Breakdown:
    """Type/age logical bytes and counts; unusable modification dates remain separate."""

    types: dict[str, tuple[int, int]]
    ages: dict[str, tuple[int, int]]


def breakdown(root: Node, now: float, cancel: threading.Event | None = None) -> Breakdown | None:
    """Survey recorded entries iteratively, yielding per folder; return None when cancelled."""
    types = dict.fromkeys(CATEGORIES, (0, 0))
    ages = dict.fromkeys((*AGES, 'unknown'), (0, 0))
    stack = [root]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        node = stack.pop()
        if node.is_link:
            continue
        if node.is_dir:
            give_way()
            stack.extend(node.children)
            continue
        category = category_of(extension_of(node.name))
        modified = node.modified
        age = age_of(modified, now) if math.isfinite(modified) and 0 < modified <= now else 'unknown'
        for values, key in ((types, category), (ages, age)):
            size, count = values[key]
            values[key] = size + node.size, count + 1
    return Breakdown(types, ages)
