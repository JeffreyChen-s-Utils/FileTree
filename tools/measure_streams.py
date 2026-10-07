"""Measure named NTFS stream prevalence/cost without opening their contents or changing the scanner."""

from __future__ import annotations

import argparse
import ctypes
import functools
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.scanner import ScanOptions, scan  # noqa: E402

_END = 38
_INVALID = ctypes.c_void_p(-1).value
_REPARSE = 0x400
_MAX_STREAMS = 256
_MAX_ENTRIES, _MAX_REPEATS, _MAX_WORKERS = 1_000_000, 20, 16


class _StreamData(ctypes.Structure):
    _fields_ = [("size", ctypes.c_longlong), ("name", ctypes.c_wchar * 296)]


@functools.cache
def _kernel() -> Any:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.FindFirstStreamW.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(_StreamData), ctypes.c_ulong]
    kernel.FindFirstStreamW.restype = ctypes.c_void_p
    kernel.FindNextStreamW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_StreamData)]
    kernel.FindNextStreamW.restype = ctypes.c_int
    kernel.FindClose.argtypes = [ctypes.c_void_p]
    kernel.FindClose.restype = ctypes.c_int
    return kernel


def named_streams(path: str) -> list[tuple[str, int]]:
    """List at most 256 named data streams; errors/changed/reparse entries remain unknown, never empty."""
    if sys.platform != "win32":
        raise OSError("This measurement requires Windows")
    before = os.lstat(path)
    if before.st_file_attributes & _REPARSE:
        raise OSError("Reparse entries are excluded")
    kernel, data = _kernel(), _StreamData()
    handle = kernel.FindFirstStreamW(path, 0, ctypes.byref(data), 0)
    if handle == _INVALID:
        error = ctypes.get_last_error()
        if error == _END:
            _unchanged(path, before)
            return []
        raise ctypes.WinError(error)
    result = []
    try:
        while True:
            if data.name != "::$DATA":
                if len(result) >= _MAX_STREAMS or data.size < 0:
                    raise OSError("Stream inventory exceeds the measurement limit or has an invalid size")
                result.append((data.name, data.size))
            if not kernel.FindNextStreamW(handle, ctypes.byref(data)):
                error = ctypes.get_last_error()
                if error != _END:
                    raise ctypes.WinError(error)
                break
        _unchanged(path, before)
        return result
    finally:
        if not kernel.FindClose(handle):
            raise ctypes.WinError(ctypes.get_last_error())


def _unchanged(path: str, before: os.stat_result) -> None:
    after = os.lstat(path)
    if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns, before.st_file_attributes) != (
            after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns, after.st_file_attributes):
        raise OSError("Entry changed during stream enumeration")


def _inventory(paths: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    known = with_streams = streams = size = 0
    errors: dict[str, int] = {}
    for path in paths:
        try:
            found = named_streams(path)
        except OSError as error:
            reason = str(getattr(error, "winerror", None) or error.strerror or error)
            errors[reason] = errors.get(reason, 0) + 1
            continue
        known += 1
        with_streams += bool(found)
        streams += len(found)
        size += sum(length for _name, length in found)
    return {"seconds": time.perf_counter() - started, "known_entries": known, "entries_with_streams": with_streams,
            "named_streams": streams, "stream_logical_bytes": size, "unknown_entries": len(paths) - known,
            "errors": errors}


def measure(root: str, *, entries: int = 10000, repeats: int = 5, workers: int = 2) -> dict[str, Any]:
    """Time ordinary scans and a bounded, additional metadata survey; include files and directories."""
    timings, inventories = [], []
    sampled, available, scan_errors = 0, 0, 0
    for _repeat in range(repeats):
        result = scan(root, options=ScanOptions(workers=workers, gentle=True))
        timings.append(result.elapsed)
        paths = []
        available = 0
        for node in result.root.iter_nodes():
            if node.is_link or node.error:
                continue
            available += 1
            if len(paths) < entries:
                paths.append(node.path)
        sampled, scan_errors = len(paths), len(result.errors)
        inventories.append(_inventory(paths))
    overhead = statistics.median(item["seconds"] for item in inventories)
    baseline = statistics.median(timings)
    return {"root": os.path.abspath(root), "python": sys.version, "platform": sys.platform, "workers": workers,
            "repeats": repeats, "sample_order": "largest-first tree traversal, files and directories",
            "available_entries": available, "sampled_entries": sampled, "sample_truncated": sampled < available,
            "scan_errors": scan_errors, "scan_seconds": timings, "stream_inventories": inventories,
            "median_scan_seconds": baseline, "median_stream_seconds": overhead,
            "additional_microseconds_per_entry": overhead * 1_000_000 / sampled if sampled else None,
            "additional_percent_of_scan": overhead / baseline * 100 if baseline else None,
            "notes": "Warm-cache sample, not drive-wide prevalence. Logical stream bytes are not allocation. "
                     "Stream phase includes two identity stats per entry; no contents opened. Scanner unchanged."}


def main() -> int:
    """Print a JSON measurement to stdout; write no files and make no normal-scan changes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--entries", type=int, default=10000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Windows is required")
    if not (1 <= args.entries <= _MAX_ENTRIES and 1 <= args.repeats <= _MAX_REPEATS
            and 1 <= args.workers <= _MAX_WORKERS):
        parser.error("entries: 1..1000000; repeats: 1..20; workers: 1..16")
    print(json.dumps(measure(args.root, entries=args.entries, repeats=args.repeats, workers=args.workers), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
