"""Ephemeral status-bar Undo ownership, expiry, native result reporting and parent refresh."""

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QMessageBox, QPushButton

from je_file_tree.core.node import Node, outermost
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import after_threads, queue_worker
from je_file_tree.gui.undo_worker import UndoBatch, UndoEntry, UndoWorker

if TYPE_CHECKING:
    from je_file_tree.gui.main_window import MainWindow
    from je_file_tree.gui.trash_worker import TrashWorker

_OFFER_MS = 8000


class TrashUndo(QObject):
    """Offer captured native plans briefly; an explicit click alone authorizes the inverse operation."""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.entries: tuple[UndoEntry, ...] = ()
        self.root: Node | None = None
        self._operation_root: Node | None = None
        self.deadline = 0.0
        self.worker: UndoWorker | None = None
        self.button = QPushButton(window)
        self.button.clicked.connect(self.undo)
        self.button.hide()
        window.statusBar().addPermanentWidget(self.button)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.expire(rescan=True))

    @property
    def busy(self) -> bool:
        """Native worker ownership lasts through result handling or an explicit joined shutdown."""
        return self.worker is not None

    @property
    def available(self) -> bool:
        """Only the same scan tree and an unexpired frozen offer may authorize Undo."""
        return bool(self.entries and self.root is self.window.results.tree_model.root
                    and time.monotonic() <= self.deadline and not self.busy)

    def offer(self, worker: "TrashWorker | None") -> str:
        """Show captured successful entries and visible reasons for unavailable inverse plans."""
        self.expire()
        if worker is None or worker._root is not self.window.results.tree_model.root:
            return ""
        self.entries = tuple(worker.undo_entries)
        self.root = self.window.results.tree_model.root
        self.deadline = time.monotonic() + _OFFER_MS / 1000
        details = "\n".join(f"{path}: {reason}" for path, reason in worker.undo_errors)
        self.button.setToolTip("\n".join(entry.plan.origin.path for entry in self.entries)
                               + ("\n" + details if details else ""))
        self.retranslate()
        if self.entries:
            self.button.show()
            self.timer.start(_OFFER_MS)
        return tr("undo_unavailable", reason=details) if details else ""

    def retranslate(self) -> None:
        """Refresh the offer's translated text without extending its deadline."""
        self.button.setText(tr("undo_button", count=str(len(self.entries))))

    def expire(self, *, rescan: bool = False) -> None:
        """Drop action authority without touching any payload or starting an inverse operation."""
        self.timer.stop()
        self.entries, self.root, self.deadline = (), None, 0.0
        self.button.hide()
        if rescan and not self.window._closing:
            self.window._rescan_after_trash()

    def undo(self) -> None:
        """Accept one current offer; double clicks, root changes and expired approvals do nothing."""
        window = self.window
        if not self.available:
            self.expire(rescan=True)
            return
        if window.operation_busy or window._worker is not None or window._path_dialogs or window._closing:
            return
        entries, deadline = self.entries, self.deadline
        self._operation_root = self.root
        self.expire()
        window._trash_rescans.clear()
        window._bin_labels.stop()
        worker = UndoWorker(entries, window._journal, deadline, int(window.winId()), window)
        worker.done.connect(lambda result: after_threads((worker,), lambda: self._finished(worker, result), self))
        self.worker = worker
        window.results.setEnabled(False)
        window._update_actions()
        window.statusBar().showMessage(tr("undo_running"))
        queue_worker(worker, lambda: not window._closing and self.worker is worker
                     and not worker.cancel_event.is_set(), window, lambda: self._discard(worker))

    def _discard(self, worker: UndoWorker) -> None:
        if worker is self.worker and not self.window._closing:
            worker.result = UndoBatch()
            self._finished(worker, worker.result)

    def _finished(self, worker: UndoWorker, result: UndoBatch) -> None:
        if worker is not self.worker:
            return
        worker.deleteLater()
        self.worker = None
        window = self.window
        if window._closing:
            return
        window.results.setEnabled(True)
        window._analyser = None
        window.results.clear_capacity()
        window.refresh_bin_labels()
        window._update_actions()
        self.report(result)
        window.statusBar().showMessage(tr("undo_done", restored=str(sum(item.restored for item in result.results)),
                                         failed=str(sum(not item.restored for item in result.results))))
        root = window.results.tree_model.root
        current = root is self._operation_root
        self._operation_root = None
        if not current:
            return
        window._trash_rescans = outermost(entry.parent for entry in worker.entries
                                         if entry.parent is not None and entry.parent.is_in(root))
        window._rescan_after_trash()

    def report(self, result: UndoBatch | None) -> None:
        """Keep native/partial/receipt/audit failures visible with exact actual paths, including on close."""
        if result is None:
            return
        lines = [tr("undo_result", source=item.source, trashed=item.trashed,
                    status=tr("journal_status_restored" if item.restored else "journal_status_failed"),
                    reason=item.error) for item in result.results if item.error]
        lines.extend(tr("journal_write_failed", reason=reason) for reason in result.journal_errors)
        if lines:
            message = QMessageBox(QMessageBox.Icon.Warning, tr("undo_title"), "\n\n".join(lines),
                                 QMessageBox.StandardButton.Ok, self.window)
            message.setTextFormat(Qt.TextFormat.PlainText)
            message.exec()

    def shutdown(self) -> None:
        """Expire authority, cancel unstarted entries, join native work and report its retained result."""
        self.expire()
        if self.worker is not None:
            worker = self.worker
            worker.cancel()
            wait_for(worker)
            self.worker = None
            self.report(worker.result)
        self._operation_root = None
