"""Compare two freshly scanned folders, with explicit cancellable content verification."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel,
                              QPushButton, QTableView, QVBoxLayout, QWidget)

from je_file_tree.core.duplicates import DuplicateSearchCancelledError
from je_file_tree.core.formatting import format_count, format_size, format_time
from je_file_tree.core.live_compare import Difference, FolderComparison, compare_folders, export_comparison, verify_pair
from je_file_tree.core.scanner import ScanCancelledError, ScanOptions, scan
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import ExportWorker, wait_for
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel


class ComparisonModel(_TableModel[Difference]):
    """Show two sides of each relative path without presenting metadata equality as byte equality."""

    def build_columns(self) -> Sequence[Column[Difference]]:
        """Relative name, state and each side's size and recorded modification time."""
        def amount(row: Difference, side: str) -> str:
            node = getattr(row, side)
            return format_size(node.size, self.unit) if node else ""
        def modified(row: Difference, side: str) -> str:
            node = getattr(row, side)
            return format_time(node.modified) if node else ""
        return (Column("compare_relative", lambda row: row.relative, lambda row: row.relative),
                Column("compare_state", lambda row: tr("compare_" + row.state), lambda row: row.state),
                Column("compare_left_size", lambda row: amount(row, "left"),
                       lambda row: row.left.size if row.left else -1, numeric=True),
                Column("compare_right_size", lambda row: amount(row, "right"),
                       lambda row: row.right.size if row.right else -1, numeric=True),
                Column("compare_left_time", lambda row: modified(row, "left"),
                       lambda row: row.left.modified if row.left else 0),
                Column("compare_right_time", lambda row: modified(row, "right"),
                       lambda row: row.right.modified if row.right else 0))


class ComparisonWorker(QThread):
    """Own cancellable fresh scans or the explicitly selected full-file hash pairs."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QWidget, *, paths: tuple[str, str] | None = None,
                 rows: list[Difference] | None = None) -> None:
        super().__init__(parent)
        self.paths, self.rows, self.cancel = paths, rows or [], threading.Event()

    def run(self) -> None:
        """Emit complete results only; stopping suppresses every queued/partial outcome."""
        try:
            if self.paths is not None:
                options = ScanOptions(gentle=True)
                left = scan(self.paths[0], options=options, cancel=self.cancel).root
                right = scan(self.paths[1], options=options, cancel=self.cancel).root
                result = compare_folders(left, right, cancel=self.cancel)
            else:
                result = [verify_pair(row, cancel=self.cancel) for row in self.rows]
        except (ScanCancelledError, DuplicateSearchCancelledError):
            return
        except OSError as error:
            if not self.cancel.is_set():
                self.failed.emit(str(error))
            return
        if result is not None and not self.cancel.is_set():
            self.ready.emit(result)


class LiveCompareDialog(QDialog):
    """Read-only side-by-side comparison; workers are canceled and joined on close."""

    def __init__(self, paths: tuple[str, str], unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_live_compare"))
        self.resize(1150, 620)
        self._closed, self._count, self._incomplete = False, 0, False
        self._exports: set[ExportWorker] = set()
        self.model = ComparisonModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSortRole(SORT_ROLE)
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setSortingEnabled(True)
        for column, width in enumerate((300, 190, 125, 125, 170, 170)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        self.hint, self.status = QLabel(tr("compare_hint")), QLabel(tr("compare_reading"))
        self.hint.setWordWrap(True)
        roots = QLabel(tr("compare_roots", left=paths[0], right=paths[1]))
        roots.setTextFormat(Qt.TextFormat.PlainText)
        roots.setWordWrap(True)
        self.verify = QPushButton(tr("compare_verify"))
        self.verify.clicked.connect(self.hash_selected)
        self.export = QPushButton(tr("action_export_list"))
        self.export.clicked.connect(self.export_rows)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        actions = QHBoxLayout()
        for button in (self.verify, self.export, self.stop_button):
            actions.addWidget(button)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (roots, self.hint, self.view, self.status):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        layout.addLayout(actions)
        layout.addWidget(close)
        self.worker = ComparisonWorker(self, paths=paths)
        self._start()

    def _start(self) -> None:
        self.verify.setEnabled(False)
        self.export.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.worker.ready.connect(self._show)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _finished(self) -> None:
        if not self._closed:
            available = self.model.rowCount() > 0
            self.verify.setEnabled(available)
            self.export.setEnabled(available)
            self.stop_button.setEnabled(False)

    def _show(self, result: FolderComparison | list[Difference]) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        if isinstance(result, FolderComparison):
            rows, self._count, self._incomplete = result.rows, result.count, result.incomplete
        else:
            changed = {row.relative: row for row in result}
            rows = [changed.get(row.relative, row) for row in self.model.rows()]
        self.model.set_rows(rows)
        self.verify.setEnabled(True)
        self.export.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status.setText(tr("compare_summary", shown=format_count(len(rows)), count=format_count(self._count))
                            + (" " + tr("compare_incomplete") if self._incomplete else ""))

    def _failed(self, reason: str) -> None:
        if not self._closed and not self.worker.cancel.is_set():
            self.status.setText(tr("compare_error", reason=reason))
            self.stop_button.setEnabled(False)

    def hash_selected(self) -> None:
        """Hash only requested pairs, keeping all other statuses unchanged."""
        available = self.model.rows()
        rows = [available[self.proxy.mapToSource(index).row()]
                for index in self.view.selectionModel().selectedRows()]
        if not rows or self.worker.isRunning():
            return
        wait_for(self.worker)
        self.worker.deleteLater()
        self.worker = ComparisonWorker(self, rows=rows)
        self.status.setText(tr("compare_hashing"))
        self._start()

    def stop(self) -> None:
        """Cancel scans/hashes; any canceled result remains undisplayed."""
        self.worker.cancel.set()
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def export_rows(self) -> None:
        """Export the displayed, explicitly bounded rows on an owned worker."""
        target, _ = QFileDialog.getSaveFileName(self, tr("action_export_list"), "comparison.csv", tr("csv_filter"))
        if not target:
            return
        rows = self.model.rows()
        worker = ExportWorker(lambda: export_comparison(rows, target), self)
        worker.done.connect(lambda count: self.status.setText(tr("export_done", count=format_count(count),
                                                                path=target)))
        worker.failed.connect(self._failed)
        worker.finished.connect(lambda: self._exports.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._exports.add(worker)
        worker.start()

    def shutdown(self) -> None:
        """Join every owned worker before the dialog and its models are destroyed."""
        self._closed = True
        self.worker.cancel.set()
        wait_for(self.worker)
        for worker in list(self._exports):
            wait_for(worker)

    def done(self, result: int) -> None:
        """Qt: invalidate delayed results and join before closing."""
        self.shutdown()
        super().done(result)
