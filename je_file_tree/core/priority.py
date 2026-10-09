"""Best-effort CPU and I/O priority changes scoped to disposable scan worker threads."""

from __future__ import annotations

import ctypes
import os
import platform
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager

_BACKGROUND_BEGIN = 0x10000
_BACKGROUND_END = 0x20000
_NICE = 10
_POINTER_32_BYTES = 4
_BEST_EFFORT_LOW = (2 << 13) | 7
_IOPRIO_SYSCALL = {"x86_64": 251, "amd64": 251, "i386": 289, "i686": 289, "aarch64": 30, "arm64": 30}


@contextmanager
def background_priority(enabled: bool) -> Iterator[list[str]]:
    """Lower only this disposable worker; yield failures without making a readable scan fail.

    Windows restores background mode on exit. Linux nice/I/O values end with the worker thread;
    unprivileged callers cannot restore nice, so never use this on a GUI or reusable pool thread.
    Unsupported platforms report a warning. I/O scheduling effects depend on the device scheduler.
    """
    warnings: list[str] = []
    windows_started = False
    if enabled:
        if sys.platform == "win32":
            try:
                _windows_mode(_BACKGROUND_BEGIN)
                windows_started = True
            except OSError as error:
                warnings.append(str(error))
        elif sys.platform.startswith("linux"):
            warnings.extend(_linux_priority())
        else:
            warnings.append("CPU/I/O background priority is unsupported on this platform")
    try:
        yield warnings
    finally:
        if windows_started:
            try:
                _windows_mode(_BACKGROUND_END)
            except OSError as error:
                warnings.append(str(error))


def _windows_mode(mode: int) -> None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentThread.argtypes = []
    kernel.GetCurrentThread.restype = ctypes.c_void_p
    kernel.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
    kernel.SetThreadPriority.restype = ctypes.c_int
    if not kernel.SetThreadPriority(kernel.GetCurrentThread(), mode):
        raise ctypes.WinError(ctypes.get_last_error())


def _linux_priority() -> list[str]:
    warnings = []
    tid = threading.get_native_id()
    try:
        current = os.getpriority(os.PRIO_PROCESS, tid)
        os.setpriority(os.PRIO_PROCESS, tid, max(current, _NICE))
    except OSError as error:
        warnings.append(f"CPU priority: {error}")
    try:
        _linux_io(tid)
    except OSError as error:
        warnings.append(f"I/O priority: {error}")
    return warnings


def _linux_io(tid: int) -> None:
    machine = platform.machine().lower()
    if ctypes.sizeof(ctypes.c_void_p) == _POINTER_32_BYTES and machine in ("x86_64", "amd64"):
        machine = "i386"
    number = _IOPRIO_SYSCALL.get(machine)
    if number is None:
        raise OSError("unsupported Linux syscall architecture")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    # Kernel ABI: ioprio_set(IOPRIO_WHO_PROCESS, tid, best-effort class / lowest priority).
    if libc.syscall(ctypes.c_long(number), ctypes.c_int(1), ctypes.c_int(tid),
                    ctypes.c_int(_BEST_EFFORT_LOW)) == -1:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))
