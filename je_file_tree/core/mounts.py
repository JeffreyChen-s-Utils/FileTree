"""Linux mount-table boundaries, including same-device bind mounts that stat/ismount cannot identify."""

from __future__ import annotations

import os
import posixpath
import re
import sys
from pathlib import Path

MOUNT_BOUNDARY = "mount boundary: not traversed"
_MOUNTINFO = Path("/proc/self/mountinfo")
_MAX_TABLE = 8 * 1024 * 1024
_ESCAPES = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}
_ESCAPE_PATTERN = re.compile(r"\\(040|011|012|134)")
_MIN_PREFIX = 6
_SUFFIX_FIELDS = 4


def parse_mountinfo(contents: str) -> frozenset[str]:
    """Decode mount points exactly once, preserving escaped whitespace/backslashes and Unicode."""
    points = set()
    for line in contents.splitlines():
        fields = line.split()
        try:
            separator = fields.index("-", _MIN_PREFIX)
        except ValueError as error:
            raise ValueError("Malformed Linux mount table") from error
        if len(fields) < separator + _SUFFIX_FIELDS or not fields[4].startswith("/"):
            raise ValueError("Malformed Linux mount table")
        if re.search(r"\\(?!040|011|012|134)", fields[4]):
            raise ValueError("Invalid Linux mount path escape")
        point = _ESCAPE_PATTERN.sub(lambda match: _ESCAPES[match[1]], fields[4])
        if "\0" in point:
            raise ValueError("Invalid Linux mount path")
        points.add(posixpath.normpath("/" + point.lstrip("/")))
    if not points:
        raise ValueError("Empty Linux mount table")
    return frozenset(points)


def mount_points() -> frozenset[str]:
    """Read the current Linux mount namespace once per scan; refuse unknown tables instead of crossing blindly."""
    if not sys.platform.startswith("linux"):
        return frozenset()
    with _MOUNTINFO.open(encoding="utf-8", errors="surrogateescape") as stream:
        contents = stream.read(_MAX_TABLE + 1)
    if len(contents) > _MAX_TABLE:
        raise OSError("Linux mount table exceeds the scan limit")
    try:
        return frozenset(os.path.normpath(path) for path in parse_mountinfo(contents))
    except ValueError as error:
        raise OSError("Linux mount boundaries could not be determined") from error


def boundary_path(path: str) -> str:
    """Normalize exact directory paths, including Linux's equivalent multiple leading slashes."""
    normalized = os.path.normpath(path)
    return "/" + normalized.lstrip("/") if normalized.startswith("/") else normalized


def rebase_mount_points(root: str, points: frozenset[str]) -> frozenset[str]:
    """Map namespace paths to an explicitly selected root reached through ancestor aliases."""
    if not points:
        return points
    selected, actual = boundary_path(root), boundary_path(os.path.realpath(root))
    if selected == actual:
        return points
    prefix = actual.rstrip(os.sep) + os.sep
    return frozenset(boundary_path(os.path.join(selected, os.path.relpath(point, actual)))
                     for point in points if point == actual or point.startswith(prefix))
