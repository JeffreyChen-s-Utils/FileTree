"""Run a scan and its analysis on a background thread so the window stays responsive.

The worker hands the root out (``started``) before any folder is read, so the
window can show the tree while it fills in (see ``FolderTreeModel.live``).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal

from file_tree.core.analysis import AgeStat, CategoryStat, ExtensionStat, category_stats, summarise
from file_tree.core.node import Node
from file_tree.core.scanner import ScanCancelledError, ScanOptions, ScanResult, scan

LARGEST_FILES_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class ScanOutcome:
    """A finished scan plus everything the result views show."""

    result: ScanResult
    largest: list[Node]
    extensions: list[ExtensionStat]
    categories: list[CategoryStat]
    ages: list[AgeStat]
    now: float
    partial: bool = False


def analyse(result: ScanResult, *, partial: bool = False) -> ScanOutcome:
    """Compute the largest files and the per-type and per-age totals of a scan (``partial`` when it was stopped)."""
    summary = summarise(result.root, LARGEST_FILES_LIMIT)
    return ScanOutcome(result, summary.largest, summary.extensions, category_stats(summary.extensions),
                       summary.ages, summary.now, partial)


class ScanWorker(QThread):
    """Scans one folder: ``started(root)`` first, ``progressed`` while running, then exactly one end signal.

    The end signals are ``succeeded(ScanOutcome)``, ``failed(str)`` (the folder
    could not be opened at all) and ``cancelled(ScanOutcome | None)``, which
    carries what was read before the stop.
    """

    started = Signal(object)
    progressed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal(object)

    def __init__(self, path: str, options: ScanOptions, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.path = path
        self._options = options
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Ask the scan to stop; ``cancelled`` follows shortly."""
        self._cancel.set()

    def run(self) -> None:
        """Thread body: scan, analyse, report."""
        try:
            result = scan(self.path, options=self._options, progress=self.progressed.emit,
                          cancel=self._cancel, on_root=self.started.emit)
        except ScanCancelledError as stopped:
            self.cancelled.emit(analyse(stopped.partial, partial=True) if stopped.partial else None)
            return
        except OSError as error:
            self.failed.emit(error.strerror or str(error))
            return
        if self._cancel.is_set():
            self.cancelled.emit(analyse(result, partial=True))
            return
        self.succeeded.emit(analyse(result))
