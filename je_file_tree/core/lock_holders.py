"""Read-only, bounded diagnostics for programs holding a failed Trash entry open."""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

_MAX_FILES = 256
_MORE_DATA = 234
_RETRIES = 3


@dataclass(frozen=True, slots=True)
class Holder:
    """A process observed using at least one of the registered files."""

    pid: int
    name: str


@dataclass(slots=True)
class LockReport:
    """Observed holders; incomplete/error explicitly distinguish missing visibility from no results."""

    holders: list[Holder] = field(default_factory=list)
    incomplete: bool = False
    error: str | None = None


class _UniqueProcess(ctypes.Structure):
    _fields_ = [("pid", wintypes.DWORD), ("started", wintypes.FILETIME)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [("process", _UniqueProcess), ("name", wintypes.WCHAR * 256),
                ("service", wintypes.WCHAR * 64), ("kind", ctypes.c_int),
                ("status", wintypes.ULONG), ("session", wintypes.DWORD), ("restartable", wintypes.BOOL)]


def find_holders(node: Node, *, cancel: threading.Event | None = None) -> LockReport:
    """Diagnose a failed entry off the UI thread, without closing or restarting any process.

    Folder diagnostics inspect at most 256 scanned files. Results are observations, not proof that a
    holder caused the failure; directory handles, permissions and races can prevent attribution.
    """
    paths, incomplete = _paths(node, cancel)
    if not paths or (cancel is not None and cancel.is_set()):
        return LockReport(incomplete=True)
    try:
        if sys.platform == "win32":
            report = _windows(paths)
        elif sys.platform.startswith("linux"):
            report = _linux(paths, cancel)
        else:
            return LockReport(incomplete=True, error="unsupported")
    except OSError as error:
        return LockReport(incomplete=True, error=str(error))
    report.incomplete |= incomplete or (cancel is not None and cancel.is_set())
    return report


def _paths(node: Node, cancel: threading.Event | None) -> tuple[list[str], bool]:
    paths: list[str] = []
    incomplete = node.is_dir  # Directory handles themselves are not covered by Restart Manager.
    for entry in node.iter_nodes():
        if cancel is not None and cancel.is_set():
            return paths, True
        if entry.is_dir:
            give_way()
        elif not entry.is_link and entry.error is None:
            if len(paths) == _MAX_FILES:
                return paths, True
            paths.append(entry.path)
        incomplete |= entry.error is not None or entry.is_link
    return paths, incomplete


def _windows(paths: list[str]) -> LockReport:
    library = ctypes.WinDLL("Rstrtmgr", use_last_error=True)
    uint_ptr = ctypes.POINTER(wintypes.UINT)
    library.RmStartSession.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.LPWSTR]
    library.RmRegisterResources.argtypes = [wintypes.DWORD, wintypes.UINT, ctypes.POINTER(wintypes.LPCWSTR),
                                          wintypes.UINT, ctypes.POINTER(_UniqueProcess), wintypes.UINT,
                                          ctypes.POINTER(wintypes.LPCWSTR)]
    library.RmGetList.argtypes = [wintypes.DWORD, uint_ptr, uint_ptr, ctypes.POINTER(_ProcessInfo),
                                 ctypes.POINTER(wintypes.DWORD)]
    library.RmEndSession.argtypes = [wintypes.DWORD]
    for name in ("RmStartSession", "RmRegisterResources", "RmGetList", "RmEndSession"):
        getattr(library, name).restype = wintypes.DWORD
    handle = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(33)
    _check(library.RmStartSession(ctypes.byref(handle), 0, key))
    try:
        resources = (wintypes.LPCWSTR * len(paths))(*paths)
        _check(library.RmRegisterResources(handle, len(paths), resources, 0, None, 0, None))
        return _processes(library, handle)
    finally:
        _check(library.RmEndSession(handle))


def _check(status: int) -> None:
    if status:
        raise OSError(status, f"Restart Manager status {status}")


def _processes(library: object, handle: wintypes.DWORD) -> LockReport:
    needed, count, reboot = wintypes.UINT(), wintypes.UINT(), wintypes.DWORD()
    buffer = None
    for _ in range(_RETRIES):
        status = library.RmGetList(handle, ctypes.byref(needed), ctypes.byref(count),
                                   buffer, ctypes.byref(reboot))
        if status == 0:
            found = [] if buffer is None else [Holder(item.process.pid, item.name or item.service)
                                               for item in buffer[:count.value]]
            return LockReport(sorted(set(found), key=lambda holder: holder.pid))
        if status != _MORE_DATA:
            _check(status)
        buffer = (_ProcessInfo * needed.value)()
        count.value = needed.value
    return LockReport(incomplete=True, error="process_list_changed")


def _linux(paths: list[str], cancel: threading.Event | None, *, proc: Path = Path("/proc")) -> LockReport:
    identities: set[tuple[int, int]] = set()
    report = LockReport()
    for path in paths:
        try:
            info = os.stat(path, follow_symlinks=False)
            identities.add((info.st_dev, info.st_ino))
        except OSError:
            report.incomplete = True  # A failed move may also leave a path unavailable.
    with os.scandir(proc) as processes:
        for process in processes:
            if cancel is not None and cancel.is_set():
                report.incomplete = True
                break
            if process.name.isdecimal():
                give_way()
                _inspect_process(Path(process.path), identities, report, cancel)
    return report


def _inspect_process(process: Path, identities: set[tuple[int, int]], report: LockReport,
                     cancel: threading.Event | None) -> None:
    try:
        with os.scandir(process / "fd") as descriptors:
            for descriptor in descriptors:
                if cancel is not None and cancel.is_set():
                    report.incomplete = True
                    return
                try:
                    info = os.stat(descriptor.path)
                except OSError:
                    report.incomplete = True  # Descriptors can close while being inspected.
                    continue
                if (info.st_dev, info.st_ino) in identities:
                    name = (process / "comm").read_text(encoding="utf-8", errors="replace").strip()
                    report.holders.append(Holder(int(process.name), name))
                    return
    except FileNotFoundError:
        report.incomplete = True  # Processes can exit between enumeration and inspection.
    except OSError:
        report.incomplete = True  # Other users' descriptor directories may be inaccessible.
