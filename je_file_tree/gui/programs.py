"""Read-only installation metadata, matched scan totals and the fixed OS uninstall settings entry."""

from __future__ import annotations

from collections.abc import Sequence
import sys
import threading
from typing import Any

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QLabel, QPushButton,
                              QTableView, QVBoxLayout, QWidget)

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.programs import Program, Programs, installed_programs
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel
from je_file_tree.gui.tree_model import NODE_ROLE


def _size(amount: int | None, unit: str) -> str:
    return tr("size_unknown") if amount is None else format_size(amount, unit)


class ProgramsModel(_TableModel[Program]):
    """Reported and recorded sizes are separate columns; overlapping installations are never summed."""

    def build_columns(self) -> Sequence[Column[Program]]:
        """Name/provider/version/publisher, reported and scanned sizes, coverage and installation path."""
        return (Column("program_name", lambda row: row.name, lambda row: row.name.casefold()),
                Column("program_source", lambda row: tr("program_" + row.source), lambda row: row.source),
                Column("program_reported", lambda row: _size(row.reported, self.unit),
                       lambda row: row.reported if row.reported is not None else -1, numeric=True),
                Column("program_scanned", lambda row: _size(row.node.size if row.node is not None else None, self.unit),
                       lambda row: row.node.size if row.node is not None else -1, numeric=True),
                Column("program_allocated", lambda row: _size(row.node.allocated if row.node else None, self.unit),
                       lambda row: row.node.allocated if row.node else -1, numeric=True),
                Column("program_coverage", lambda row: tr("program_outside" if row.node is None else
                                                         "history_complete" if row.complete else "history_incomplete"),
                       lambda row: row.complete),
                Column("program_version", lambda row: row.version, lambda row: row.version),
                Column("program_publisher", lambda row: row.publisher, lambda row: row.publisher),
                Column("program_location", lambda row: row.location or tr("size_unknown"), lambda row: row.location))

    def extra_data(self, row: Program, role: int) -> Any:
        """Expose only an exact nonlinked recorded folder for tree activation."""
        if role == NODE_ROLE:
            return row.node
        return row.location if role == Qt.ItemDataRole.ToolTipRole else None


class ProgramsWorker(QThread):
    """Read registrations and small snapshot-guarded manifests off the GUI thread."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, root: Node, parent: QWidget, *, partial: bool = False) -> None:
        super().__init__(parent)
        self.root, self.partial, self.cancel = root, partial, threading.Event()

    def run(self) -> None:
        """Discard canceled inventories and report unexpected OS/metadata failures visibly."""
        try:
            result = installed_programs(self.root, partial=self.partial, cancel=self.cancel)
        except (OSError, ValueError) as error:
            if not self.cancel.is_set():
                self.failed.emit(str(error))
            return
        if result is not None and not self.cancel.is_set():
            self.ready.emit(result)


class ProgramsDialog(QDialog):
    """Review installer/game names and known totals; all uninstalling remains in the OS/launcher."""

    selected = Signal(object)

    def __init__(self, root: Node, unit: str, parent: QWidget, *, partial: bool = False) -> None:
        super().__init__(parent)
        self._closed = False
        self.setWindowTitle(tr("action_programs"))
        self.resize(1200, 580)
        self.model = ProgramsModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(3, Qt.SortOrder.DescendingOrder)
        self.view.doubleClicked.connect(self._select)
        for column, width in enumerate((240, 150, 150, 150, 160, 240, 160, 190, 440)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        hint = QLabel(tr("program_hint"))
        hint.setWordWrap(True)
        self.status = QLabel(tr("program_reading"))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.os_button = QPushButton(tr("program_uninstall_page"))
        self.os_button.setVisible(sys.platform == "win32")
        self.os_button.clicked.connect(self.open_uninstall_page)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (hint, self.view, self.status, self.os_button, self.stop_button, close):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self.worker = ProgramsWorker(root, self, partial=partial)
        self.worker.ready.connect(self._show)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _show(self, result: Programs) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self.model.set_rows(result.rows)
        self.status.setText(tr("program_summary", shown=format_count(len(result.rows)),
                               count=format_count(result.count),
                               issues=format_count(result.issues)))
        self.stop_button.setEnabled(False)

    def _failed(self, reason: str) -> None:
        if not self._closed and not self.worker.cancel.is_set():
            self.status.setText(tr("program_failed", reason=reason))
            self.stop_button.setEnabled(False)

    def _select(self, index) -> None:
        node = index.data(NODE_ROLE)
        if isinstance(node, Node):
            self.accept()
            self.selected.emit(node)

    def open_uninstall_page(self) -> None:
        """Open only the fixed Apps & Features URI; never execute a registry-provided command."""
        if sys.platform == "win32" and not QDesktopServices.openUrl(QUrl("ms-settings:appsfeatures")):
            self.status.setText(tr("program_open_failed"))

    def stop(self) -> None:
        """Cancel between folders/registration keys/manifests; suppress partial results."""
        self.worker.cancel.set()
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def shutdown(self) -> None:
        """Reject late replies and join the owned worker before destroying the view."""
        self._closed = True
        self.worker.cancel.set()
        wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: wait for cancellation on Close, Escape or tree activation."""
        self.shutdown()
        super().done(result)
