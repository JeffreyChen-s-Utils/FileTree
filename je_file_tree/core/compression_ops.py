"""Confirmed, exact-file compact operations; never native recursion or wildcard expansion."""

from __future__ import annotations

import contextlib
import ctypes
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

from je_file_tree.core.compression import file_system
from je_file_tree.core.node import Node
from je_file_tree.core.protected import protected_places, protection_of
from je_file_tree.core.snapshot import pack_snapshot, stable_snapshot, unpack_snapshot
from je_file_tree.core.system_files import system_file
from je_file_tree.core.windows_allocation import file_allocation

MODES = ("ntfs", "xpress8k", "uncompress")
_UNAVAILABLE = 0x2 | 0x4 | 0x200 | 0x400 | 0x1000 | 0x40000 | 0x400000
_MAX_OUTPUT = 8192
_TIMEOUT = 120
_LIMIT = 1000
_DRIVE_LENGTH = 2
_FIXED_DRIVE = 3


@dataclass(frozen=True, slots=True)
class CompressionResult:
    """Per-command completion counts and known allocation totals; cancellation may leave changes."""

    attempted: int
    completed: int
    before: int
    after: int
    unknown: int
    failures: tuple[tuple[str, str], ...]
    canceled: bool


def compress_files(root: Node, files: Sequence[Node], mode: str, *, cancel: threading.Event | None = None,
                   progress: Callable[[int, int], None] | None = None) -> CompressionResult:
    """Operate only approved recorded files, pinned against rename/delete with all ancestors.

    Requires Windows/current NTFS, unchanged recorded snapshots and single-link regular local files.
    Protected, sparse, hidden/system and known cloud/link paths are rejected. Never sets directory
    compression flags or uses /s/wildcards. Stop terminates the current command and preserves partial
    results; no rollback is promised. Native commands may read payloads only after caller confirmation.
    """
    if sys.platform != "win32" or mode not in MODES or root.is_link or not root.is_dir:
        raise ValueError("Unsupported compression scope or mode")
    if len(files) > _LIMIT or len({id(node) for node in files}) != len(files):
        raise ValueError("Review at most 1000 distinct recorded files")
    stop = cancel if cancel is not None else threading.Event()
    program = _compact_program()
    attempted = completed = before = after = unknown = 0
    failures: list[tuple[str, str]] = []
    for node in files:
        if stop.is_set():
            break
        attempted += 1
        try:
            prior, later, success, message = _operate(root, node, mode, program, stop)
            if prior is None or later is None:
                unknown += 1
            else:
                before += prior
                after += later
            completed += success
            if message:
                failures.append((node.path, message))
        except (OSError, ValueError) as exc:
            failures.append((node.path, str(exc)))
            unknown += 1
        if progress is not None:
            progress(attempted, len(files))
    return CompressionResult(attempted, completed, before, after, unknown, tuple(failures), stop.is_set())


def _operate(root: Node, node: Node, mode: str, program: str,
             cancel: threading.Event) -> tuple[int | None, int | None, bool, str]:
    if not _approved(root, node) or node.is_dir or node.is_link or node.snapshot is None or node.error:
        raise ValueError("Not an approved recorded file")
    with _pinned_path(node.path):
        _validate_root(root)
        info = os.lstat(node.path)
        _validate(node, info)
        if file_system(root.path) != "NTFS" or file_system(node.path) != "NTFS":
            raise ValueError("Current NTFS scope could not be confirmed")
        prior = file_allocation(node.path, info)
        if prior is None:
            raise ValueError("Current allocation/identity could not be confirmed")
        messages: list[str] = []
        success = True
        for arguments in _arguments(mode):
            if cancel.is_set():
                success = False
                break
            code, output = _run(program, [*arguments, node.path], cancel)
            success &= code == 0
            if code != 0:
                messages.append(output or f"compact exit {code}")
        current = os.lstat(node.path)
        # Compression can change metadata; retain identity, size and modification-time checks.
        if ((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                != (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)):
            return prior, None, False, "File changed during compression; rescan required"
        later = file_allocation(node.path, current)
        return prior, later, success and not cancel.is_set(), "\n".join(messages)


def _approved(root: Node, node: Node) -> bool:
    ancestor = node.parent
    while ancestor is not None and ancestor is not root:
        ancestor = ancestor.parent
    scope, path = os.path.normcase(os.path.abspath(root.path)), os.path.normcase(os.path.abspath(node.path))
    return ancestor is root and os.path.commonpath((scope, path)) == scope


def _validate_root(root: Node) -> None:
    if root.snapshot is None:
        raise ValueError("Recorded folder identity unavailable")
    recorded = unpack_snapshot(root.snapshot)
    current = os.lstat(root.path)
    if (not stat.S_ISDIR(current.st_mode) or not current.st_ino
            or (current.st_dev, current.st_ino) != recorded.identity
            or getattr(current, "st_file_attributes", 0) & (0x400 | 0x1000 | 0x40000 | 0x400000)):
        raise ValueError("Recorded folder changed or became unavailable")


def _validate(node: Node, info: os.stat_result) -> None:
    if (not stat.S_ISREG(info.st_mode) or not info.st_ino or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & _UNAVAILABLE
            or stable_snapshot(pack_snapshot(info)) != stable_snapshot(node.snapshot)):
        raise ValueError("Changed, linked, sparse, hidden/system or unavailable file")
    if protection_of(node.path, protected_places()) is not None or system_file(node.path) is not None:
        raise ValueError("Protected or system-managed file")


@contextlib.contextmanager
def _pinned_path(path: str) -> Iterator[None]:
    normalized = os.path.abspath(path)
    drive, tail = os.path.splitdrive(normalized)
    if (len(drive) != _DRIVE_LENGTH or drive[1] != ":" or not tail.startswith("\\")
            or any(char in tail for char in "*?:\0")):
        raise ValueError("Only exact local-drive paths are supported")
    parts = tail.strip("\\").split("\\")
    kernel = _kernel()
    if kernel.GetDriveTypeW(drive + "\\") != _FIXED_DRIVE:
        raise ValueError("Only fixed local NTFS drives are supported")
    with contextlib.ExitStack() as stack:
        current = drive + "\\"
        stack.enter_context(_pin(kernel, current))
        for part in parts:
            current = os.path.join(current, part)
            stack.enter_context(_pin(kernel, current))
        yield


@contextlib.contextmanager
def _pin(kernel, path: str) -> Iterator[None]:
    prior = os.lstat(path)
    if getattr(prior, "st_file_attributes", 0) & (0x400 | 0x1000 | 0x40000 | 0x400000):
        raise ValueError("Linked or cloud ancestor/file")
    handle = kernel.CreateFileW(path, 0x80000000, 3, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        current = os.lstat(path)
        if stable_snapshot(pack_snapshot(prior)) != stable_snapshot(pack_snapshot(current)):
            raise ValueError("Path changed while pinning")
        yield
    finally:
        kernel.CloseHandle(handle)


def _arguments(mode: str) -> tuple[tuple[str, ...], ...]:
    if mode == "uncompress":
        return (("/u", "/i", "/q"), ("/u", "/exe", "/i", "/q"))
    arguments = ("/c", "/i", "/q")
    return (arguments + (("/exe:xpress8k",) if mode == "xpress8k" else ()),)


def _run(program: str, arguments: list[str], cancel: threading.Event) -> tuple[int, str]:
    # /q on one exact file bounds normal output; a temporary stream avoids pipe deadlocks.
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen([program, *arguments], stdout=output, stderr=subprocess.STDOUT,  # noqa: S603
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        started = time.monotonic()
        while process.poll() is None:
            if cancel.wait(0.05) or time.monotonic() - started >= _TIMEOUT:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                break
        output.seek(0)
        codepage = _kernel().GetOEMCP()
        text = output.read(_MAX_OUTPUT).decode(f"cp{codepage}", errors="replace")
        return process.returncode, text


def _compact_program() -> str:
    kernel = _kernel()
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel.GetSystemDirectoryW(buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise OSError("System directory unavailable")
    return os.path.join(buffer.value, "compact.exe")


def _kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                  ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [ctypes.c_void_p], ctypes.c_int
    kernel.GetSystemDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetSystemDirectoryW.restype = ctypes.c_uint32
    kernel.GetOEMCP.argtypes, kernel.GetOEMCP.restype = [], ctypes.c_uint32
    kernel.GetDriveTypeW.argtypes, kernel.GetDriveTypeW.restype = [ctypes.c_wchar_p], ctypes.c_uint32
    return kernel
