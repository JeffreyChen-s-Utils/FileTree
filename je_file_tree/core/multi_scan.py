"""Bounded multi-root scans reuse the normal no-follow crawler beneath a pathless virtual root."""

from collections.abc import Sequence
from dataclasses import replace
import os
import threading
import time

from je_file_tree.core.hard_links import account_hard_links
from je_file_tree.core.mounts import mount_points
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import (NOT_SCANNED, ProgressCallback, RootCallback, ScanCancelledError,
                                      ScanOptions, ScanProgress, ScanResult, scan)

MAX_ROOTS = 256


def _roots(paths: Sequence[str | os.PathLike[str]]) -> tuple[str, ...]:
    if isinstance(paths, (str, bytes)) or not 1 <= len(paths) <= MAX_ROOTS:
        raise ValueError("a multi-scan requires between 1 and 256 explicit roots")
    unique = {os.path.normcase(os.path.abspath(os.fspath(path))): os.path.abspath(os.fspath(path)) for path in paths}
    points = mount_points()
    kept: list[str] = []
    for path in sorted(unique.values(), key=lambda value: (len(value), os.path.normcase(value))):
        if not any(_overlaps(parent, path, points) for parent in kept):
            kept.append(path)
    return tuple(kept)


def _overlaps(parent: str, path: str, points: frozenset[str]) -> bool:
    try:
        if os.path.commonpath((parent, path)) != parent:
            return False
    except ValueError:
        return False  # Different drives are independent roots.
    try:
        if os.stat(parent, follow_symlinks=False).st_dev != os.stat(path, follow_symlinks=False).st_dev:
            return False  # A subfolder on another mounted volume is not traversed by its ancestor.
    except OSError:
        return False  # Keep unavailable explicit roots as error-bearing children.
    # The normal crawler stops at these native boundaries, so their explicitly selected roots
    # remain separate scans even when they are lexically below another requested root.
    boundaries = points | {path} if os.path.ismount(path) else points
    return not any(point != parent and os.path.commonpath((parent, point)) == parent
                   and os.path.commonpath((point, path)) == point for point in boundaries)


def _aggregate(result: ScanResult, started: float, options: ScanOptions, *, ordered: bool = True) -> ScanResult:
    root = result.root
    root.size = sum(child.size for child in root.children)
    root.allocated = sum(child.allocated for child in root.children)
    root.file_count = sum(child.file_count for child in root.children)
    root.dir_count = sum(child.dir_count + 1 for child in root.children)
    root.modified = max((child.modified for child in root.children), default=0)
    if ordered:
        root.children.sort(key=lambda child: (-child.size, child.name))
    result.elapsed = time.monotonic() - started
    result.warnings = sorted(set(result.warnings))
    result.hard_links = account_hard_links(root) if options.count_hard_links else None
    return result


def scan_roots(paths: Sequence[str | os.PathLike[str]], *, options: ScanOptions | None = None,
               progress: ProgressCallback | None = None, cancel: threading.Event | None = None,
               on_root: RootCallback | None = None, pause: threading.Event | None = None) -> ScanResult:
    """Scan explicit roots sequentially under one pathless node, with bounded ordinary worker pools.

    Exact duplicate and overlapping ordinary paths are collapsed; explicit mounted scopes remain
    independent because the normal scanner never traverses those boundaries. A failed root remains
    an error-bearing child, rather than an empty successful folder. Cancellation preserves scanned,
    active partial and still-pending roots. Callbacks run on the calling thread; active crawlers join.
    Hard-link accounting is applied once over all observed roots, never independently per folder.
    The virtual root grants no filesystem operation authority or aggregate OS capacity.
    """
    normalized = _roots(paths)
    options = options or ScanOptions()
    started = time.monotonic()
    virtual = Node("", True, children=[])
    virtual.children = [Node(path, True, parent=virtual, error=NOT_SCANNED, children=[]) for path in normalized]
    result = ScanResult(virtual)
    if on_root is not None:
        on_root(virtual)
    for position, path in enumerate(normalized):
        if cancel is not None and cancel.is_set():
            raise ScanCancelledError(_aggregate(result, started, options))
        previous = virtual.file_count, virtual.dir_count, virtual.size
        def attach(root: Node, slot: int = position) -> None:
            root.parent = virtual
            virtual.children[slot] = root
        def report(value: ScanProgress, previous: tuple[int, int, int] = previous) -> None:
            if progress is not None:
                progress(ScanProgress(previous[0] + value.files, previous[1] + value.folders,
                                      previous[2] + value.size, value.current))
        try:
            part = scan(path, options=replace(options, count_hard_links=False), progress=report,
                        cancel=cancel, on_root=attach, pause=pause)
        except ScanCancelledError as stopped:
            if stopped.partial is not None:
                result.errors.extend(stopped.partial.errors)
                result.warnings.extend(stopped.partial.warnings)
            raise ScanCancelledError(_aggregate(result, started, options)) from None
        except OSError as error:
            virtual.children[position].error = str(error)
            result.errors.append((path, str(error)))
        else:
            result.errors.extend(part.errors)
            result.warnings.extend(part.warnings)
        _aggregate(result, started, replace(options, count_hard_links=False), ordered=False)
    return _aggregate(result, started, options)
