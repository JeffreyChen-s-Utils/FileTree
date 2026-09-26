"""Compare a scan with one saved earlier: the JSON that Export → Folder tree (JSON) writes.

Folders are matched by their path below the scanned folder (case-insensitive where the file system
is, see ``os.path.normcase``), so a scan can also be compared with a copy of the same tree elsewhere,
such as a backup.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from je_file_tree.core.export import JSON_FORMAT
from je_file_tree.core.node import Node


class SavedScanError(ValueError):
    """The file is not a saved scan that FileTree can read."""


@dataclass(frozen=True, slots=True)
class SavedFolder:
    """One folder of a saved scan: its path below the scanned folder (``""`` for that folder) and its size."""

    path: str
    size: int


@dataclass(frozen=True, slots=True)
class SavedScan:
    """A saved scan: the folder scanned, when it was saved (ISO 8601, ``""`` if unknown) and its folders."""

    root: str
    saved: str
    folders: dict[str, SavedFolder]  # keyed by ``folder_key(path)``

    @property
    def size(self) -> int:
        """The size of the scanned folder then."""
        top = self.folders.get("")
        return top.size if top is not None else 0


@dataclass(frozen=True, slots=True)
class FolderChange:
    """A folder that grew, shrank, appeared (``before`` is None) or disappeared (``node`` and ``after`` are None)."""

    path: str
    node: Node | None
    before: int | None
    after: int | None

    @property
    def change(self) -> int:
        """How much it grew (negative when it shrank)."""
        return (self.after or 0) - (self.before or 0)


def folder_key(path: str) -> str:
    """The key that matches a folder path below the scanned folder across scans."""
    return os.path.normcase(path.replace("\\", "/").strip("/")).replace("\\", "/")


def load_saved(file: str | os.PathLike[str]) -> SavedScan:
    """Read a saved scan; ``SavedScanError`` (with the reason) when the file is not one."""
    try:
        document = json.loads(Path(file).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SavedScanError(str(error)) from error
    if not isinstance(document, dict) or document.get("format") != JSON_FORMAT:
        raise SavedScanError(f"not a FileTree scan (no \"format\": \"{JSON_FORMAT}\")")
    top = document.get("root")
    if not isinstance(top, dict) or not isinstance(top.get("name"), str):
        raise SavedScanError("the scan has no root folder")
    saved = document.get("saved")
    return SavedScan(top["name"], saved if isinstance(saved, str) else "", _folders_of(top))


def _folders_of(top: dict[str, Any]) -> dict[str, SavedFolder]:
    """Every folder of the saved tree by key, read without recursion and checked on the way."""
    folders: dict[str, SavedFolder] = {}
    stack: list[tuple[dict[str, Any], str]] = [(top, "")]
    while stack:
        entry, path = stack.pop()
        where = path or top["name"]
        folders[folder_key(path)] = SavedFolder(path, _size_of(entry, where))
        stack.extend((child, f"{path}/{child['name']}" if path else child["name"])
                     for child in _children_of(entry, where))
    return folders


def _size_of(entry: dict[str, Any], where: str) -> int:
    """A saved folder's size: a whole number of bytes, not negative (JSON ``true`` is not a size)."""
    size = entry.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise SavedScanError(f"folder {where!r} has no valid size")
    return size


def _children_of(entry: dict[str, Any], where: str) -> list[dict[str, Any]]:
    """A saved folder's subfolders: a list of objects that each have a name."""
    children = entry.get("children", [])
    if not isinstance(children, list):
        raise SavedScanError(f"folder {where!r} has invalid children")
    for child in children:
        if not isinstance(child, dict) or not isinstance(child.get("name"), str) or not child["name"]:
            raise SavedScanError(f"folder {where!r} has a child without a name")
    return children


def compare(root: Node, saved: SavedScan) -> list[FolderChange]:
    """Every folder that changed since ``saved``: the biggest growth first, the biggest shrink last."""
    changes: list[FolderChange] = []
    seen: set[str] = set()
    stack: list[tuple[Node, str]] = [(root, "")]
    while stack:
        folder, path = stack.pop()
        key = folder_key(path)
        seen.add(key)
        before = saved.folders.get(key)
        if before is None or before.size != folder.size:
            changes.append(FolderChange(path, folder, None if before is None else before.size, folder.size))
        stack.extend((child, f"{path}/{child.name}" if path else child.name)
                     for child in folder.children if child.is_dir and not child.is_link)
    changes.extend(FolderChange(gone.path, None, gone.size, None)
                   for key, gone in saved.folders.items() if key not in seen)
    changes.sort(key=lambda change: (-change.change, change.path.lower()))
    return changes
