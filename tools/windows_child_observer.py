"""Read bounded wait-chain and CPU observations for a sibling child held by our parent."""

from __future__ import annotations

import argparse
import ctypes as c
from ctypes import wintypes as w
import json
import os
import sys
import time

_THREAD_LIMIT = 16
_STATE_LIMIT = 48  # thread-state records, oldest first: the main thread always leads
_MODULE_LIMIT = 160  # newest names in load order; a stall's pending load is at the end
_SNAP_MODULES = 0x8 | 0x10  # TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32
_NODE_LIMIT = 16
_NO_MORE_FILES = 18
_THREAD_KIND = 8
_UNIX_EPOCH_FILETIME = 116444736000000000
_SYSTEM_PROCESS_INFORMATION = 5
_INFO_LENGTH_MISMATCH = 0xC0000004 - (1 << 32)  # NTSTATUS as a signed 32-bit value
_PROCESS_BUFFER_START, _PROCESS_BUFFER_LIMIT = 1 << 20, 64 << 20
# x64 SYSTEM_PROCESS_INFORMATION: thread count, I/O counters, process ID and the thread array.
_PROCESS_THREADS, _PROCESS_ID, _PROCESS_THREAD_ARRAY = 4, 0x50, 0x100
_PROCESS_IO = {"read_operations": 0xD0, "write_operations": 0xD8, "other_operations": 0xE0,
               "read_bytes": 0xE8, "write_bytes": 0xF0, "other_bytes": 0xF8}
_THREAD_WIN32_START = 9  # ThreadQuerySetWin32StartAddress
_X64_POINTER = 8  # the offsets above are the x64 layout


class _ProcessEntry(c.Structure):
    _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD), ("heap", c.c_size_t),
                ("module", w.DWORD), ("threads", w.DWORD), ("parent", w.DWORD),
                ("priority", w.LONG), ("flags", w.DWORD), ("exe", w.WCHAR * 260)]


class _ThreadEntry(c.Structure):
    _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("tid", w.DWORD), ("pid", w.DWORD),
                ("priority", w.LONG), ("delta", w.LONG), ("flags", w.DWORD)]


class _ModuleEntry(c.Structure):
    _fields_ = [("size", w.DWORD), ("module_id", w.DWORD), ("pid", w.DWORD), ("global_usage", w.DWORD),
                ("process_usage", w.DWORD), ("base", c.c_void_p), ("base_size", w.DWORD), ("handle", w.HMODULE),
                ("name", w.WCHAR * 256), ("path", w.WCHAR * 260)]


class _SystemThread(c.Structure):
    # Fixed-width fields: Windows ULONG is 32-bit, while ctypes' c_ulong is 64-bit on LP64 test hosts.
    _fields_ = [("kernel", c.c_int64), ("user", c.c_int64), ("created", c.c_int64),
                ("wait_time", c.c_uint32), ("start", c.c_void_p), ("pid", c.c_void_p), ("tid", c.c_void_p),
                ("priority", c.c_int32), ("base_priority", c.c_int32), ("switches", c.c_uint32),
                ("state", c.c_uint32), ("wait_reason", c.c_uint32)]


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
        ntdll = c.WinDLL("ntdll")
        self.system_information = _api(ntdll, "NtQuerySystemInformation",
                                       [w.ULONG, c.c_void_p, w.ULONG, c.POINTER(w.ULONG)], w.LONG)
        self.thread_information = _api(ntdll, "NtQueryInformationThread",
                                       [w.HANDLE, w.ULONG, c.c_void_p, w.ULONG, c.POINTER(w.ULONG)], w.LONG)
        self.module_first = _api(kernel, "Module32FirstW", [w.HANDLE, c.POINTER(_ModuleEntry)], w.BOOL)
        self.module_next = _api(kernel, "Module32NextW", [w.HANDLE, c.POINTER(_ModuleEntry)], w.BOOL)
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


def _modules(native: _Native, pid: int, ranges: list | None = None) -> dict:
    """Name the target's loaded modules, in load order, from a read-only Toolhelp snapshot.

    ``ranges`` (when given) also receives every module's ``(base, size, name)`` for address lookups.
    """
    handle = native.snapshot(_SNAP_MODULES, pid)
    if handle == c.c_void_p(-1).value:
        return {"event": "modules", "error": c.get_last_error()}
    entry = _ModuleEntry()
    entry.size = c.sizeof(entry)
    names = []
    try:
        exists = native.module_first(handle, c.byref(entry))
        while exists:
            names.append(entry.name)
            if ranges is not None:
                ranges.append((entry.base or 0, entry.base_size, entry.name))
            exists = native.module_next(handle, c.byref(entry))
        error = c.get_last_error()
    finally:
        native.close(handle)
    return {"event": "modules", "count": len(names), "truncated": len(names) > _MODULE_LIMIT,
            "names": names[-_MODULE_LIMIT:], **({"error": error} if error != _NO_MORE_FILES else {})}


def _process_snapshot(native: _Native) -> c.Array | int:
    """All processes' kernel thread records (``SystemProcessInformation``), or the failing NTSTATUS."""
    size = _PROCESS_BUFFER_START
    while size <= _PROCESS_BUFFER_LIMIT:
        buffer, needed = c.create_string_buffer(size), w.ULONG()
        status = native.system_information(_SYSTEM_PROCESS_INFORMATION, buffer, size, c.byref(needed))
        if status != _INFO_LENGTH_MISMATCH:
            return buffer if status >= 0 else status
        size = max(size * 2, needed.value + (64 << 10))
    return _INFO_LENGTH_MISMATCH


def _process_entry(buffer: c.Array, pid: int) -> int | None:
    """Offset of ``pid``'s entry in a process snapshot."""
    offset = 0
    while True:
        if c.c_void_p.from_buffer(buffer, offset + _PROCESS_ID).value == pid:
            return offset
        step = c.c_uint32.from_buffer(buffer, offset).value
        if not step:
            return None
        offset += step


def _module_at(address: int | None, ranges: list) -> dict:
    for base, size, name in ranges:
        if address and base <= address < base + size:
            return {"start_module": name, "start_offset": address - base}
    return {"start_module": None}


def _win32_start(native: _Native, pid: int, tid: int) -> int | None:
    """The thread's own start routine; the kernel record usually shows only ntdll's thunk."""
    handle = native.open_thread(0x0040 | 0x0800, False, tid)  # THREAD_QUERY_(LIMITED_)INFORMATION
    if not handle:
        return None
    try:
        if native.thread_pid(handle) != pid:  # pinned handle: refuse a recycled thread ID
            return None
        start = c.c_void_p()
        status = native.thread_information(handle, _THREAD_WIN32_START, c.byref(start), c.sizeof(start), None)
        return start.value if status >= 0 else None
    finally:
        native.close(handle)


def _thread_states(native: _Native, pid: int, ranges: list) -> dict:
    """Kernel state, wait reason and start module of the oldest threads plus process I/O counters.

    Read-only: one ``SystemProcessInformation`` snapshot and per-thread start-address queries.
    """
    if c.sizeof(c.c_void_p) != _X64_POINTER:
        return {"event": "thread-states", "error": "x64 layout only"}
    buffer = _process_snapshot(native)
    if isinstance(buffer, int):
        return {"event": "thread-states", "error": buffer & 0xFFFFFFFF}
    offset = _process_entry(buffer, pid)
    if offset is None:
        return {"event": "thread-states", "error": "process not in snapshot"}
    count = c.c_uint32.from_buffer(buffer, offset + _PROCESS_THREADS).value
    io = {name: c.c_uint64.from_buffer(buffer, offset + field).value for name, field in _PROCESS_IO.items()}
    first, size = offset + _PROCESS_THREAD_ARRAY, c.sizeof(_SystemThread)
    records = sorted((_SystemThread.from_buffer(buffer, first + index * size) for index in range(count)),
                     key=lambda record: record.created)
    threads = [{"tid": record.tid or 0, "created_100ns": record.created, "state": record.state,
                "wait_reason": record.wait_reason, "switches": record.switches, "wait_time_raw": record.wait_time,
                **_module_at(_win32_start(native, pid, record.tid or 0), ranges)}
               for record in records[:_STATE_LIMIT]]
    return {"event": "thread-states", "count": count, "truncated": count > _STATE_LIMIT, "io": io,
            "threads": threads}


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
    before = _filetime()
    complete = bool(native.wait(session, 0, 0, tid, c.byref(count), nodes, c.byref(cycle)))
    error = 0 if complete else c.get_last_error()
    after = _filetime()
    records = []
    for node in nodes[:min(count.value, _NODE_LIMIT)] if complete or error in (234, 565) else []:
        record = {"kind": node.kind, "status": node.status}
        if node.kind == _THREAD_KIND:
            thread = node.object.thread
            record.update(pid=thread.pid, tid=thread.tid, wait_time_raw=thread.wait_ms, switches=thread.switches)
        records.append(record)
    return {"tid": tid, "complete": complete, "error": error, "cycle": bool(cycle.value),
            "required_nodes": count.value, "nodes": records,
            "query_before_filetime_100ns": before, "query_after_filetime_100ns": after}


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
    ranges: list = []
    _emit(_modules(native, pid, ranges))
    _emit(_thread_states(native, pid, ranges))
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
    sys.stdout.write(json.dumps({**value, "emitted_filetime_100ns": _filetime()}, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _filetime() -> int:
    return _UNIX_EPOCH_FILETIME + time.time_ns() // 100


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
