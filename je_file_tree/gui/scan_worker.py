"""Run a scan and its analysis on a background thread so the window stays responsive.

The worker hands the root out (``started``) before any folder is read, so the
window can show the tree while it fills in (see ``FolderTreeModel.live``).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QAbstractEventDispatcher, QObject, QThread, Signal

from je_file_tree.core.analysis import AgeStat, CategoryStat, ExtensionStat, Summary, category_stats, summarise
from je_file_tree.core.cleanup import find_cleanup
from je_file_tree.core.cleanup_policy import CleanupPolicy
from je_file_tree.core.capacity import CapacityLedger, capacity_ledger
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.compare import SavedScan, SavedScanError, compare, load_saved
from je_file_tree.core.duplicates import DuplicateProgress, DuplicateSearchCancelledError, find_duplicates
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import WINDOW
from je_file_tree.core.scanner import ScanCancelledError, ScanOptions, ScanResult, scan
from je_file_tree.core.search import Query, search

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
    capacity: CapacityLedger | None = None


def pace_workers(connect: bool = True) -> None:
    """Close ``core.pacing.WINDOW`` while this thread's event loop handles something, open it while it waits.

    Called once by ``app.main`` (``connect=False`` undoes it, for tests). The workers then pause at their
    ``give_way()`` steps whenever the window has work to do, so clicks and painting are not held up.
    """
    dispatcher = QAbstractEventDispatcher.instance()
    if dispatcher is None:
        return
    if connect:
        dispatcher.awake.connect(WINDOW.close)
        dispatcher.aboutToBlock.connect(WINDOW.open)
    else:
        dispatcher.awake.disconnect(WINDOW.close)
        dispatcher.aboutToBlock.disconnect(WINDOW.open)
        WINDOW.open()


def wait_for(worker: QThread) -> None:
    """Block until ``worker`` has ended, the workers' gate open meanwhile so that they finish at full speed."""
    WINDOW.open()
    worker.wait()


def analyse(result: ScanResult, *, partial: bool = False) -> ScanOutcome:
    """Compute the largest files and the per-type and per-age totals of a scan (``partial`` when it was stopped)."""
    summary = summarise(result.root, LARGEST_FILES_LIMIT)
    return ScanOutcome(result, summary.largest, summary.extensions, category_stats(summary.extensions),
                       summary.ages, summary.now, partial, capacity_ledger(result.root, partial=partial))


class AnalyseWorker(QThread):
    """Recomputes the largest files and the per-type and per-age totals of a whole tree; emits ``done(Summary)``."""

    done = Signal(object)
    capacity_ready = Signal(object)

    def __init__(self, root: Node, parent: QObject | None = None, *, partial: bool = False,
                 with_capacity: bool = False) -> None:
        super().__init__(parent)
        self._root = root
        self._partial = partial
        self._with_capacity = with_capacity

    def run(self) -> None:
        """Thread body."""
        summary: Summary = summarise(self._root, LARGEST_FILES_LIMIT)
        if self._with_capacity:
            self.capacity_ready.emit(capacity_ledger(self._root, partial=self._partial))
        self.done.emit(summary)


class SearchWorker(QThread):
    """Searches a tree by name off the GUI thread; emits ``found(SearchResult)`` unless stopped first."""

    found = Signal(object)

    def __init__(self, root: Node, query: Query | str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = root
        self._query = query
        self._cancel = threading.Event()

    def stop(self) -> None:
        """Ask the search to give up (it checks once per folder); ``found`` is then not emitted."""
        self._cancel.set()

    def run(self) -> None:
        """Thread body."""
        result = search(self._root, self._query, LARGEST_FILES_LIMIT, self._cancel)
        if result is not None:
            self.found.emit(result)


class ExportWorker(QThread):
    """Writes an export off the GUI thread: ``done(rows written)``, or ``failed(reason)`` when the file cannot be saved.

    The folder tree of 86,000 folders took 1.3 s to write as JSON (measured 2026-09-26), long enough to freeze
    the window.
    """

    done = Signal(int)
    failed = Signal(str)

    def __init__(self, write: Callable[[], int], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._write = write

    def run(self) -> None:
        """Thread body."""
        try:
            count = self._write()
        except (OSError, ValueError) as error:
            self.failed.emit(getattr(error, "strerror", None) or str(error))
            return
        self.done.emit(count)


class CleanupWorker(QThread):
    """Looks for clean-up suggestions off the GUI thread; emits ``done(list[CleanupGroup])`` unless stopped."""

    done = Signal(object, object)

    def __init__(self, root: Node, parent: QObject | None = None, *, policy: CleanupPolicy | None = None) -> None:
        super().__init__(parent)
        self._root = root
        self._policy = policy
        self._cancel = threading.Event()

    def stop(self) -> None:
        """Ask the search to give up (checked once per folder); ``done`` is then not emitted."""
        self._cancel.set()

    def run(self) -> None:
        """Thread body."""
        coverage = coverage_of(self._root)
        groups = find_cleanup(self._root, cancel=self._cancel, coverage=coverage, policy=self._policy)
        if groups is not None:
            self.done.emit(groups, coverage)


class CompareWorker(QThread):
    """Reads a saved scan (given ``file``) or takes one (``saved``) and compares the tree with it.

    Emits ``done(SavedScan, list[FolderChange])``, or ``failed(reason)`` when the file is not a saved scan.
    """

    done = Signal(object, object)
    failed = Signal(str)

    def __init__(self, root: Node, *, saved: SavedScan | None = None, file: str | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = root
        self._saved = saved
        self._file = file

    def run(self) -> None:
        """Thread body."""
        saved = self._saved
        if saved is None:
            try:
                saved = load_saved(self._file or "")
            except SavedScanError as error:
                self.failed.emit(str(error))
                return
        self.done.emit(saved, compare(self._root, saved))


class DuplicatesWorker(QThread):
    """Looks for duplicate files off the GUI thread: ``progressed``, then ``succeeded`` or ``cancelled``."""

    progressed = Signal(object)
    succeeded = Signal(object)
    cancelled = Signal()

    PROGRESS_INTERVAL = 0.1  # seconds between two progress signals

    def __init__(self, root: Node, min_size: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = root
        self._min_size = min_size
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._last_report = 0.0

    def stop(self) -> None:
        """Ask the search to give up; ``cancelled`` follows."""
        self._cancel.set()

    def run(self) -> None:
        """Thread body."""
        try:
            result = find_duplicates(self._root, min_size=self._min_size, progress=self._report, cancel=self._cancel)
        except DuplicateSearchCancelledError:
            self.cancelled.emit()
            return
        self.succeeded.emit(result)

    def _report(self, progress: DuplicateProgress) -> None:
        """Called from the reading threads: passes on at most one progress per ``PROGRESS_INTERVAL``."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_report < self.PROGRESS_INTERVAL:
                return
            self._last_report = now
        self.progressed.emit(progress)


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
    analysing = Signal()

    def __init__(self, path: str, options: ScanOptions, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.path = path
        self._options = options
        self._cancel = threading.Event()
        self._pause = threading.Event()
        self._scanning = True

    def cancel(self) -> None:
        """Ask the scan to stop; ``cancelled`` follows shortly."""
        self._cancel.set()
        self._pause.clear()

    def set_paused(self, paused: bool) -> bool:
        """Pause taking new folders; return false after scanning ends or cancellation begins."""
        if not self._scanning or self._cancel.is_set():
            return False
        self._pause.set() if paused else self._pause.clear()
        return True

    def _analyse(self, result: ScanResult, *, partial: bool = False) -> ScanOutcome:
        self._scanning = False
        self.analysing.emit()
        return analyse(result, partial=partial)

    def run(self) -> None:
        """Thread body: scan, analyse, report."""
        try:
            result = scan(self.path, options=self._options, progress=self.progressed.emit,
                          cancel=self._cancel, on_root=self.started.emit, pause=self._pause)
        except ScanCancelledError as stopped:
            self.cancelled.emit(self._analyse(stopped.partial, partial=True) if stopped.partial else None)
            return
        except OSError as error:
            self.failed.emit(error.strerror or str(error))
            return
        if self._cancel.is_set():
            self.cancelled.emit(self._analyse(result, partial=True))
            return
        self.succeeded.emit(self._analyse(result))
