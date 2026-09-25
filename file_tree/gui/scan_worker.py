"""Run a scan and its analysis on a background thread so the window stays responsive."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal

from file_tree.core.analysis import CategoryStat, ExtensionStat, category_stats, summarise
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


def analyse(result: ScanResult) -> ScanOutcome:
    """Compute the largest files and the per-type totals of a scan."""
    largest, extensions = summarise(result.root, LARGEST_FILES_LIMIT)
    return ScanOutcome(result, largest, extensions, category_stats(extensions))


class ScanWorker(QThread):
    """Scans one folder; emits ``progressed`` while running and exactly one of the three end signals.

    The end signals are ``succeeded(ScanOutcome)``, ``failed(str)`` (the folder
    could not be opened at all) and ``cancelled()``.
    """

    progressed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

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
                          cancel=self._cancel)
        except ScanCancelledError:
            self.cancelled.emit()
            return
        except OSError as error:
            self.failed.emit(error.strerror or str(error))
            return
        if self._cancel.is_set():
            self.cancelled.emit()
            return
        self.succeeded.emit(analyse(result))
