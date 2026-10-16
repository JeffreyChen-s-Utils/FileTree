"""Read bounded wait-chain and CPU observations for a sibling child held by our parent."""

from __future__ import annotations

import argparse
import ctypes as c
from ctypes import wintypes as w
import json
import os
import sys

_THREAD_LIMIT = 16
_NODE_LIMIT = 16
_NO_MORE_FILES = 18
_THREAD_KIND = 8


class _ProcessEntry(c.Structure):
    _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD), ("heap", c.c_size_t),
                ("module", w.DWORD), ("threads", w.DWORD), ("parent", w.DWORD),
                ("priority", w.LONG), ("flags", w.DWORD), ("exe", w.WCHAR * 260)]


class _ThreadEntry(c.Structure):
    _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("tid", w.DWORD), ("pid", w.DWORD),
                ("priority", w.LONG), ("delta", w.LONG), ("flags", w.DWORD)]


class _Lock(c.Structure):
    _fields_ = [("name", w.WCHAR * 128), ("timeout", c.c_longlong), ("alertable", w.BOOL)]


class _Thread(c.Structure):
    _fields_ = [("pid", w.DWORD), ("tid", w.DWORD), ("wait_ms", w.DWORD), ("switches", w.DWORD)]


class _Object(c.Union):
    _fields_ = [("lock", _Lock), ("thread", _Thread)]


class _WaitNode(c.Structure):
    _fields_ = [("kind", c.c_int), ("status", c.c_int), ("object", _Object)]


def _api(library: object, name: str, args: list, result: object) -> object:
    function = getattr(library, name)
    function.argtypes, function.restype = args, result
    return function


class _Native:
    def __init__(self) -> None:
        kernel = c.WinDLL("kernel32", use_last_error=True)
        advance = c.WinDLL("advapi32", use_last_error=True)
        self.snapshot = _api(kernel, "CreateToolhelp32Snapshot", [w.DWORD, w.DWORD], w.HANDLE)
        self.close = _api(kernel, "CloseHandle", [w.HANDLE], w.BOOL)
        self.process_first = _api(kernel, "Process32FirstW", [w.HANDLE, c.POINTER(_ProcessEntry)], w.BOOL)
        self.process_next = _api(kernel, "Process32NextW", [w.HANDLE, c.POINTER(_ProcessEntry)], w.BOOL)
        self.thread_first = _api(kernel, "Thread32First", [w.HANDLE, c.POINTER(_ThreadEntry)], w.BOOL)
        self.thread_next = _api(kernel, "Thread32Next", [w.HANDLE, c.POINTER(_ThreadEntry)], w.BOOL)
        self.open_process = _api(kernel, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
        self.open_thread = _api(kernel, "OpenThread", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
        self.thread_pid = _api(kernel, "GetProcessIdOfThread", [w.HANDLE], w.DWORD)
        self.times = _api(kernel, "GetProcessTimes", [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4, w.BOOL)
        self.open_wait = _api(advance, "OpenThreadWaitChainSession", [w.DWORD, c.c_void_p], w.HANDLE)
        self.close_wait = _api(advance, "CloseThreadWaitChainSession", [w.HANDLE], None)
        self.wait = _api(advance, "GetThreadWaitChain", [w.HANDLE, c.c_size_t, w.DWORD, w.DWORD,
                         c.POINTER(w.DWORD), c.POINTER(_WaitNode), c.POINTER(w.BOOL)], w.BOOL)


def _entries(native: _Native, threads: bool) -> list:
    handle = native.snapshot(4 if threads else 2, 0)
    if handle == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    entry = _ThreadEntry() if threads else _ProcessEntry()
    entry.size = c.sizeof(entry)
    first, next_entry = ((native.thread_first, native.thread_next) if threads
                         else (native.process_first, native.process_next))
    values = []
    try:
        exists = first(handle, c.byref(entry))
        while exists:
            values.append((entry.pid, entry.tid) if threads else (entry.pid, entry.parent, entry.threads))
            exists = next_entry(handle, c.byref(entry))
        if c.get_last_error() != _NO_MORE_FILES:
            raise c.WinError(c.get_last_error())
    finally:
        native.close(handle)
    return values


def _cpu(native: _Native, pid: int) -> dict:
    handle = native.open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return {"error": c.get_last_error()}
    stamps = [w.FILETIME() for _ in range(4)]
    try:
        if not native.times(handle, *(c.byref(stamp) for stamp in stamps)):
            return {"error": c.get_last_error()}
        raw = [(stamp.dwHighDateTime << 32) | stamp.dwLowDateTime for stamp in stamps]
        return {"created_100ns": raw[0], "exited_100ns": raw[1], "kernel_100ns": raw[2], "user_100ns": raw[3]}
    finally:
        native.close(handle)


def _chain(native: _Native, session: int, pid: int, tid: int) -> dict:
    handle = native.open_thread(0x0800, False, tid)  # THREAD_QUERY_LIMITED_INFORMATION; pin against ID reuse
    if not handle:
        return {"tid": tid, "complete": False, "error": c.get_last_error(), "ownership_checked": False}
    try:
        owner = native.thread_pid(handle)
        if owner != pid:
            return {"tid": tid, "complete": False, "error": c.get_last_error() if not owner else 0,
                    "ownership_refused": True}
        return _wait(native, session, tid)
    finally:
        native.close(handle)


def _wait(native: _Native, session: int, tid: int) -> dict:
    nodes = (_WaitNode * _NODE_LIMIT)()
    count, cycle = w.DWORD(_NODE_LIMIT), w.BOOL()
    complete = bool(native.wait(session, 0, 0, tid, c.byref(count), nodes, c.byref(cycle)))
    error = 0 if complete else c.get_last_error()
    records = []
    for node in nodes[:min(count.value, _NODE_LIMIT)] if complete or error in (234, 565) else []:
        record = {"kind": node.kind, "status": node.status}
        if node.kind == _THREAD_KIND:
            thread = node.object.thread
            record.update(pid=thread.pid, tid=thread.tid, wait_time_raw=thread.wait_ms, switches=thread.switches)
        records.append(record)
    return {"tid": tid, "complete": complete, "error": error, "cycle": bool(cycle.value),
            "required_nodes": count.value, "nodes": records}


def observe(pid: int) -> None:
    """Refuse non-sibling targets; emit incremental records so a killed observer retains partial proof."""
    if sys.platform != "win32" or pid <= 0 or pid in (os.getpid(), os.getppid()):
        raise RuntimeError("A separate owned Windows child is required")
    native = _Native()
    matches = [entry for entry in _entries(native, False) if entry[0] == pid]
    if len(matches) != 1 or matches[0][1] != os.getppid():
        raise RuntimeError("Target is not a child of the observer's parent")
    _emit({"event": "identity", "pid": pid, "parent_pid": os.getppid(), "cpu": _cpu(native, pid),
           "reported_threads": matches[0][2]})
    tids = sorted(tid for owner, tid in _entries(native, True) if owner == pid)
    _emit({"event": "threads", "count": len(tids), "truncated": len(tids) > _THREAD_LIMIT})
    session = native.open_wait(0, None)
    if not session:
        _emit({"event": "wait-session-error", "error": c.get_last_error()})
        return
    try:
        for tid in tids[:_THREAD_LIMIT]:
            _emit({"event": "chain", **_chain(native, session, pid, tid)})
    finally:
        native.close_wait(session)
    _emit({"event": "complete", "cpu": _cpu(native, pid)})


def _emit(value: dict) -> None:
    sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> None:
    """Only observe; never suspend, debug, terminate or change the target process."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    arguments = parser.parse_args()
    try:
        observe(arguments.pid)
    except (OSError, RuntimeError) as error:
        _emit({"event": "error", "type": type(error).__name__, "message": str(error)[:512]})
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
