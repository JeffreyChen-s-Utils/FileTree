"""Read-only largest Git objects, with bounded subprocess pipes and an explicit Stop."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDialogButtonBox, QLabel, QPushButton,
                              QTableView, QVBoxLayout, QWidget)

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.git_history import GitHistory, GitHistoryCancelledError, GitObject, git_history
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel


class GitObjectsModel(_TableModel[GitObject]):
    """Object IDs, translated Git types and logical lengths; no disk-saving claim."""

    def build_columns(self) -> Sequence[Column[GitObject]]:
        """Read-only metadata for the largest objects reachable from every ref."""
        return (Column("git_oid", lambda row: row.oid, lambda row: row.oid),
                Column("git_kind", lambda row: tr("git_type_" + row.kind), lambda row: row.kind),
                Column("git_length", lambda row: format_size(row.size, self.unit), lambda row: row.size, numeric=True))


class GitHistoryWorker(QThread):
    """Run only read-only fixed Git plumbing and clean up its owned processes on Stop."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.path, self.cancel = path, threading.Event()

    def run(self) -> None:
        """Emit complete inventory or a clear error, suppressing canceled outcomes."""
        try:
            result = git_history(self.path, cancel=self.cancel)
        except GitHistoryCancelledError:
            return
        except (OSError, ValueError) as error:
            if not self.cancel.is_set():
                self.failed.emit(str(error))
            return
        if not self.cancel.is_set():
            self.ready.emit(result)


class GitHistoryDialog(WorkerDialog):
    """Inspect a selected working folder without running gc or modifying the repository."""

    def __init__(self, path: str, unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_git_history"))
        self.resize(950, 570)
        self._closed = False
        self.model = GitObjectsModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        for column, width in enumerate((520, 230, 160)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        location = QLabel(path)
        location.setTextFormat(Qt.TextFormat.PlainText)
        location.setWordWrap(True)
        hint = QLabel(tr("git_hint"))
        hint.setWordWrap(True)
        self.status = QLabel(tr("git_reading"))
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.advice = QLabel()
        self.advice.setWordWrap(True)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (location, hint, self.view, self.status, self.advice, self.stop_button, close):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self.worker = GitHistoryWorker(path, self)
        self.worker.ready.connect(self._show)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _show(self, result: GitHistory) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self.model.set_rows(result.rows)
        self.status.setText(tr("git_summary", shown=format_count(len(result.rows)), count=format_count(result.count),
                               size=format_size(result.logical, self.model.unit)))
        self.advice.setText(tr("git_gc_loose", count=format_count(result.loose)) if result.loose
                            else tr("git_gc_packed"))
        self.stop_button.setEnabled(False)

    def _failed(self, reason: str) -> None:
        if not self._closed and not self.worker.cancel.is_set():
            self.status.setText(tr("git_failed", reason=reason))
            self.stop_button.setEnabled(False)

    def stop(self) -> None:
        """Stop metadata subprocesses; canceled inventories are not shown as complete."""
        self.worker.cancel.set()
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def shutdown(self, *, wait: bool = True) -> None:
        """Join the worker and its owned Git processes/pipe threads before destruction."""
        self._closed = True
        self.worker.cancel.set()
        if wait:
            wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: reject late replies and wait for cancellation before closing."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
