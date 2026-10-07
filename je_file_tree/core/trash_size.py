"""OS bin metadata, POSIX payload inventories and explicitly approved Windows native emptying."""

from __future__ import annotations

import ctypes
from collections import deque
import functools
import os
from pathlib import Path
import re
import stat
import sys
import threading

from dataclasses import dataclass
from je_file_tree.core.pacing import give_way


@dataclass(frozen=True, slots=True)
class TrashUsage:
    """Reported/logical payload bytes and top-level items; incomplete data never means an empty bin."""

    size: int
    count: int
    complete: bool
    error: str = ""


class _QueryInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("size", ctypes.c_int64), ("count", ctypes.c_int64)]


@functools.lru_cache(maxsize=1)
def _shell32():
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.SHQueryRecycleBinW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(_QueryInfo)]
    shell.SHQueryRecycleBinW.restype = ctypes.c_int32
    shell.SHEmptyRecycleBinW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
    shell.SHEmptyRecycleBinW.restype = ctypes.c_int32
    return shell


def _windows_usage(root: str) -> TrashUsage:
    if not re.fullmatch(r"[A-Za-z]:[/\\]", root):
        return TrashUsage(0, 0, False, "Recycle Bin query requires a local drive-letter root")
    info = _QueryInfo()
    info.cbSize = ctypes.sizeof(info)
    result = _shell32().SHQueryRecycleBinW(root, ctypes.byref(info))
    if result != 0 or info.size < 0 or info.count < 0:
        return TrashUsage(0, 0, False, f"SHQueryRecycleBinW failed (0x{result & 0xffffffff:08x})")
    return TrashUsage(info.size, info.count, True)


def empty_windows_bin(root: str, approved: TrashUsage) -> None:
    """Permanently empty one drive's OS bin, only after the GUI's two explicit questions.

    Reject nonlocal/nonroot scopes, incomplete or empty approvals and changed query totals.
    Native deletion cannot be canceled once started. No arbitrary filesystem paths are removed.
    """
    if sys.platform != "win32" or not re.fullmatch(r"[A-Za-z]:[/\\]", root):
        raise ValueError("Emptying requires one Windows local drive-letter root")
    if not approved.complete or approved.count <= 0 or approved.size < 0:
        raise ValueError("No complete nonempty Recycle Bin approval")
    current = _windows_usage(root)
    if current != approved:
        raise ValueError("Recycle Bin changed or became unavailable; refresh and review again")
    result = _shell32().SHEmptyRecycleBinW(None, root, 0x7)
    if result != 0:
        raise OSError(f"SHEmptyRecycleBinW failed (0x{result & 0xffffffff:08x}); refresh to inspect remaining items")


def _is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _locations(root: Path, home: Path, data_home: Path, uid: int, platform: str) -> list[Path]:
    device = root.stat().st_dev
    paths = []
    if platform == "darwin":
        if home.stat().st_dev == device:
            paths.append(home / ".Trash")
        paths.append(root / ".Trashes" / str(uid))
        return paths
    if not data_home.is_absolute():
        data_home = home / ".local" / "share"
    ancestor = data_home
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if ancestor.stat().st_dev == device:
        paths.append(data_home / "Trash" / "files")
    shared = root / ".Trash"
    try:
        info = shared.lstat()
    except FileNotFoundError:
        info = None
    if info is not None and not _is_link(info) and stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX:
        paths.append(shared / str(uid) / "files")
    paths.append(root / f".Trash-{uid}" / "files")
    return paths


def _payload_root(root: Path) -> os.stat_result | TrashUsage:
    try:
        parent = root.parent.lstat()
        if _is_link(parent) or not stat.S_ISDIR(parent.st_mode):
            return TrashUsage(0, 0, False, "Trash parent is a link or not a directory")
        info = root.lstat()
    except FileNotFoundError:
        return TrashUsage(0, 0, True)
    except OSError as error:
        return TrashUsage(0, 0, False, str(error))
    if _is_link(info) or not stat.S_ISDIR(info.st_mode):
        return TrashUsage(0, 0, False, "Trash payload folder is a link or not a directory")
    return info


def _inspect_entry(entry: os.DirEntry[str], device: int, stack: list[Path], problems: deque[str]) -> int:
    child = entry.stat(follow_symlinks=False)
    if not child.st_dev:  # Some directory listings omit identity; a metadata stat supplies it.
        child = os.stat(entry.path, follow_symlinks=False)
    if _is_link(child):
        return child.st_size
    if child.st_dev != device:
        problems.append("Different-device boundary inside Trash")
    elif stat.S_ISDIR(child.st_mode):
        stack.append(Path(entry.path))
    elif stat.S_ISREG(child.st_mode):
        return child.st_size
    else:
        problems.append("Special entry inside Trash")
    return 0


def _payload_usage(root: Path, cancel: threading.Event | None) -> TrashUsage | None:
    info = _payload_root(root)
    if isinstance(info, TrashUsage):
        return info
    size = count = 0
    problems, stack = deque(maxlen=3), [root]
    while stack:
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        folder = stack.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if cancel is not None and cancel.is_set():
                        return None
                    count += int(folder == root)
                    try:
                        size += _inspect_entry(entry, info.st_dev, stack, problems)
                    except OSError as error:
                        problems.append(str(error))
        except OSError as error:
            problems.append(str(error))
    return TrashUsage(size, count, not problems, "; ".join(problems))


def trash_usage(root: str, *, cancel: threading.Event | None = None) -> TrashUsage | None:
    """Query a mounted root without opening payload contents or modifying any Trash entry.

    POSIX reports logical payload bytes, excluding directory/receipt metadata and shared allocation.
    None denotes explicit cancellation; permission/API errors return incomplete known data.
    """
    if cancel is not None and cancel.is_set():
        return None
    if sys.platform == "win32":
        return _windows_usage(root)
    if sys.platform != "darwin" and not sys.platform.startswith("linux"):
        return TrashUsage(0, 0, False, "Trash inventory is unavailable on this platform")
    try:
        home = Path.home()
        locations = _locations(Path(root), home, Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")),
                               os.getuid(), sys.platform)
    except OSError as error:
        return TrashUsage(0, 0, False, str(error))
    size = count = 0
    errors = []
    for path in dict.fromkeys(locations):
        usage = _payload_usage(path, cancel)
        if usage is None:
            return None
        size += usage.size
        count += usage.count
        if not usage.complete:
            errors.append(usage.error)
    return TrashUsage(size, count, not errors, "; ".join(errors[:3]))
