"""Recorded compression preview and explicitly confirmed exact-file native operations."""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.core.analysis import extension_of
from je_file_tree.core.compression import CompressionPlan, compression_plan
from je_file_tree.core.compression_ops import MODES, CompressionResult
from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.compression_worker import CompactWorker
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel


class CompressionModel(_TableModel[Node]):
    """Recorded candidates with logical/allocated sizes, type and path; no mutation actions."""

    def build_columns(self) -> Sequence[Column[Node]]:
        """Expose candidate sizes without claiming a fixed compression percentage."""
        return (
            Column("column_name", lambda node: node.name, lambda node: node.name.lower()),
            Column("column_size", lambda node: format_size(node.size, self.unit), lambda node: node.size, True),
            Column("column_allocated", lambda node: format_size(node.allocated, self.unit),
                   lambda node: node.allocated, True),
            Column("column_type", lambda node: extension_of(node.name), lambda node: extension_of(node.name)),
            Column("column_folder", lambda node: os.path.dirname(node.path), lambda node: os.path.dirname(node.path)),
        )

    def extra_data(self, row: Node, role: int) -> str | None:
        """Expose the full recorded path when the visible cell is shortened."""
        return row.path if role == Qt.ItemDataRole.ToolTipRole else None


class CompressionWorker(QThread):
    """Survey recorded candidates and OS filesystem/cluster metadata without opening payload files."""

    ready = Signal(object)

    def __init__(self, root: Node, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.cancel = root, threading.Event()
        self.include_compressed = False

    def run(self) -> None:
        """Canceled queries do not publish a partial candidate list."""
        kwargs = {"include_compressed": True} if self.include_compressed else {}
        result = compression_plan(self.root, cancel=self.cancel, **kwargs)
        if result is not None and not self.cancel.is_set():
            self.ready.emit(result)


class CompressionDialog(QDialog):
    """Review bounded exact files, confirm operations, cancel/join and request a fresh allocation scan."""

    selected = Signal(object)

    def __init__(self, root: Node, unit: str, parent: QWidget, *, partial: bool = False) -> None:
        super().__init__(parent)
        self.root, self.unit, self.partial = root, unit, partial
        self._closed = self._stopped = False
        self.plan: CompressionPlan | None = None
        self.operation: CompactWorker | None = None
        self.changed = False
        self.setWindowTitle(tr("menu_compression"))
        self.resize(1050, 610)
        self.model = CompressionModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        for column, width in enumerate((200, 110, 110, 90, 460)):
            self.view.setColumnWidth(column, width)
        self.view.doubleClicked.connect(self._select)
        install_copy(self.view)
        self.scope = QLabel(root.path)
        self.hint = QLabel(tr("compression_hint"))
        self.status = QLabel(tr("compression_reading"))
        for label in (self.scope, self.hint, self.status):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        self._build_operations()
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (self.scope, self.hint, self.mode, self.view, self.status, self.output,
                       self.apply_button, self.stop_button, close):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self._query()

    def _build_operations(self) -> None:
        self.mode = QComboBox()
        for mode in MODES:
            self.mode.addItem(tr("compression_mode_" + mode), mode)
        self.mode.currentIndexChanged.connect(self._query)
        self.apply_button = QPushButton(tr("compression_apply"))
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(120)
        self.output.hide()

    def _query(self, _index: int = 0) -> None:
        if self._closed or self.operation is not None:
            return
        if hasattr(self, "worker"):
            self.worker.cancel.set()
            wait_for(self.worker)
            self.worker.deleteLater()
        self._stopped, self.plan = False, None
        self.model.set_rows([])
        self.status.setText(tr("compression_reading"))
        self.apply_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        worker = CompressionWorker(self.root, self)
        worker.include_compressed = self.mode.currentData() == "uncompress"
        worker.ready.connect(lambda plan: self.worker is worker and self._show(plan))
        worker.finished.connect(lambda: self.worker is worker and self.operation is None
                                and self.stop_button.setEnabled(False))
        self.worker = worker
        worker.start()

    def _show(self, plan: CompressionPlan) -> None:
        if self._closed or self._stopped or self.worker.cancel.is_set():
            return
        self.plan = plan
        self.model.set_rows(plan.rows)
        text = tr("compression_summary", count=format_count(plan.count), shown=format_count(len(plan.rows)),
                  logical=format_size(plan.logical, self.unit), allocated=format_size(plan.allocated, self.unit),
                  total=format_count(plan.total_files), unknown=format_count(plan.unknown_files))
        if self.mode.currentData() == "uncompress":
            text = tr("compression_restore_summary", count=format_count(plan.count),
                      shown=format_count(len(plan.rows)), total=format_count(plan.total_files))
        filesystem = plan.filesystem or tr("compression_unknown")
        unit = format_size(plan.unit, self.unit) if plan.unit is not None else tr("compression_unknown")
        text += "\n" + tr("compression_volume", filesystem=filesystem, unit=unit)
        if not plan.ntfs:
            text += "\n" + tr("compression_ntfs_only")
        if self.partial or plan.incomplete:
            text += "\n" + tr("compression_partial")
        self.status.setText(text)
        self.apply_button.setEnabled(plan.ntfs and bool(plan.rows) and not self.changed)

    def _select(self, index) -> None:
        if self.operation is not None:
            return
        node = self.model.row_at(self.proxy.mapToSource(index).row())
        if node is not None:
            self.accept()
            self.selected.emit(node)

    def stop(self) -> None:
        """Discard canceled replies, preserving only a previously completed preview."""
        if self.operation is not None:
            self.operation.cancel.set()
            self.stop_button.setEnabled(False)
            return
        self._stopped = True
        self.worker.cancel.set()
        self.stop_button.setEnabled(False)
        if self.plan is None:
            self.status.setText(tr("scan_cancelled"))

    def _apply(self) -> None:
        if self.plan is None or not self.plan.ntfs or self.operation is not None or self.changed:
            return
        files = tuple(self.plan.rows)
        if not files:
            return
        question = QMessageBox(QMessageBox.Icon.Warning, tr("menu_compression"), "",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        question.setTextFormat(Qt.TextFormat.PlainText)
        question.setText(tr("compression_confirm", path=self.root.path, mode=self.mode.currentText(),
                            count=format_count(len(files)), total=format_count(self.plan.count),
                            size=format_size(sum(node.size for node in files), self.unit)))
        question.setDefaultButton(QMessageBox.StandardButton.No)
        if question.exec() != QMessageBox.StandardButton.Yes:
            return
        worker = CompactWorker(self.root, files, self.mode.currentData(), self)
        self.operation = worker
        self.changed = True  # Failed/canceled native commands may already have changed allocation.
        self.mode.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.view.setEnabled(False)
        self.stop_button.setEnabled(True)
        worker.progressed.connect(lambda done, total: self.status.setText(
            tr("compression_progress", done=format_count(done), total=format_count(total))))
        worker.ready.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(lambda: self.stop_button.setEnabled(False))
        worker.start()

    def _completed(self, result: CompressionResult) -> None:
        if self._closed:
            return
        self.status.setText(tr("compression_done", done=format_count(result.completed),
                               attempted=format_count(result.attempted), before=format_size(result.before, self.unit),
                               after=format_size(result.after, self.unit), unknown=format_count(result.unknown),
                               failures=format_count(len(result.failures)))
                            + ("\n" + tr("compression_canceled") if result.canceled else ""))
        if result.failures:
            self.output.setPlainText("\n\n".join(f"{path}: {reason[:2048]}" for path, reason in result.failures[:20]))
            self.output.show()

    def _failed(self, reason: str) -> None:
        if not self._closed:
            self.status.setText(tr("compression_failed", reason=reason))

    def shutdown(self) -> None:
        """Join the owned query through the shared GUI wait helper."""
        self._closed = True
        self.worker.cancel.set()
        wait_for(self.worker)
        if self.operation is not None:
            self.operation.cancel.set()
            wait_for(self.operation)

    def done(self, result: int) -> None:
        """Qt: cancel and join before this preview can be destroyed."""
        self.shutdown()
        super().done(result)
