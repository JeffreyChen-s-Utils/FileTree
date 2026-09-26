"""Save scan results as CSV or JSON.

CSV files are written as UTF-8 with a byte-order mark so that Excel shows
non-English file names correctly when the file is double-clicked. Every file
is written to a temporary sibling first and then moved into place, so an
interrupted export never leaves a half-written file under the chosen name.
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from je_file_tree.core.node import Node

FOLDER_COLUMNS = ("path", "size_bytes", "allocated_bytes", "share_of_parent", "files", "folders", "modified",
                  "error")
FILE_COLUMNS = ("path", "size_bytes", "allocated_bytes", "modified")
JSON_FORMAT = "file-tree/1"  # also what a saved scan must say to be compared (core/compare.py)


def export_folders_csv(root: Node, target: str | os.PathLike[str],
                       max_depth: int | None = None) -> int:
    """Write one row per folder (``root`` included, down to ``max_depth`` levels); return the row count."""
    rows = ([node.path, node.size, node.allocated, round(node.share_of_parent(), 6), node.file_count,
             node.dir_count, _iso_time(node.modified), node.error or ""]
            for node in _folders(root, max_depth))
    return _write_csv(target, FOLDER_COLUMNS, rows)


def export_files_csv(files: Iterable[Node], target: str | os.PathLike[str]) -> int:
    """Write one row per file in ``files``, in the given order; return the row count."""
    rows = ([node.path, node.size, node.allocated, _iso_time(node.modified)] for node in files)
    return _write_csv(target, FILE_COLUMNS, rows)


def export_json(root: Node, target: str | os.PathLike[str], max_depth: int | None = None) -> None:
    """Write the folder tree (files left out) as nested JSON, down to ``max_depth`` levels.

    The file doubles as a saved scan to compare a later scan with (``core/compare.py``); ``saved`` is
    when it was written.
    """
    document = {"format": JSON_FORMAT, "saved": _iso_time(time.time()), "root": _folder_json(root, max_depth)}
    _write_atomically(target, json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")


def _folders(root: Node, max_depth: int | None) -> Iterable[Node]:
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        yield node
        if max_depth is not None and depth >= max_depth:
            continue
        stack.extend((child, depth + 1) for child in reversed(node.children)
                     if child.is_dir and not child.is_link)


def _folder_json(root: Node, max_depth: int | None) -> dict[str, Any]:
    """The JSON object for ``root``, built without recursion so deep trees cannot overflow."""
    top: dict[str, Any] = {}
    stack: list[tuple[Node, dict[str, Any], int]] = [(root, top, 0)]
    while stack:
        node, target, depth = stack.pop()
        target.update(name=node.name, size=node.size, allocated=node.allocated, files=node.file_count,
                      folders=node.dir_count, modified=_iso_time(node.modified))
        if node.error:
            target["error"] = node.error
        if max_depth is not None and depth >= max_depth:
            continue
        children = [child for child in node.children if child.is_dir and not child.is_link]
        if children:
            target["children"] = [{} for _ in children]
            stack.extend((child, slot, depth + 1)
                         for child, slot in zip(children, target["children"], strict=True))
    return top


def _iso_time(timestamp: float) -> str:
    if timestamp <= 0:
        return ""
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return ""


def _write_csv(target: str | os.PathLike[str], header: tuple[str, ...],
               rows: Iterable[list[Any]]) -> int:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    count = 0
    for row in rows:
        writer.writerow(row)
        count += 1
    _write_atomically(target, buffer.getvalue(), encoding="utf-8-sig")
    return count


def _write_atomically(target: str | os.PathLike[str], text: str, *, encoding: str) -> None:
    """Write ``text`` to a temporary file next to ``target`` and move it into place."""
    target = os.fspath(target)
    folder = os.path.dirname(os.path.abspath(target))
    handle, temporary = tempfile.mkstemp(prefix=".file-tree-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding=encoding, newline="") as stream:
            stream.write(text)
        os.replace(temporary, target)
    except BaseException:
        os.unlink(temporary)
        raise
