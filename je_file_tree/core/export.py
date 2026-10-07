"""Save scan results as CSV or JSON.

CSV files are written as UTF-8 with a byte-order mark so that Excel shows
non-English file names correctly when the file is double-clicked. Every file
is written to a temporary sibling first and then moved into place, so an
interrupted export never leaves a half-written file under the chosen name.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
import time
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, TextIO

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

FOLDER_COLUMNS = ("path", "size_bytes", "allocated_bytes", "share_of_parent", "files", "folders", "modified",
                  "error")
FILE_COLUMNS = ("path", "size_bytes", "allocated_bytes", "modified", "accessed", "created")
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
    rows = ([node.path, node.size, node.allocated, _iso_time(node.modified), _iso_time(node.accessed or 0.0),
             _iso_time(node.created or 0.0)] for node in files)
    return _write_csv(target, FILE_COLUMNS, rows)


def export_table_csv(header: Sequence[str], rows: Iterable[Sequence[str]],
                     target: str | os.PathLike[str]) -> int:
    """Atomically save displayed table text as UTF-8/BOM CSV, escaping spreadsheet formulas."""
    return _write_csv(target, tuple(spreadsheet_text(cell) for cell in header),
                      ([spreadsheet_text(cell) for cell in row] for row in rows))


def spreadsheet_text(cell: str) -> str:
    """Prefix text that a spreadsheet could interpret as an executable formula."""
    dangerous = cell.startswith(('\t', '\r', '\n')) or cell.lstrip().startswith(('=', '+', '-', '@'))
    return "'" + cell if dangerous else cell


def export_json(root: Node, target: str | os.PathLike[str], max_depth: int | None = None) -> None:
    """Write the folder tree (files left out) as nested JSON, down to ``max_depth`` levels.

    The file doubles as a saved scan to compare a later scan with (``core/compare.py``); ``saved`` is
    when it was written.
    """
    header = json.dumps({"format": JSON_FORMAT, "saved": _iso_time(time.time())}, ensure_ascii=False)
    with _atomic_file(target, encoding="utf-8") as stream:
        stream.write(header[:-1] + ', "root": ')
        stream.writelines(_folder_json(root, max_depth))
        stream.write("}\n")


def _folders(root: Node, max_depth: int | None) -> Iterable[Node]:
    stack = [(root, 0)]
    while stack:
        give_way()
        node, depth = stack.pop()
        yield node
        if max_depth is not None and depth >= max_depth:
            continue
        stack.extend((child, depth + 1) for child in reversed(node.children)
                     if child.is_dir and not child.is_link)


def _folder_json(root: Node, max_depth: int | None) -> Iterator[str]:
    """Stream nested folders with a depth-sized stack, without a second tree or recursive JSON encoder."""
    stack: list[tuple[Iterator[Node], int]] = []
    node: Node | None = root
    depth = 0
    while node is not None:
        give_way()
        fields: dict[str, Any] = dict(name=node.name, size=node.size, allocated=node.allocated,
                                     files=node.file_count, folders=node.dir_count, modified=_iso_time(node.modified))
        if node.error:
            fields["error"] = node.error
        children = iter(child for child in node.children if child.is_dir and not child.is_link)
        first = next(children, None) if max_depth is None or depth < max_depth else None
        encoded = json.dumps(fields, ensure_ascii=False)
        if first is not None:
            yield encoded[:-1] + ', "children": ['
            stack.append((children, depth))
            node, depth = first, depth + 1
            continue
        yield encoded
        node = None
        while stack and node is None:
            children, parent_depth = stack[-1]
            node = next(children, None)
            if node is None:
                stack.pop()
                yield "]}"
            else:
                depth = parent_depth + 1
                yield ", "


def _iso_time(timestamp: float) -> str:
    if timestamp <= 0:
        return ""
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return ""


def _write_csv(target: str | os.PathLike[str], header: tuple[str, ...],
               rows: Iterable[list[Any]]) -> int:
    count = 0
    with _atomic_file(target, encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


@contextmanager
def _atomic_file(target: str | os.PathLike[str], *, encoding: str) -> Iterator[TextIO]:
    """Write to a temporary sibling, replacing the destination only after a successful close."""
    target = os.fspath(target)
    folder = os.path.dirname(os.path.abspath(target))
    handle, temporary = tempfile.mkstemp(prefix=".file-tree-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding=encoding, newline="") as stream:
            yield stream
        os.replace(temporary, target)
    except BaseException:
        os.unlink(temporary)
        raise
