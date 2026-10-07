"""Measure a real scan with a memory/time budget; writes no files unless --output is given."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core import export, sunburst, treemap  # noqa: E402
from je_file_tree.core.analysis import summarise  # noqa: E402
from je_file_tree.core.cleanup import find_cleanup  # noqa: E402
from je_file_tree.core.duplicates import DuplicateSearchCancelledError, find_duplicates  # noqa: E402
from je_file_tree.core.node import Node  # noqa: E402
from je_file_tree.core.scanner import ScanCancelledError, ScanOptions, scan  # noqa: E402
from je_file_tree.core.search import search  # noqa: E402

MB = 1024 * 1024


def resident_bytes() -> int:
    """Current resident memory (Windows/Linux), peak resident memory on other POSIX systems."""
    if sys.platform == "win32":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in ("peak", "working", "pp", "p", "pn", "n", "page", "peakpage")]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.working
    if sys.platform.startswith("linux"):
        pages = int(Path("/proc/self/statm").read_text(encoding="ascii").split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    import resource  # noqa: PLC0415 - unavailable on Windows

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def measure(args: argparse.Namespace) -> dict[str, Any]:
    """Measure scan, analysis, layouts, search, cleanup and exports, retaining only one tree."""
    initial = peak = resident_bytes()
    started = time.perf_counter()
    cancel = threading.Event()
    stop_reason = ""

    def progress(_snapshot: object) -> None:
        nonlocal peak, stop_reason
        peak = max(peak, resident_bytes())
        if peak > args.memory_mb * MB:
            stop_reason = "memory budget"
        elif time.perf_counter() - started > args.seconds:
            stop_reason = "time budget"
        if stop_reason:
            cancel.set()

    try:
        result = scan(args.root, options=ScanOptions(workers=args.workers), cancel=cancel, progress=progress)
    except ScanCancelledError as error:
        if error.partial is None:
            raise
        result = error.partial
    root = result.root
    report: dict[str, Any] = {"root": root.path, "platform": sys.platform, "python": sys.version,
                              "workers": args.workers, "scan_seconds": result.elapsed,
                              "partial": bool(stop_reason), "stop_reason": stop_reason,
                              "errors": len(result.errors), "entries": root.file_count + root.dir_count + 1,
                              "initial_resident": initial, "scan_resident": resident_bytes(),
                              "budget_mb": args.memory_mb, "logical_bytes": root.size,
                              "allocated_bytes": root.allocated}
    phases = {"analysis": lambda: summarise(root), "search_all": lambda: search(root, "*"),
              "cleanup": lambda: find_cleanup(root),
              "treemap": lambda: treemap.layout(root, treemap.Rect(0, 0, 1200, 800)),
              "sunburst": lambda: sunburst.layout(root)}
    for name, operation in phases.items():
        before = time.perf_counter()
        value = operation()
        report[f"{name}_seconds"] = time.perf_counter() - before
        if isinstance(value, list):
            report[f"{name}_items"] = len(value)
        peak = max(peak, resident_bytes())
        del value
    with tempfile.TemporaryDirectory(prefix="filetree-scale-") as temporary:
        target = Path(temporary) / "tree.json"
        before = time.perf_counter()
        export.export_json(root, target)
        report["json_seconds"] = time.perf_counter() - before
        report["json_bytes"] = target.stat().st_size
        peak = max(peak, resident_bytes())
    if args.gui:
        report.update(_gui(root))
    if args.duplicates_seconds > 0:
        report.update(_duplicates(root, args.duplicates_seconds))
    report["sampled_peak_resident"] = max(peak, resident_bytes())
    report["resident_bytes_per_entry"] = (report["scan_resident"] - initial) / report["entries"]
    return report


def _gui(root: Node) -> dict[str, Any]:
    # Optional Qt measurements; ordinary core measurements need no display or Qt.
    from PySide6.QtCore import Qt  # noqa: PLC0415
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    from je_file_tree.gui.charts import ChartStack  # noqa: PLC0415
    from je_file_tree.gui.tree_model import FolderTreeModel  # noqa: PLC0415

    app = QApplication.instance() or QApplication([])
    model = FolderTreeModel()
    model.set_root(root, live=True)
    top = model.index(0, 0)
    model.rowCount(top)
    times = []
    for _ in range(5):
        started = time.perf_counter()
        model.refresh()
        times.append(time.perf_counter() - started)
    charts = ChartStack()
    charts.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    charts.resize(1200, 800)
    charts.set_view_root(root)
    report: dict[str, Any] = {"live_refresh_max_seconds": max(times)}
    for mode in ("treemap", "sunburst"):
        charts.set_mode(mode)
        app.processEvents()
        started = time.perf_counter()
        charts.currentWidget().grab()
        report[f"{mode}_paint_seconds"] = time.perf_counter() - started
    charts.close()
    return report


def _duplicates(root: Node, seconds: float) -> dict[str, Any]:
    cancel = threading.Event()
    timer = threading.Timer(seconds, cancel.set)
    started = time.perf_counter()
    timer.start()
    try:
        result = find_duplicates(root, cancel=cancel)
        return {"duplicates_seconds": time.perf_counter() - started, "duplicates_complete": True,
                "duplicates_groups": len(result.groups), "duplicates_bytes_read": result.bytes_read}
    except DuplicateSearchCancelledError:
        return {"duplicates_seconds": time.perf_counter() - started, "duplicates_complete": False}
    finally:
        timer.cancel()


def main() -> None:
    """Run the bounded measurement from a console."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--memory-mb", type=int, default=512)
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--duplicates-seconds", type=float, default=0)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.memory_mb <= 0 or args.seconds <= 0 or args.workers <= 0:
        parser.error("budgets and workers must be positive")
    report = json.dumps(measure(args), indent=2, ensure_ascii=False)
    if args.output is not None:
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
