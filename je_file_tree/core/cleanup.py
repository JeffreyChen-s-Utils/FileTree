"""Clean-up suggestions: known places whose contents can usually go, and empty folders.

The rules are data (``RULES``): folders are recognised by the end of their path (``AppData/Local/Temp``,
``Google/Chrome/User Data/*/Cache``; ``*`` and ``?`` within a name, case ignored; a leading ``/``
anchors at the file-system root), files by their name (``*.dmp``). A rule can also ask for a sign
next to the folder (``target`` beside ``Cargo.toml``), for files inside a folder of some name
(installers in ``Downloads``) and for files unchanged for some days. A matching folder is suggested
as a whole and not looked into further. Nothing here deletes anything: the window moves what the
user picks to the Recycle Bin, asking first.
"""

from __future__ import annotations

import fnmatch
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePath

from je_file_tree.core.node import Node, outermost

EMPTY_FOLDERS = "empty_folders"
_DAY = 86400.0


@dataclass(frozen=True, slots=True)
class Rule:
    """One kind of clean-up: what to recognise and the group (``key``) it lands in."""

    key: str
    folders: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    beside: tuple[str, ...] = ()
    in_folder: str | None = None
    unchanged_days: float | None = None
    rebuildable: bool = False


RULES: tuple[Rule, ...] = (
    Rule("temp", folders=("AppData/Local/Temp", "Windows/Temp", "/tmp", "/var/tmp",  # noqa: S108 - patterns, not files
                          "/private/var/folders/*/*/T")),
    Rule("browser_cache", folders=(
        "Google/Chrome/User Data/*/Cache", "Google/Chrome/User Data/*/Code Cache",
        "Google/Chrome/User Data/*/GPUCache", "Microsoft/Edge/User Data/*/Cache",
        "Microsoft/Edge/User Data/*/Code Cache", "BraveSoftware/Brave-Browser/User Data/*/Cache",
        "Mozilla/Firefox/Profiles/*/cache2", ".cache/google-chrome", ".cache/chromium", ".cache/mozilla",
        "Library/Caches/Google/Chrome", "Library/Caches/Firefox")),
    Rule("thumbnails", folders=(".cache/thumbnails",), files=("thumbcache_*.db",), in_folder="Explorer"),
    Rule("crash_dumps", folders=("AppData/Local/CrashDumps", "Library/Logs/DiagnosticReports"), files=("*.dmp",)),
    Rule("package_caches", rebuildable=True, folders=(
        "AppData/Local/pip/Cache", ".cache/pip", "Library/Caches/pip", "AppData/Local/npm-cache",
        "AppData/Roaming/npm-cache", ".npm/_cacache", "AppData/Local/Yarn/Cache", ".cache/yarn",
        "Library/Caches/Yarn", ".gradle/caches", ".m2/repository", ".nuget/packages",
        "AppData/Local/NuGet/v3-cache", ".cargo/registry/cache")),
    Rule("build_output", rebuildable=True, folders=(
        "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox")),
    Rule("build_output", rebuildable=True, folders=("target",), beside=("Cargo.toml", "pom.xml")),
    Rule("build_output", rebuildable=True, folders=("build", "dist"),
         beside=("pyproject.toml", "setup.py", "package.json")),
    Rule("old_installers", files=("*.msi", "*.msix", "*.exe", "*.dmg", "*.pkg", "*.deb", "*.rpm"),
         in_folder="Downloads", unchanged_days=90),
)


@dataclass(frozen=True, slots=True)
class CleanupGroup:
    """The entries one kind of clean-up found, the largest first, and their total size."""

    key: str
    nodes: list[Node]
    size: int


def find_cleanup(root: Node, *, rules: tuple[Rule, ...] = RULES, now: float | None = None,
                 cancel: threading.Event | None = None) -> list[CleanupGroup] | None:
    """The clean-up groups beneath ``root`` (empty folders included), the largest group first.

    None when ``cancel`` is set before the walk is done (checked once per folder).
    """
    matcher = _Matcher(rules, time.time() if now is None else now)
    found: dict[str, list[Node]] = defaultdict(list)
    stack: list[tuple[Node, tuple[str, ...]]] = [(root, _parts(root.path))]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        folder, parts = stack.pop()
        names = {child.name.casefold() for child in folder.children}
        for child in folder.children:
            if child.is_link:
                continue
            if not child.is_dir:
                key = matcher.file_key(child, parts[-1] if parts else "")
                if key is not None:
                    found[key].append(child)
                continue
            child_parts = (*parts, child.name.casefold())
            key = matcher.folder_key(child_parts, names)
            if key is not None:
                found[key].append(child)
            elif child.children:
                stack.append((child, child_parts))
    claimed = {id(node) for nodes in found.values() for node in nodes}
    empty = [folder for folder in empty_folders(root) if not _inside(folder, claimed)]  # listed once, in its group
    if empty:
        found[EMPTY_FOLDERS] = empty
    groups = [CleanupGroup(key, sorted(nodes, key=lambda node: -node.size), sum(node.size for node in nodes))
              for key, nodes in found.items()]
    groups.sort(key=lambda group: (-group.size, group.key))
    return groups


def empty_folders(root: Node) -> list[Node]:
    """Folders beneath ``root`` with nothing in them but empty folders, the outermost of each only.

    A folder that could not be read, was skipped or holds a link is not known to be empty.
    """
    order: list[Node] = []
    stack = [root]
    while stack:
        folder = stack.pop()
        order.append(folder)
        stack.extend(child for child in folder.children if child.is_dir and not child.is_link)
    empty: set[int] = set()
    for folder in reversed(order):  # children before their parents
        if folder.error is None and all(child.is_dir and not child.is_link and id(child) in empty
                                        for child in folder.children):
            empty.add(id(folder))
    return outermost(folder for folder in order if id(folder) in empty and folder is not root)


class _Matcher:
    """The rules, indexed for a quick test of every folder and file of a scan."""

    def __init__(self, rules: tuple[Rule, ...], now: float) -> None:
        self._now = now
        self._folders: dict[str, list[tuple[tuple[str, ...], bool, Rule]]] = defaultdict(list)
        self._files: list[tuple[re.Pattern[str], Rule]] = []
        for rule in rules:
            for pattern in rule.folders:
                anchored = pattern.startswith("/")
                parts = tuple(part.casefold() for part in pattern.strip("/").split("/"))
                self._folders[parts[-1]].append((parts, anchored, rule))
            if rule.files:
                names = "|".join(f"(?:{fnmatch.translate(name)})" for name in rule.files)
                self._files.append((re.compile(names, re.IGNORECASE), rule))

    def folder_key(self, parts: tuple[str, ...], siblings: set[str]) -> str | None:
        """The group of the folder at ``parts`` (its casefolded path components), or None."""
        candidates = self._folders.get(parts[-1], ())
        for pattern, anchored, rule in candidates:
            if _ends_with(parts, pattern, anchored) and _has_sign(rule, siblings):
                return rule.key
        return None

    def file_key(self, node: Node, folder_name: str) -> str | None:
        """The group of the file ``node`` (in a folder of the casefolded name ``folder_name``), or None."""
        for names, rule in self._files:
            if not names.match(node.name):
                continue
            if rule.in_folder is not None and folder_name != rule.in_folder.casefold():
                continue
            if rule.unchanged_days is not None and not 0 < node.modified <= self._now - rule.unchanged_days * _DAY:
                continue
            return rule.key
        return None


def _ends_with(parts: tuple[str, ...], pattern: tuple[str, ...], anchored: bool) -> bool:
    count = len(pattern)
    if len(parts) < count or (anchored and len(parts) != count + 1):  # anchored: only the root before it
        return False
    return all(fnmatch.fnmatchcase(part, wanted) for part, wanted in zip(parts[-count:], pattern, strict=True))


def _inside(node: Node, folders: set[int]) -> bool:
    above = node.parent
    while above is not None:
        if id(above) in folders:
            return True
        above = above.parent
    return False


def _has_sign(rule: Rule, siblings: set[str]) -> bool:
    return not rule.beside or any(sign.casefold() in siblings for sign in rule.beside)


def _parts(path: str) -> tuple[str, ...]:
    """The casefolded components of an absolute path, the root (``/``, ``C:\\``) as the first one."""
    pure = PurePath(path)
    return tuple(part.casefold() for part in pure.parts)
