"""Folders to skip while scanning: name patterns (``node_modules``, ``*.cache``) and whole paths.

A pattern without a path separator is matched against folder names, with ``*`` and ``?``, case
never mattering (``node_modules`` skips every folder of that name). A pattern with a separator, or a
drive, is a folder path: that one folder is skipped. Only folders are skipped: a skipped folder is
still listed (size 0, marked), but nothing inside it is read.
"""

from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Callable, Iterable

Excluded = Callable[[str, str], bool]
"""Tells from a folder's name and full path whether it is skipped."""


def exclusion_test(patterns: Iterable[str]) -> Excluded | None:
    """The test for ``patterns`` (blank ones ignored), or None when nothing is excluded."""
    names: list[str] = []
    paths: set[str] = set()
    for raw in patterns:
        pattern = raw.strip()
        if not pattern:
            continue
        if is_path(pattern):
            paths.add(_normal(pattern))
        else:
            names.append(fnmatch.translate(pattern))
    if not names and not paths:
        return None
    name_match = re.compile("|".join(f"(?:{name})" for name in names), re.IGNORECASE).match if names else None

    def excluded(name: str, path: str) -> bool:
        if name_match is not None and name_match(name):
            return True
        return bool(paths) and _normal(path) in paths

    return excluded


def is_path(pattern: str) -> bool:
    """Whether ``pattern`` names one folder by its path rather than folders by their name."""
    return "/" in pattern or "\\" in pattern or bool(os.path.splitdrive(pattern)[0])


def _normal(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))
