"""Console scanning and atomic exports without importing Qt; stdout is newline-delimited JSON."""

from __future__ import annotations

import argparse
import dataclasses
import json
import signal
import sys
import threading
from collections.abc import Sequence
from typing import TextIO

from je_file_tree.core import export
from je_file_tree.core.analysis import summarise
from je_file_tree.core.compare import SavedScan, compare, load_saved
from je_file_tree.core.capacity import capacity_ledger
from je_file_tree.core.coverage import Coverage, coverage_of
from je_file_tree.core.scanner import ScanCancelledError, ScanOptions, ScanResult, scan

OK, INCOMPLETE, INVALID_ARGUMENTS, IO_ERROR, INTERRUPTED = 0, 1, 2, 3, 130


def _positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(value)
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="je-file-tree-cli")
    commands = parser.add_subparsers(dest="command", required=True)
    scanning = commands.add_parser("scan")
    scanning.add_argument("root")
    for kind in ("folders", "largest", "json", "compare"):
        scanning.add_argument(f"--{kind}")
    scanning.add_argument("--workers", type=_positive, default=2)
    scanning.add_argument("--limit", type=_positive, default=1000)
    scanning.add_argument("--exclude", action="append", default=[])
    scanning.add_argument("--no-hidden", action="store_true")
    scanning.add_argument("--gentle", action="store_true")
    return parser


def _emit(stream: TextIO, document: dict) -> None:
    # ASCII JSON also works on a Windows console whose encoding cannot represent a scanned name.
    stream.write(json.dumps(document, ensure_ascii=True) + "\n")


def _run_scan(args: argparse.Namespace, cancel: threading.Event) -> tuple[ScanResult, bool]:
    try:
        options = ScanOptions(workers=args.workers, include_hidden=not args.no_hidden,
                              exclude=tuple(args.exclude), gentle=args.gentle)
        return scan(args.root, options=options, cancel=cancel), False
    except ScanCancelledError as stopped:
        if stopped.partial is None:
            raise
        return stopped.partial, True


def _reports(args: argparse.Namespace, result: ScanResult, saved: SavedScan | None) -> None:
    if args.folders:
        export.export_folders_csv(result.root, args.folders)
    if args.largest:
        summary = summarise(result.root, args.limit)
        export.export_files_csv(summary.largest, args.largest)
    if args.json:
        export.export_json(result.root, args.json)
    if saved is not None:
        changes = sorted(compare(result.root, saved), key=lambda change: -abs(change.change))[:args.limit]
        _emit(sys.stdout, {"kind": "changes", "saved": saved.saved,
                           "changes": [{"path": change.path, "before": change.before, "after": change.after,
                                        "change": change.change} for change in changes]})


def _summary(result: ScanResult, coverage: Coverage, interrupted: bool) -> dict:
    ledger = capacity_ledger(result.root, partial=interrupted)
    capacity = {field.name: getattr(ledger, field.name) for field in dataclasses.fields(ledger)
                if field.name != "coverage"}
    return {"format": "file-tree-cli/1", "kind": "scan", "root": result.root.path,
            "partial": interrupted or not coverage.complete, "interrupted": interrupted,
            "files": result.root.file_count, "folders": result.root.dir_count,
            "logical_bytes": result.root.size, "allocated_estimate_bytes": result.root.allocated,
            "elapsed_seconds": result.elapsed, "errors": len(result.errors), "capacity": capacity,
            "warnings": result.warnings,
            "coverage": {"known_folders": coverage.known_folders, "skipped_folders": coverage.skipped_folders,
                         "inaccessible_folders": coverage.inaccessible_folders,
                         "pending_folders": coverage.pending_folders, "omitted_bytes": None}}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the console command; return 0/1/2/3/130 for success/partial/arguments/I/O/interruption.

    Each requested export is atomic independently. Ctrl+C stops the scan and exports its partial
    snapshot; a second Ctrl+C aborts immediately. No move or removal is offered by this entry point.
    Argument parsing uses argparse's standard help/error messages; report keys are a fixed JSON protocol.
    """
    args = _parser().parse_args(argv)
    cancel = threading.Event()

    def interrupt(_number: int, _frame: object) -> None:
        if cancel.is_set():
            raise KeyboardInterrupt
        cancel.set()

    previous = signal.signal(signal.SIGINT, interrupt)
    try:
        saved = load_saved(args.compare) if args.compare else None
        result, interrupted = _run_scan(args, cancel)
        coverage = coverage_of(result.root)
        _emit(sys.stdout, _summary(result, coverage, interrupted))
        if result.errors:
            _emit(sys.stderr, {"kind": "scan_errors", "entries": result.errors})
        _reports(args, result, saved)
        if interrupted or cancel.is_set():
            return INTERRUPTED
        return OK if coverage.complete else INCOMPLETE
    except (OSError, ValueError) as error:
        _emit(sys.stderr, {"kind": "error", "reason": str(error)})
        return IO_ERROR
    except (KeyboardInterrupt, ScanCancelledError):
        return INTERRUPTED
    finally:
        signal.signal(signal.SIGINT, previous)


if __name__ == "__main__":
    raise SystemExit(main())
