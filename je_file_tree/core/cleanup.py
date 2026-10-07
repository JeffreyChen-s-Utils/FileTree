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
from dataclasses import dataclass, field
from pathlib import PurePath

from je_file_tree.core.coverage import Coverage, coverage_of
from je_file_tree.core.node import Node, outermost
from je_file_tree.core.pacing import give_way

EMPTY_FOLDERS = "empty_folders"
_DAY = 86400.0


@dataclass(frozen=True, slots=True)
class RuleDetails:
    """Stable explanation keys, minimum age and risk; manual rules never permit bulk selection."""

    category: str = "temporary"
    minimum_age: float = 0
    risk: str = "manual"
    evidence: str = "manual"
    rebuild: str = "manual"
    rebuildable: bool = False


@dataclass(frozen=True, slots=True)
class Rule:
    """One kind of clean-up: what to recognise and the group (``key``) it lands in."""

    key: str
    folders: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    beside: tuple[str, ...] = ()
    in_folder: str | None = None
    details: RuleDetails = field(default_factory=RuleDetails)

    @property
    def rebuildable(self) -> bool:
        """Whether the application can recreate these generated files."""
        return self.details.rebuildable


DETAILS = {
    "temp": RuleDetails("temporary", 7, "manual", "temp", "temp"),
    "browser_cache": RuleDetails("cache", 7, "low", "browser_cache", "browser_cache", True),
    "thumbnails": RuleDetails("cache", 7, "low", "thumbnails", "thumbnails", True),
    "crash_dumps": RuleDetails("application_state", 30, "manual", "crash_dumps", "crash_dumps"),
    "package_caches": RuleDetails("cache", 30, "low", "package_caches", "package_caches", True),
    "build_output": RuleDetails("build", 7, "manual", "build_output", "build_output", True),
    "old_installers": RuleDetails("downloads", 90, "manual", "old_installers", "old_installers"),
    EMPTY_FOLDERS: RuleDetails("application_state", 7, "manual", "empty_folders", "empty_folders"),
}


RULES: tuple[Rule, ...] = (
    # The temporary folders are patterns that paths are compared with; nothing is written to them.
    Rule("temp", details=DETAILS["temp"],
         folders=("AppData/Local/Temp", "Windows/Temp", "/tmp", "/var/tmp",  # noqa: S108  # NOSONAR
                          "/private/var/folders/*/*/T")),
    Rule("browser_cache", details=DETAILS["browser_cache"], folders=(
        "Google/Chrome/User Data/*/Cache", "Google/Chrome/User Data/*/Code Cache",
        "Google/Chrome/User Data/*/GPUCache", "Microsoft/Edge/User Data/*/Cache",
        "Microsoft/Edge/User Data/*/Code Cache", "BraveSoftware/Brave-Browser/User Data/*/Cache",
        "Mozilla/Firefox/Profiles/*/cache2", ".cache/google-chrome/*/Cache", ".cache/chromium/*/Cache",
        ".cache/mozilla/firefox/*/cache2", "Library/Caches/Google/Chrome/*/Cache",
        "Library/Caches/Firefox/Profiles/*/cache2")),
    Rule("thumbnails", details=DETAILS["thumbnails"], folders=(".cache/thumbnails",),
         files=("thumbcache_*.db",), in_folder="Explorer"),
    Rule("crash_dumps", details=DETAILS["crash_dumps"],
         folders=("AppData/Local/CrashDumps", "Library/Logs/DiagnosticReports"), files=("*.dmp",)),
    Rule("package_caches", details=DETAILS["package_caches"], folders=(
        "AppData/Local/pip/Cache", ".cache/pip", "Library/Caches/pip", "AppData/Local/npm-cache",
        "AppData/Roaming/npm-cache", ".npm/_cacache", "AppData/Local/Yarn/Cache", ".cache/yarn",
        "Library/Caches/Yarn",
        "AppData/Local/NuGet/v3-cache", ".cargo/registry/cache")),
    Rule("build_output", details=DETAILS["build_output"], folders=(
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")),
    Rule("build_output", details=DETAILS["build_output"], folders=("node_modules",), beside=("package.json",)),
    Rule("build_output", details=DETAILS["build_output"], folders=(".tox",), beside=("tox.ini", "pyproject.toml")),
    Rule("build_output", details=DETAILS["build_output"], folders=("target",), beside=("Cargo.toml", "pom.xml")),
    Rule("build_output", details=DETAILS["build_output"], folders=("build", "dist"),
         beside=("pyproject.toml", "setup.py", "package.json")),
    Rule("old_installers", details=DETAILS["old_installers"],
         files=("*.msi", "*.msix", "*.exe", "*.dmg", "*.pkg", "*.deb", "*.rpm"), in_folder="Downloads"),
)


@dataclass(frozen=True, slots=True)
class CleanupGroup:
    """The entries one kind of clean-up found, the largest first, and their total size."""

    key: str
    nodes: list[Node]
    size: int
    details: RuleDetails = field(default_factory=RuleDetails)


def find_cleanup(root: Node, *, rules: tuple[Rule, ...] = RULES, now: float | None = None,
                 cancel: threading.Event | None = None, coverage: Coverage | None = None) -> list[CleanupGroup] | None:
    """The clean-up groups beneath ``root`` (empty folders included), the largest group first.

    None when ``cancel`` is set before the walk is done (checked once per folder).
    """
    matcher = _Matcher(rules, time.time() if now is None else now)
    coverage = coverage or coverage_of(root)
    found = _walk(root, matcher, cancel, coverage)
    if found is None:
        return None
    claimed = {id(node) for nodes in found.values() for node in nodes}
    empty = [folder for folder in empty_folders(root) if not _inside(folder, claimed)
             and matcher.old_enough(folder, DETAILS[EMPTY_FOLDERS].minimum_age)]
    if empty:
        found[EMPTY_FOLDERS] = empty
    details = {rule.key: rule.details for rule in rules} | {EMPTY_FOLDERS: DETAILS[EMPTY_FOLDERS]}
    groups = [CleanupGroup(key, sorted(nodes, key=lambda node: -node.size), sum(node.size for node in nodes),
                           details[key])
              for key, nodes in found.items()]
    groups.sort(key=lambda group: (-group.size, group.key))
    return groups


def _walk(root: Node, matcher: _Matcher, cancel: threading.Event | None,
          coverage: Coverage) -> dict[str, list[Node]] | None:
    """Every entry beneath ``root`` a rule matches, by group; None when cancelled."""
    found: dict[str, list[Node]] = defaultdict(list)
    stack: list[tuple[Node, tuple[str, ...]]] = [(root, _parts(root.path))]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        folder, parts = stack.pop()
        stack.extend(_visit(folder, parts, matcher, found, coverage))
    return found


def _visit(folder: Node, parts: tuple[str, ...], matcher: _Matcher,
           found: dict[str, list[Node]], coverage: Coverage) -> list[tuple[Node, tuple[str, ...]]]:
    """Put ``folder``'s matching entries in ``found``; returns the subfolders still to look into."""
    names = {child.name.casefold() for child in folder.children}
    deeper: list[tuple[Node, tuple[str, ...]]] = []
    for child in folder.children:
        if child.is_link or child.error is not None:
            continue
        if child.is_dir:
            child_parts = (*parts, child.name.casefold())
            key = matcher.folder_key(child_parts, names, child) if coverage.can_clean(child) else None
            if key is None and child.children:
                deeper.append((child, child_parts))  # a matching folder is suggested whole, not entered
        else:
            key = matcher.file_key(child, parts[-1] if parts else "")
        if key is not None:
            found[key].append(child)
    return deeper


def empty_folders(root: Node) -> list[Node]:
    """Folders beneath ``root`` with nothing in them but empty folders, the outermost of each only.

    A folder that could not be read, was skipped or holds a link is not known to be empty.
    """
    order: list[Node] = []
    stack = [root]
    while stack:
        give_way()
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

    def folder_key(self, parts: tuple[str, ...], siblings: set[str], node: Node) -> str | None:
        """The group of the folder at ``parts`` (its casefolded path components), or None."""
        candidates = self._folders.get(parts[-1], ())
        for pattern, anchored, rule in candidates:
            if (_ends_with(parts, pattern, anchored) and _has_sign(rule, siblings)
                    and self.old_enough(node, rule.details.minimum_age) and _has_evidence(node, rule)):
                return rule.key
        return None

    def file_key(self, node: Node, folder_name: str) -> str | None:
        """The group of the file ``node`` (in a folder of the casefolded name ``folder_name``), or None."""
        for names, rule in self._files:
            if not names.match(node.name):
                continue
            if rule.in_folder is not None and folder_name != rule.in_folder.casefold():
                continue
            if not self.old_enough(node, rule.details.minimum_age):
                continue
            return rule.key
        return None

    def old_enough(self, node: Node, days: float) -> bool:
        """Folder.modified is the newest descendant, so a recent file disqualifies the whole folder."""
        return days == 0 or 0 < node.modified <= self._now - days * _DAY


def _has_evidence(node: Node, rule: Rule) -> bool:
    if rule.key != "build_output":
        return True
    if node.name.casefold() == "__pycache__":
        return bool(node.children) and all(not child.is_dir and child.name.casefold().endswith(".pyc")
                                          for child in node.children)
    if node.name.casefold() in (".pytest_cache", ".mypy_cache", ".ruff_cache"):
        return any(child.name == "CACHEDIR.TAG" and not child.is_dir for child in node.children)
    return True  # Other build rules require a sibling project manifest and remain manual review.


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
