"""Read-only per-drive Trash labels with cancellable queries and explicit snapshot ownership."""

from __future__ import annotations

import os
import threading

from PySide6.QtCore import QObject, QStorageInfo, QThread, Signal
from PySide6.QtWidgets import QWidget

from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_size
from je_file_tree.core.trash_size import TrashUsage, trash_usage
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import after_threads

_LIMIT = 256


def bin_key(root: str) -> str:
    """Normalize mounted-root keys consistently across Qt slash variants and Windows case."""
    return os.path.normcase(os.path.normpath(root))


def bin_caption(root: str, usage: TrashUsage | None, unit: str = AUTO_UNIT) -> str:
    """Show unqueried/partial totals distinctly from a successfully queried empty bin."""
    if not root:
        return tr("bin_label_scope_unknown")
    if usage is None:
        return tr("bin_label_unqueried", root=root)
    fields = dict(root=root, size=format_size(usage.size, unit), count=format_count(usage.count))
    if usage.complete:
        return tr("bin_label_total", **fields)
    text = tr("bin_label_partial", **fields)
    return text + ("\n" + usage.error if usage.error else "")


class BinLabelsWorker(QThread):
    """Query only ready mounted scopes, resolving the current scan's drive on this worker."""

    ready = Signal(object, str)

    def __init__(self, path: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.path, self.cancel = path, threading.Event()

    def run(self) -> None:
        """Emit up to 256 per-root metadata totals; canceled inventories emit no partial map."""
        rows, selected, roots = {}, "", []
        if self.path:
            volume = QStorageInfo(self.path)
            if volume.isValid() and volume.isReady():
                selected = volume.rootPath()
                if selected:
                    roots.append(selected)
        for volume in QStorageInfo.mountedVolumes():
            if self.cancel.is_set():
                return
            if volume.isValid() and volume.isReady() and volume.bytesTotal() > 0:
                roots.append(volume.rootPath())
        for root in roots:
            if self.cancel.is_set():
                return
            key = bin_key(root)
            if not root or key in rows or len(rows) >= _LIMIT:
                continue
            usage = trash_usage(root, cancel=self.cancel)
            if usage is None:
                return
            rows[key] = usage
        if not self.cancel.is_set():
            self.ready.emit(rows, selected)


class BinLabels(QObject):
    """Own replaced query threads; close waits only through the shared worker-join helper."""

    ready = Signal(object, str)
    busy_changed = Signal(bool)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._parent = parent
        self._current: BinLabelsWorker | None = None
        self._running: set[BinLabelsWorker] = set()
        self._closed = False

    @property
    def busy(self) -> bool:
        """Whether the latest query is still running."""
        return self._current is not None

    def refresh(self, path: str = "") -> None:
        """Replace the query without waiting on an OS call in the GUI thread."""
        if self._closed:
            return
        self.stop()
        worker = BinLabelsWorker(path, self._parent)
        self._current = worker
        self._running.add(worker)
        worker.ready.connect(lambda rows, root: self._show(worker, rows, root))
        worker.finished.connect(lambda: after_threads((worker,), lambda: self._retire(worker), self))
        self.busy_changed.emit(True)
        worker.start()

    def _show(self, worker: BinLabelsWorker, rows: dict[str, TrashUsage], root: str) -> None:
        if not self._closed and self._current is worker and not worker.cancel.is_set():
            self.ready.emit(rows, root)

    def _finished(self, worker: BinLabelsWorker) -> None:
        self._running.discard(worker)
        if self._current is worker:
            self._current = None
            self.busy_changed.emit(False)

    def _retire(self, worker: BinLabelsWorker) -> None:
        self._finished(worker)
        worker.deleteLater()

    def stop(self, *, wait: bool = False) -> None:
        """Invalidate replies and cancel between OS queries; optional waiting joins every owned thread."""
        self._current = None
        for worker in self._running.copy():
            worker.cancel.set()
            if wait:
                wait_for(worker)
        self.busy_changed.emit(False)

    def shutdown(self, *, wait: bool = True) -> None:
        """Prevent more queries and join outstanding metadata calls before the window is destroyed."""
        self._closed = True
        self.stop(wait=wait)
