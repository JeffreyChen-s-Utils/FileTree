"""Default-off per-tab native following; bounded metadata events only request fresh scans."""

from __future__ import annotations

import sys
import threading
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel

from je_file_tree.core.change_watch import MAX_FOLDERS, ChangeBatch, changed, watch
from je_file_tree.core.node import Node, outermost
from je_file_tree.core.pacing import give_way
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import after_threads, queue_worker

if TYPE_CHECKING:
    from je_file_tree.gui.main_window import MainWindow

ENABLED_KEY = "follow_changes"
COALESCE_SECONDS = 1.0
RECONCILE_SECONDS = 300.0


def supported() -> bool:
    """Native change feeds currently support Windows and Linux."""
    return sys.platform == "win32" or sys.platform.startswith("linux")


def _inside(node: Node, ancestor: Node) -> bool:
    while node is not ancestor and node.parent is not None:
        node = node.parent
    return node is ancestor


class ChangeWorker(QThread):
    """Capture folder maps off the GUI thread and retain at most one bounded dirty batch."""

    def __init__(self, root: Node, parent: QObject) -> None:
        super().__init__(parent)
        self.root = root
        self.cancel = threading.Event()
        self.folders: dict[str, Node] = {}
        self.backend, self.error = "", ""
        self._lock = threading.Lock()
        self._batch = ChangeBatch()

    def record(self, batch: ChangeBatch) -> None:
        """Coalesce at the producer; event storms cannot create an unbounded Qt signal queue."""
        with self._lock:
            self._batch = changed(set(self._batch.folders) | set(batch.folders),
                                  full=self._batch.full or batch.full,
                                  reason=batch.reason or self._batch.reason)

    def take(self) -> ChangeBatch:
        """Transfer pending metadata once under the producer lock."""
        with self._lock:
            result, self._batch = self._batch, ChangeBatch()
        return result

    def run(self) -> None:
        """Retain native setup/errors until the owning controller cancels and joins this worker."""
        try:
            for node in self.root.iter_nodes():
                if self.cancel.is_set():
                    return
                if node.is_dir:
                    give_way()
                    if not node.is_link and node.path is not None:
                        self.folders[node.path] = node
                        if len(self.folders) > MAX_FOLDERS:
                            raise ValueError("Follow changes exceeds the captured-folder limit")
            watch(self.root, self.record, self.cancel, ready=self._initialized)
        except (OSError, ValueError, UnicodeError) as error:
            self.error = str(error)

    def _initialized(self, backend: str) -> None:
        self.backend = backend


class FollowChanges(QObject):
    """Own one tab's monitor, defer busy work and periodically reconcile observational gaps."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.worker: ChangeWorker | None = None
        self.root: Node | None = None
        self.enabled, self._closing = False, False
        self._pending = ChangeBatch()
        self._since, self._reconcile = 0.0, 0.0
        self._status, self._detail = "follow_waiting", ""
        self._retiring: set[ChangeWorker] = set()
        self.label = QLabel(window)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setMaximumWidth(300)
        self.label.hide()
        window.statusBar().addPermanentWidget(self.label)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)

    def configure(self, enabled: bool) -> None:
        """Persist the default-off preference; cancel old readers and retire them asynchronously."""
        self.window.settings.setValue(ENABLED_KEY, enabled)
        self.enabled = enabled
        self.stop(clear=True)
        self.label.setVisible(enabled)
        if enabled and not self._closing:
            self.timer.start()
            outcome = self.window.results.outcome
            if (outcome is not None and self.window.operation_busy
                    and outcome.result.root.path is not None and not outcome.partial):
                self.root = outcome.result.root
                self._merge(ChangeBatch(full=True, reason="source_operation"))
                self._set_status("follow_waiting")
            elif outcome is not None and self.window._worker is None:
                self.adopt(outcome.result.root)
            else:
                self._set_status("follow_waiting")
        else:
            self.timer.stop()

    def adopt(self, root: Node) -> None:
        """Rearm after a complete/branch result; pending captured paths survive branch replacement."""
        previous = self.root
        self.stop()
        self.root = root
        if not self.enabled or self._closing:
            return
        if not supported():
            self._set_status("follow_unsupported")
            return
        outcome = self.window.results.outcome
        if root.path is None or outcome is None or outcome.partial:
            self._set_status("follow_incomplete")
            return
        self._set_status("follow_starting")
        worker = ChangeWorker(root, self)
        self.worker = worker
        queue_worker(worker, lambda: self.worker is worker and not self._closing
                     and not self.window._closing and not worker.cancel.is_set(), self)
        if root is not previous or not self._reconcile:
            self._reconcile = time.monotonic() + RECONCILE_SECONDS

    def stop(self, *, clear: bool = False, wait: bool = False) -> tuple[ChangeWorker, ...]:
        """Join through the GUI's shared gate; retain the final bounded batch before releasing maps."""
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.cancel.set()
            root = self.root
            self._retiring.add(worker)
            after_threads((worker,), lambda: self._retired(worker, root, clear), self)
        if clear:
            self.root = None
            self._pending, self._since = ChangeBatch(), 0.0
            self._reconcile = 0.0
        retiring = tuple(self._retiring)
        if wait:
            for pending in retiring:
                wait_for(pending)
        return retiring

    def _retired(self, worker: ChangeWorker, root: Node | None, clear: bool) -> None:
        self._retiring.discard(worker)
        if not clear and not self._closing and self.root is root:
            self._merge(worker.take())
            if worker.error:
                self._set_status("follow_failed", worker.error)
        worker.deleteLater()

    def quiesce(self, *, wait: bool = True) -> tuple[ChangeWorker, ...]:
        """Stop tree capture before source operations; their observation gap requires full reconciliation."""
        active = self.worker is not None
        retiring = self.stop(wait=wait)
        if active:
            self._merge(ChangeBatch(full=True, reason="source_operation"))
        return retiring

    def shutdown(self, *, wait: bool = True) -> None:
        """Prevent late replies and join all native work before the tab is destroyed."""
        self._closing = True
        self.timer.stop()
        self.stop(clear=True, wait=wait)

    def _merge(self, batch: ChangeBatch) -> None:
        if not batch.folders and not batch.full:
            return
        if not self._pending.full and not self._pending.folders:
            self._since = time.monotonic()
        self._pending = changed(set(self._pending.folders) | set(batch.folders),
                                full=self._pending.full or batch.full,
                                reason=batch.reason or self._pending.reason)

    def tick(self) -> None:
        """Poll bounded events once a second and avoid scans during reviews, Undo offers or analysis."""
        if not self.enabled or self._closing or self.window._closing:
            return
        worker = self.worker
        if worker is not None:
            self._merge(worker.take())
            if worker.error:
                self._set_status("follow_failed", worker.error)
                return
            elif worker.backend:
                self._set_status("follow_active", worker.backend)
        if (self.root is not None and worker is not None and not worker.error and worker.backend
                and time.monotonic() >= self._reconcile):
            self._merge(ChangeBatch(full=True, reason="periodic_reconciliation"))
        self._flush()

    def _flush(self) -> None:
        window = self.window
        if (window._worker is not None or window.operation_busy or window._analysers
                or window._undo.available or window._trash_rescans or QApplication.activeModalWidget() is not None
                or time.monotonic() - self._since < COALESCE_SECONDS):
            return
        outcome = window.results.outcome
        if (self.root is None or self.root.path is None or outcome is None
                or outcome.partial or outcome.result.root is not self.root):
            return
        batch = self._pending
        if not batch.full and not batch.folders:
            return
        if batch.full:
            node = self.root
            self._pending = ChangeBatch()
        else:
            worker = self.worker
            if worker is None or not worker.backend or worker.error:
                return
            candidates = [worker.folders.get(path) for path in batch.folders]
            if any(node is None or not node.is_in(self.root) for node in candidates):
                self._merge(ChangeBatch(full=True, reason="scope_changed"))
                return
            node = outermost(candidates)[0]
            # Keep unrelated dirty branches; the next result's worker supplies their fresh map.
            remaining = {path for path, candidate in zip(batch.folders, candidates, strict=True)
                         if not _inside(candidate, node)}
            self._pending = changed(remaining)
        window.rescan_folder(node)

    def _set_status(self, key: str, detail: str = "") -> None:
        self._status, self._detail = key, detail
        self.retranslate()

    def retranslate(self) -> None:
        """Show plain-text feed status/errors in the current interface language."""
        detail = tr("follow_backend_" + self._detail) if self._status == "follow_active" else self._detail
        self.label.setText(tr(self._status, detail=detail))
        self.label.setToolTip(self.label.text())
