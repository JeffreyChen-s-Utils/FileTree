"""Two-question Windows drive and reviewed freedesktop volume OS-bin emptying."""

from __future__ import annotations

import re
import sys
import threading

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.bin_empty import BinEmptyPlan, empty_posix_bin, prepare_bin_empty
from je_file_tree.core.trash_size import TrashUsage, empty_windows_bin
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.volumes import Volume, VolumesDialog


def ask_bin(parent: QWidget, title: str, message: str, buttons: QMessageBox.StandardButton,
            default: QMessageBox.StandardButton) -> int:
    """Show literal scope paths even when filesystem names resemble rich text."""
    box = QMessageBox(QMessageBox.Icon.Question, title, message, buttons, parent)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setDefaultButton(default)
    return box.exec()


class BinApprovalWorker(QThread):
    """Capture complete recognized Linux scopes on an owned cancellable thread."""

    completed = Signal(object, str)

    def __init__(self, root: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.cancel = root, threading.Event()

    def run(self) -> None:
        """Return the captured plan or a plain error; cancellation suppresses approval."""
        try:
            plan = prepare_bin_empty(self.root, cancel=self.cancel)
            reason = "" if plan is None or plan.usage.complete else plan.usage.error
        except (OSError, ValueError) as error:
            plan, reason = None, str(error)
        if not self.cancel.is_set():
            self.completed.emit(plan, reason)


class EmptyBinWorker(QThread):
    """Call only the native, approved single-drive API; do not terminate permanent operations midway."""

    completed = Signal(str)

    def __init__(self, root: str, approved: TrashUsage | BinEmptyPlan, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.approved = root, approved

    def run(self) -> None:
        """Recheck approved totals and report native errors, including partial emptying."""
        try:
            if isinstance(self.approved, BinEmptyPlan):
                result = empty_posix_bin(self.approved)
                if result.failures:
                    self.completed.emit(tr("bin_partial", count=format_count(result.removed),
                                           reason="; ".join(result.failures)))
                    return
            else:
                empty_windows_bin(self.root, self.approved)
        except (OSError, ValueError) as error:
            self.completed.emit(str(error))
            return
        self.completed.emit("")


class BinDialog(VolumesDialog):
    """Current bin metadata and exact-scope Windows/Linux emptying with two questions."""

    emptied = Signal(str)

    def __init__(self, unit: str, parent: QWidget | None = None) -> None:
        super().__init__(unit, parent)
        self._empty_worker: EmptyBinWorker | None = None
        self._approval_worker: BinApprovalWorker | None = None
        self.last_error = ""
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.setWindowTitle(tr("action_bins"))
        self.hint.setText(tr("bin_hint"))
        self.empty_button = QPushButton(tr("bin_empty"))
        self.empty_button.setEnabled(False)
        self.empty_button.setVisible(sys.platform == "win32" or sys.platform.startswith("linux"))
        self.empty_button.clicked.connect(self.empty_selected)
        self.layout().insertWidget(self.layout().count() - 1, self.empty_button)
        self.view.selectionModel().currentChanged.connect(self._buttons)

    def _show(self, rows: list[Volume], count: int) -> None:
        super()._show(rows, count)
        if not self._closed and not self.worker.cancel.is_set():
            self._buttons()
            if self.last_error:
                self.status.setText(tr("bin_failed", reason=self.last_error))
                self.status.setTextFormat(Qt.TextFormat.PlainText)

    def _selected(self) -> Volume | None:
        row = self.view.currentIndex().data(Qt.ItemDataRole.UserRole)
        return row if isinstance(row, Volume) else None

    def _buttons(self) -> None:
        row = self._selected()
        platform = (sys.platform.startswith("linux") or sys.platform == "win32" and row is not None
                    and re.fullmatch(r"[A-Za-z]:[/\\]", row.root) is not None)
        enabled = (platform and self._empty_worker is None and self._approval_worker is None
                   and not self.worker.cancel.is_set()
                   and row is not None and row.trash.complete and row.trash.count > 0
                   and not self._closed)
        self.empty_button.setEnabled(enabled)

    def empty_selected(self) -> None:
        """Ask twice with the current drive/size/count and irreversibility before starting deletion."""
        self._buttons()
        row = self._selected()
        if not self.empty_button.isEnabled() or row is None:
            return
        if sys.platform.startswith("linux"):
            worker = BinApprovalWorker(row.root, self)
            worker.completed.connect(lambda plan, reason: self._approval_finished(worker, plan, reason))
            self._approval_worker = worker
            self.empty_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.view.setEnabled(False)
            self.status.setText(tr("bin_preparing", root=row.root))
            worker.start()
            return
        self._confirm(row.root, row.trash, row.root)

    def _approval_finished(self, worker: BinApprovalWorker, plan: BinEmptyPlan | None, reason: str) -> None:
        if worker is not self._approval_worker:
            return
        wait_for(worker)
        self._approval_worker = None
        worker.deleteLater()
        if self._closed:
            return
        self.view.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._buttons()
        if worker.cancel.is_set():
            return
        if reason or plan is None or not plan.usage.complete or plan.usage.count <= 0:
            self.last_error = reason or tr("bin_no_approval")
            self.status.setTextFormat(Qt.TextFormat.PlainText)
            self.status.setText(tr("bin_failed", reason=self.last_error))
            return
        scope = "\n".join(f"{entry.directory}/files\n{entry.directory}/info" for entry in plan.scopes)
        self._confirm(plan.root, plan, scope)

    def _confirm(self, root: str, approved: TrashUsage | BinEmptyPlan, scope: str) -> None:
        usage = approved.usage if isinstance(approved, BinEmptyPlan) else approved
        fields = dict(root=scope, size=format_size(usage.size, self.model.unit), count=format_count(usage.count))
        keys = ("bin_scope_first", "bin_scope_irreversible") if isinstance(approved, BinEmptyPlan) else (
            "bin_first", "bin_irreversible")
        for key in keys:
            answer = ask_bin(self, tr("bin_empty"), tr(key, **fields),
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                             QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self.refresh()
                return
        self.empty_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.close_box.setEnabled(False)
        self.view.setEnabled(False)
        self.status.setText(tr("bin_running", root=root))
        worker = EmptyBinWorker(root, approved, self)
        worker.completed.connect(self._empty_finished)
        self._empty_worker = worker
        worker.start()

    def _empty_finished(self, reason: str) -> None:
        worker = self._empty_worker
        if worker is not None:
            wait_for(worker)
            worker.deleteLater()
        self._empty_worker = None
        if self._closed:
            return
        self.last_error = reason
        if worker is not None:
            self.emptied.emit(worker.root)
        self.close_box.setEnabled(True)
        self.view.setEnabled(True)
        self.refresh()

    def _scan(self, index) -> None:
        if self._empty_worker is None and self._approval_worker is None:
            super()._scan(index)

    def stop(self) -> None:
        """Stop surveys only; an active OS emptying call cannot be canceled."""
        if self._empty_worker is None:
            if self._approval_worker is not None:
                self._approval_worker.cancel.set()
                wait_for(self._approval_worker)
                self._approval_worker.deleteLater()
                self._approval_worker = None
                self.view.setEnabled(True)
            super().stop()
            self.empty_button.setEnabled(False)

    def done(self, result: int) -> None:
        """Wait for an active native emptying operation before permitting close."""
        if self._empty_worker is None:
            super().done(result)

    def shutdown(self) -> None:
        """Join any native operation and the current metadata survey before destruction."""
        if self._empty_worker is not None:
            wait_for(self._empty_worker)
        if self._approval_worker is not None:
            self._approval_worker.cancel.set()
            wait_for(self._approval_worker)
        super().shutdown()
