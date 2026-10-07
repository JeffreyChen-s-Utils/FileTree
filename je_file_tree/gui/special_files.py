"""A read-only, cancellable view of special file metadata already captured by the scan."""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QLabel, QPushButton,
                              QTableView, QVBoxLayout, QWidget)

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.special_files import SpecialEntry, SpecialFiles, special_files
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel
from je_file_tree.gui.tree_model import NODE_ROLE


class SpecialFilesModel(_TableModel[SpecialEntry]):
    """Display recorded states beside logical/allocated bytes; no provider inference or download commands."""

    def build_columns(self) -> Sequence[Column[SpecialEntry]]:
        """Name, recorded states, full logical content length, allocation and folder."""
        return (Column("column_name", lambda row: row.node.name, lambda row: row.node.name.lower()),
                Column("special_states", _states, _states),
                Column("special_content_size", lambda row: format_size(row.node.size, self.unit),
                       lambda row: row.node.size, numeric=True),
                Column("column_allocated", lambda row: format_size(row.node.allocated, self.unit),
                       lambda row: row.node.allocated, numeric=True),
                Column("column_folder", lambda row: os.path.dirname(row.node.path), lambda row: row.node.path))

    def extra_data(self, row: SpecialEntry, role: int) -> Any:
        """Expose the scanned node for activation and a full path tooltip."""
        if role == NODE_ROLE:
            return row.node
        return row.node.path if role == Qt.ItemDataRole.ToolTipRole else None


def _states(row: SpecialEntry) -> str:
    return ", ".join(tr(f"special_{state}") for state in row.states)


class SpecialFilesWorker(QThread):
    """Survey snapshots off the GUI thread; canceled surveys emit no partial result."""

    ready = Signal(object)

    def __init__(self, root: Node, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.cancel = root, threading.Event()

    def run(self) -> None:
        """Emit the bounded recorded metadata inventory if it completed."""
        result = special_files(self.root, cancel=self.cancel)
        if result is not None and not self.cancel.is_set():
            self.ready.emit(result)


class SpecialFilesDialog(QDialog):
    """Inspect the completed scan; double-click selects an existing entry and closes the dialog."""

    selected = Signal(object)

    def __init__(self, root: Node, unit: str, *, partial: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_special_files"))
        self.resize(1050, 560)
        self._partial, self._closed = partial, False
        self.model = SpecialFilesModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSortRole(SORT_ROLE)
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self.view.doubleClicked.connect(self._select)
        for column, width in ((0, 180), (1, 210), (2, 135), (3, 100), (4, 350)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        self.hint = QLabel(tr("special_hint"))
        self.hint.setWordWrap(True)
        self.status = QLabel(tr("special_reading"))
        self.status.setWordWrap(True)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (self.hint, self.view, self.status, self.stop_button, buttons):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self.worker = SpecialFilesWorker(root, self)
        self.worker.ready.connect(self._show)
        self.worker.start()

    def _show(self, result: SpecialFiles) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self.stop_button.setEnabled(False)
        self.model.set_rows(result.rows)
        self.status.setText(tr("special_summary", shown=format_count(len(result.rows)),
                               count=format_count(result.count),
                               size=format_size(result.logical, self.model.unit),
                               allocated=format_size(result.allocated, self.model.unit),
                               unknown=format_count(result.unknown)) + (" " + tr("special_partial")
                                                                      if self._partial or result.incomplete else ""))

    def _select(self, index) -> None:
        node = index.data(NODE_ROLE)
        if isinstance(node, Node):
            self.selected.emit(node)
            self.accept()

    def stop(self) -> None:
        """Cancel metadata enumeration; no incomplete list is presented as complete."""
        self.worker.cancel.set()
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def shutdown(self) -> None:
        """Invalidate queued replies and join the owned worker before destruction."""
        self._closed = True
        self.worker.cancel.set()
        wait_for(self.worker)

    def done(self, result: int) -> None:
        """Join background enumeration before closing."""
        self.shutdown()
        super().done(result)
