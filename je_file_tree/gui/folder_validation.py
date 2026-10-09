"""Owned folder checks for GUI entry points; slow filesystem calls stay off the event thread."""

import os
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal

from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import after_threads, queue_worker

if TYPE_CHECKING:
    from je_file_tree.gui.main_window import MainWindow


class FolderWorker(QThread):
    """Return the first actual folder from copied paths, unless the request was canceled."""

    checked = Signal(object)

    def __init__(self, paths: tuple[str, ...], parent: QObject) -> None:
        super().__init__(parent)
        self.paths = paths
        self.cancel = threading.Event()

    def run(self) -> None:
        """Check cancellation around each native query; never infer folder status from its name."""
        found = None
        for path in self.paths:
            if self.cancel.is_set():
                return
            valid = os.path.isdir(path)
            if self.cancel.is_set():
                return
            if valid:
                found = path
                break
        self.checked.emit(found)


class FolderDrops(QObject):
    """Coalesce copied drop references while retaining canceled native checks until termination."""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.current: FolderWorker | None = None
        self.workers: set[FolderWorker] = set()

    def request(self, paths: tuple[str, ...]) -> None:
        """Validate copied paths asynchronously; stale drops cannot replace a newer scan."""
        if self.window._closing or self.window.operation_busy:
            return
        self.cancel()
        worker = FolderWorker(paths, self)
        self.current = worker
        self.workers.add(worker)
        worker.checked.connect(lambda path: after_threads((worker,), lambda: self._checked(worker, path), self))
        worker.finished.connect(lambda: after_threads((worker,), lambda: self._retire(worker), self))
        queue_worker(worker, lambda: self.current is worker and not self.window._closing
                     and not worker.cancel.is_set(), self)

    def _checked(self, worker: FolderWorker, path: str | None) -> None:
        if worker is not self.current or self.window._closing or worker.cancel.is_set():
            return
        self.current = None
        if path is not None:
            self.window.start_scan(path)

    def _retire(self, worker: FolderWorker) -> None:
        if worker in self.workers:
            self.workers.remove(worker)
            worker.deleteLater()

    def cancel(self) -> None:
        """Invalidate the pending drop without waiting for an in-flight filesystem query."""
        worker, self.current = self.current, None
        if worker is not None:
            worker.cancel.set()
            after_threads((worker,), lambda: self._retire(worker), self)

    def shutdown(self) -> None:
        """Join retained folder queries before their owning window is destroyed."""
        self.cancel()
        for worker in tuple(self.workers):
            worker.cancel.set()
            wait_for(worker)
