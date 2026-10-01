"""Numbers computed from a scanned tree: the largest files, space per file type and per age."""

from __future__ import annotations

import heapq
import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

# File-type groups shown in the "File types" view and used to colour the
# treemap. Keys are stable identifiers (the GUI translates them).
CATEGORY_EXTENSIONS: dict[str, frozenset[str]] = {
    "images": frozenset({
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif",
        ".svg", ".ico", ".psd", ".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".avif",
    }),
    "video": frozenset({
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts",
    }),
    "audio": frozenset({
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus", ".mid", ".midi",
    }),
    "documents": frozenset({
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp",
        ".txt", ".md", ".rtf", ".csv", ".epub",
    }),
    "archives": frozenset({
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".iso", ".img", ".cab",
    }),
    "code": frozenset({
        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb",
        ".php", ".html", ".css", ".json", ".xml", ".yml", ".yaml", ".toml", ".sql", ".sh",
        ".ps1", ".bat", ".ipynb", ".pyc",
    }),
    "programs": frozenset({
        ".exe", ".dll", ".msi", ".sys", ".so", ".dylib", ".app", ".apk", ".jar", ".pyd",
    }),
}
OTHER_CATEGORY = "other"
CATEGORIES: tuple[str, ...] = (*CATEGORY_EXTENSIONS, OTHER_CATEGORY)
NO_EXTENSION = ""

_CATEGORY_OF_EXTENSION = {
    extension: category
    for category, extensions in CATEGORY_EXTENSIONS.items()
    for extension in extensions
}


def extension_of(name: str) -> str:
    """The lower-case extension of a file name, dot included ("" when it has none).

    A leading dot does not start an extension (``.bashrc`` has none), and
    neither does a trailing one. Written with ``rfind`` rather than
    ``os.path.splitext``: it runs once per file, and this is twice as fast.
    """
    dot = name.rfind(".")
    return name[dot:].lower() if 0 < dot < len(name) - 1 else NO_EXTENSION


def category_of(extension: str) -> str:
    """The file-type group of an extension as returned by ``extension_of``."""
    return _CATEGORY_OF_EXTENSION.get(extension, OTHER_CATEGORY)


@dataclass(frozen=True, slots=True)
class ExtensionStat:
    """Space taken by every file with one extension."""

    extension: str
    category: str
    size: int
    count: int


@dataclass(frozen=True, slots=True)
class CategoryStat:
    """Space taken by every file of one type group."""

    category: str
    size: int
    count: int


# Age groups by time since a file last changed: (name, the oldest age in days
# that still belongs to it). The last group takes everything older, and files
# with no usable time (0) land there too.
AGE_GROUPS: tuple[tuple[str, float], ...] = (
    ("month", 30.0), ("half_year", 182.5), ("year", 365.0), ("two_years", 730.0), ("older", math.inf),
)
AGES: tuple[str, ...] = tuple(name for name, _ in AGE_GROUPS)
_DAY = 86400.0


@dataclass(frozen=True, slots=True)
class AgeStat:
    """Space taken by every file last changed within one age group."""

    age: str
    size: int
    count: int


@dataclass(frozen=True, slots=True)
class Summary:
    """What the result views show, computed in one pass."""

    largest: list[Node]
    extensions: list[ExtensionStat]
    ages: list[AgeStat]
    now: float


def summarise(root: Node, limit: int = 1000, *, now: float | None = None) -> Summary:
    """The largest files, the per-extension totals and the per-age totals, in one pass over the tree.

    A single pass matters on big scans: measured on 650,000 files, 0.65 s
    against 1.4 s for the first two computed one after the other. ``now`` is
    the moment ages are counted from (the current time when omitted).
    """
    now = time.time() if now is None else now
    files, sizes, counts = _files_and_extensions(root)
    largest = heapq.nlargest(limit, files, key=_file_size) if limit > 0 else []
    return Summary(largest, _extension_list(sizes, counts), age_stats(files, now), now)


def largest_files(root: Node, limit: int = 1000) -> list[Node]:
    """The ``limit`` largest files beneath ``root`` (or ``root`` itself if it is a file), largest first."""
    return summarise(root, limit).largest


def largest_matching(root: Node, keep: Callable[[Node], bool], limit: int = 1000) -> list[Node]:
    """The ``limit`` largest files beneath ``root`` for which ``keep`` is true, largest first."""
    files = _files_and_extensions(root)[0]
    return heapq.nlargest(limit, filter(keep, files), key=_file_size) if limit > 0 else []


def files_beneath(root: Node) -> list[Node]:
    """Every file beneath ``root`` (or ``root`` itself if it is a file), links left out."""
    return _files_and_extensions(root)[0]


def age_of(modified: float, now: float) -> str:
    """The age group of a file last changed at ``modified`` (a POSIX time), seen from ``now``."""
    if modified <= 0:
        return AGES[-1]
    days = (now - modified) / _DAY
    return next(name for name, oldest in AGE_GROUPS if days <= oldest)


def age_stats(files: Iterable[Node], now: float) -> list[AgeStat]:
    """Total size and count per age group, in the order of ``AGES`` (empty groups included)."""
    sizes = dict.fromkeys(AGES, 0)
    counts = dict.fromkeys(AGES, 0)
    for node in files:
        age = age_of(node.modified, now)
        sizes[age] += node.size
        counts[age] += 1
    return [AgeStat(age, sizes[age], counts[age]) for age in AGES]


def subtract_ages(ages: list[AgeStat], removed: list[AgeStat]) -> list[AgeStat]:
    """``ages`` minus ``removed`` group by group (both from ``age_stats``), after files were deleted."""
    taken = {stat.age: stat for stat in removed}
    return [AgeStat(stat.age, stat.size - taken[stat.age].size, stat.count - taken[stat.age].count)
            if stat.age in taken else stat for stat in ages]


def extension_stats(root: Node) -> list[ExtensionStat]:
    """Total size and count per extension beneath ``root`` (or of ``root`` if it is a file), largest first."""
    _, sizes, counts = _files_and_extensions(root)
    return _extension_list(sizes, counts)


def _files_and_extensions(root: Node) -> tuple[list[Node], dict[str, int], dict[str, int]]:
    """Every file beneath ``root`` (links left out), with the total size and count per extension."""
    files: list[Node] = []
    sizes: dict[str, int] = {}
    counts: dict[str, int] = {}
    stack = [root]
    while stack:
        node = stack.pop()
        if node.is_link:
            continue
        if node.is_dir:
            give_way()
            stack.extend(node.children)
            continue
        files.append(node)
        extension = extension_of(node.name)
        sizes[extension] = sizes.get(extension, 0) + node.size
        counts[extension] = counts.get(extension, 0) + 1
    return files, sizes, counts


def _extension_list(sizes: dict[str, int], counts: dict[str, int]) -> list[ExtensionStat]:
    stats = [ExtensionStat(extension, category_of(extension), size, counts[extension])
             for extension, size in sizes.items()]
    stats.sort(key=lambda stat: (-stat.size, stat.extension))
    return stats


def subtract_stats(stats: list[ExtensionStat], removed: list[ExtensionStat]) -> list[ExtensionStat]:
    """``stats`` minus ``removed`` (both from ``extension_stats``), dropping extensions left with no files.

    Keeps the per-type totals right after files were deleted, without a rescan.
    """
    taken = {stat.extension: stat for stat in removed}
    result = []
    for stat in stats:
        gone = taken.get(stat.extension)
        if gone is None:
            result.append(stat)
        elif stat.count > gone.count:
            result.append(ExtensionStat(stat.extension, stat.category, stat.size - gone.size,
                                        stat.count - gone.count))
    result.sort(key=lambda stat: (-stat.size, stat.extension))
    return result


def category_stats(extensions: list[ExtensionStat]) -> list[CategoryStat]:
    """``extension_stats`` added up per type group, largest first; empty groups left out."""
    sizes = dict.fromkeys(CATEGORIES, 0)
    counts = dict.fromkeys(CATEGORIES, 0)
    for stat in extensions:
        sizes[stat.category] += stat.size
        counts[stat.category] += stat.count
    stats = [CategoryStat(category, sizes[category], counts[category])
             for category in CATEGORIES if counts[category]]
    stats.sort(key=lambda stat: (-stat.size, stat.category))
    return stats


def _file_size(node: Node) -> int:
    return node.size
