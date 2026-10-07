"""Read-only recorded-time filtering with cancellable whole-tree enumeration."""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                              QPushButton, QSpinBox, QTableView, QVBoxLayout, QWidget)

from je_file_tree.core.file_times import TimeInventory, files_older_than
from je_file_tree.core.formatting import format_count, format_size, format_time
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel
from je_file_tree.gui.tree_model import NODE_ROLE


def _date(value: float | None) -> str:
    return format_time(value) if value is not None else tr("size_unknown")


class FileTimesModel(_TableModel[Node]):
    """Present recorded file dates beside named sizes, without filesystem queries."""

    def build_columns(self) -> Sequence[Column[Node]]:
        """Name, logical/named allocated sizes, recorded access/birth dates and containing folder."""
        return (Column("column_name", lambda node: node.name, lambda node: node.name.lower()),
                Column("column_size", lambda node: format_size(node.size, self.unit),
                       lambda node: node.size, numeric=True),
                Column("column_allocated", lambda node: format_size(node.allocated, self.unit),
                       lambda node: node.allocated, numeric=True),
                Column("column_accessed", lambda node: _date(node.accessed), lambda node: node.accessed or -1),
                Column("column_created", lambda node: _date(node.created), lambda node: node.created or -1),
                Column("column_folder", lambda node: os.path.dirname(node.path), lambda node: node.path))

    def extra_data(self, node: Node, role: int) -> Any:
        """Expose the exact scanned node for activation; tooltip clarifies timestamp reliability."""
        if role == NODE_ROLE:
            return node
        return tr("file_times_hint") if role == Qt.ItemDataRole.ToolTipRole else None


class FileTimesWorker(QThread):
    """Query recorded metadata on a worker; canceled queries publish no rows."""

    ready = Signal(object)

    def __init__(self, root: Node, clock: str, days: int, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.clock, self.days, self.cancel = root, clock, days, threading.Event()

    def run(self) -> None:
        """Return a bounded inventory with full match/unknown counts and reported NTFS policy."""
        result = files_older_than(self.root, self.days, clock=self.clock, cancel=self.cancel)
        if result is not None and not self.cancel.is_set():
            self.ready.emit(result)


class FileTimesDialog(QDialog):
    """Filter recorded access/creation dates; activation returns an existing node after joining work."""

    selected = Signal(object)

    def __init__(self, root: Node, unit: str, *, partial: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.root, self._closed, self._partial = root, False, partial
        self.worker: FileTimesWorker | None = None
        self.setWindowTitle(tr("action_file_times"))
        self.resize(1120, 600)
        self.mode = QComboBox()
        for key in ("accessed", "created"):
            self.mode.addItem(tr(f"file_times_{key}"), key)
        self.mode.setAccessibleName(tr("file_times_mode"))
        self.days = QSpinBox()
        self.days.setRange(0, 36500)
        self.days.setValue(730)
        self.days.setAccessibleName(tr("file_times_days"))
        controls = QHBoxLayout()
        for widget in (self.mode, QLabel(tr("file_times_days")), self.days):
            controls.addWidget(widget)
        controls.addStretch()
        self.model = FileTimesModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        self.view.doubleClicked.connect(self._select)
        for column, width in enumerate((210, 110, 120, 185, 185, 340)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        self.hint = QLabel(tr("file_times_hint"))
        self.hint.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        for widget in (self.hint, self.view, self.status, self.stop_button, buttons):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self.mode.currentIndexChanged.connect(self._refresh)
        self.days.valueChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        if self._closed:
            return
        if self.worker is not None:
            self.worker.cancel.set()
            wait_for(self.worker)
            self.worker.deleteLater()
        self.model.set_rows([])
        self.status.setText(tr("file_times_reading"))
        self.stop_button.setEnabled(True)
        worker = FileTimesWorker(self.root, self.mode.currentData(), self.days.value(), self)
        self.worker = worker
        worker.ready.connect(lambda result: self._show(worker, result))
        worker.start()

    def _show(self, worker: FileTimesWorker, result: TimeInventory) -> None:
        if self._closed or self.worker is not worker or worker.cancel.is_set():
            return
        self.stop_button.setEnabled(False)
        self.model.set_rows(result.rows)
        policy = tr(f"file_times_policy_{result.policy.state}")
        self.status.setText(tr("file_times_summary", shown=format_count(len(result.rows)),
                               count=format_count(result.count), size=format_size(result.size, self.model.unit),
                               unknown=format_count(result.unknown), total=format_count(result.total))
                            + " " + policy + (" " + tr("special_partial")
                                              if self._partial or result.incomplete else ""))

    def _select(self, index) -> None:
        node = index.data(NODE_ROLE)
        if isinstance(node, Node):
            self.accept()
            self.selected.emit(node)

    def stop(self) -> None:
        """Cancel the current query without presenting a partial inventory as complete."""
        if self.worker is not None:
            self.worker.cancel.set()
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def shutdown(self) -> None:
        """Ignore queued replies and join the owned worker before destruction."""
        self._closed = True
        if self.worker is not None:
            self.worker.cancel.set()
            wait_for(self.worker)

    def done(self, result: int) -> None:
        """Join enumeration before closing the dialog."""
        self.shutdown()
        super().done(result)
