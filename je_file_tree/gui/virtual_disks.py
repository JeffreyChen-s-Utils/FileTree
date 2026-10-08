"""Bounded read-only virtual-disk inventory and explicit native-header queries on owned workers."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
import sys
import threading
from typing import Any
import uuid

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDialogButtonBox, QHBoxLayout, QLabel, QPushButton,
                              QTableView, QVBoxLayout, QWidget)

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.operation_journal import OperationJournal
from je_file_tree.core.virtual_disks import VirtualDisk, VirtualDisks, find_virtual_disks
from je_file_tree.core.virtual_disk_info import VirtualDiskInfo, inspect_virtual_disk
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.reasons import problem_text
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel
from je_file_tree.gui.virtual_disk_compaction import VirtualDiskCompactionDialog


@dataclass(frozen=True, slots=True)
class DiskRow:
    """An immutable candidate and optional explicitly queried native observation/error."""

    disk: VirtualDisk
    info: VirtualDiskInfo | None = None
    error: str = ""


def _amount(row: DiskRow, field: str) -> int | None:
    return getattr(row.disk, field) if field in ("size", "allocated", "guest_used") else (
        getattr(row.info, field) if row.info is not None else None)


def _state(row: DiskRow) -> str:
    if row.error:
        return row.error
    if row.disk.issue:
        return tr("vd_issue_" + row.disk.issue) if row.disk.issue in (
            "unverified", "unavailable", "changed", "duplicate_hard_links") else problem_text(row.disk.issue)
    if row.disk.kind not in ("vhd", "vhdx"):
        return tr("vd_unsupported")
    if row.info is None:
        return tr("vd_not_queried")
    kind = {2: "fixed", 3: "dynamic", 4: "differencing"}[row.info.subtype]
    return tr("vd_" + kind) + "; " + tr("vd_loaded" if row.info.loaded else "vd_detached")


class VirtualDisksModel(_TableModel[DiskRow]):
    """Backing-file length/allocation, virtual capacity/provider bytes and unknown guest usage stay separate."""

    def _size_column(self, field: str, title: str) -> Column[DiskRow]:
        def text(row):
            amount = _amount(row, field)
            return tr("size_unknown") if amount is None else format_size(amount, self.unit)
        return Column(title, text, lambda row: -1 if _amount(row, field) is None else _amount(row, field), numeric=True)

    def build_columns(self) -> Sequence[Column[DiskRow]]:
        """Keep native and estimated observations separate; never treat unknown guest usage as zero."""
        return (Column("vd_name", lambda row: row.disk.name, lambda row: row.disk.name.casefold()),
                Column("vd_kind", lambda row: row.disk.kind.upper(), lambda row: row.disk.kind),
                Column("vd_source", lambda row: tr("vd_source_" + row.disk.source), lambda row: row.disk.source),
                self._size_column("size", "vd_length"), self._size_column("allocated", "vd_allocation"),
                self._size_column("virtual_size", "vd_capacity"), self._size_column("physical_size", "vd_physical"),
                self._size_column("guest_used", "vd_guest"), Column("namespace_status", _state, _state),
                Column("program_location", lambda row: row.disk.path, lambda row: row.disk.path.casefold()))

    def extra_data(self, row: DiskRow, role: int) -> Any:
        """Expose immutable rows for explicit selection and literal complete-path/native-UUID tooltips."""
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role == Qt.ItemDataRole.ToolTipRole:
            identifier = str(uuid.UUID(bytes_le=row.info.identifier)) if row.info and row.info.identifier else ""
            return "\n".join((row.disk.path, _state(row), identifier))
        return None


class VirtualDisksWorker(QThread):
    """Discover extension/provider candidates off the GUI thread without opening headers/guests."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, root: Node, parent: QWidget, *, partial: bool = False) -> None:
        super().__init__(parent)
        self.root, self.partial, self.cancel = root, partial, threading.Event()

    def run(self) -> None:
        """Canceled inventories never publish late rows or native-query authority."""
        try:
            result = find_virtual_disks(self.root, partial=self.partial, cancel=self.cancel)
        except (OSError, ValueError) as exc:
            if not self.cancel.is_set():
                self.failed.emit(str(exc))
            return
        if result is not None and not self.cancel.is_set():
            self.ready.emit(result)


class VirtualDiskInfoWorker(QThread):
    """Explicitly query one frozen candidate; synchronous native calls finish before close can join."""

    ready = Signal(object, str)

    def __init__(self, disk: VirtualDisk, parent: QWidget) -> None:
        super().__init__(parent)
        self.disk, self.cancel = disk, threading.Event()

    def run(self) -> None:
        """Read-only native errors remain visible; cancellation suppresses late observations."""
        try:
            info, error = inspect_virtual_disk(self.disk, cancel=self.cancel), ""
        except (OSError, ValueError) as exc:
            info, error = None, str(exc)
        if not self.cancel.is_set():
            self.ready.emit(info, error)


class VirtualDisksDialog(WorkerDialog):
    """Backing-file inventory and an explicit owned compaction review; discovery remains read-only."""

    selected = Signal(object)
    execution_requested = Signal()

    def __init__(self, root: Node, unit: str, parent: QWidget, *, partial: bool = False,
                 journal: OperationJournal | None = None) -> None:
        super().__init__(parent)
        self._closed = False
        self.journal, self.changed = journal, False
        self.compaction: VirtualDiskCompactionDialog | None = None
        self.info_worker: VirtualDiskInfoWorker | None = None
        self.setWindowTitle(tr("action_virtual_disks"))
        self.resize(1400, 640)
        self.model = VirtualDisksModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(4, Qt.SortOrder.DescendingOrder)
        for column, width in enumerate((200, 90, 150, 130, 140, 140, 150, 140, 310, 480)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        self.hint, self.status = QLabel(tr("vd_hint")), QLabel(tr("vd_reading"))
        for label in (self.hint, self.status):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
        layout = QVBoxLayout(self)
        for widget in (self.hint, self.view, self.status):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self._controls(layout)
        self.worker = VirtualDisksWorker(root, self, partial=partial)
        self.worker.ready.connect(self._show)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._buttons)
        self.view.selectionModel().currentChanged.connect(self._buttons)
        self.worker.start()

    def _controls(self, layout: QVBoxLayout) -> None:
        buttons = QHBoxLayout()
        self.info_button = QPushButton(tr("vd_inspect"))
        self.info_button.setVisible(sys.platform == "win32")
        self.info_button.clicked.connect(self.inspect_selected)
        self.select_button = QPushButton(tr("vd_select"))
        self.select_button.clicked.connect(self.select_recorded)
        self.compact_button = QPushButton(tr("vc_title"))
        self.compact_button.setVisible(sys.platform == "win32")
        self.compact_button.clicked.connect(self.compact_selected)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        for button in (self.info_button, self.compact_button, self.select_button, self.stop_button):
            buttons.addWidget(button)
        self.info_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.compact_button.setEnabled(False)
        layout.addLayout(buttons)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def _current(self) -> DiskRow | None:
        row = self.view.currentIndex().data(Qt.ItemDataRole.UserRole)
        return row if isinstance(row, DiskRow) else None

    def _buttons(self) -> None:
        row = self._current()
        idle = (not self._closed and not self.worker.isRunning() and self.info_worker is None
                and self.compaction is None)
        self.info_button.setEnabled(bool(idle and sys.platform == "win32" and row and not row.disk.issue
                                         and not self.changed and row.disk.snapshot
                                         and row.disk.kind in ("vhd", "vhdx")))
        self.compact_button.setEnabled(self.info_button.isEnabled() and self.journal is not None)
        self.select_button.setEnabled(bool(idle and row and row.disk.node is not None))

    def _show(self, result: VirtualDisks) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self.model.set_rows([DiskRow(disk) for disk in result.rows])
        self.status.setText(tr("vd_summary", shown=format_count(len(result.rows)), count=format_count(result.count),
                               issues=format_count(result.issues),
                               coverage=tr("history_incomplete" if result.incomplete else "history_complete")))
        self.stop_button.setEnabled(False)
        self._buttons()

    def _failed(self, reason: str) -> None:
        if not self._closed and not self.worker.cancel.is_set():
            self.status.setText(tr("vd_failed", reason=reason))
            self.stop_button.setEnabled(False)

    def inspect_selected(self) -> None:
        """Read only the explicitly selected captured VHD/VHDX; no automatic header/guest query."""
        self._buttons()
        row = self._current()
        if not self.info_button.isEnabled() or row is None:
            return
        worker = VirtualDiskInfoWorker(row.disk, self)
        self.info_worker = worker
        worker.ready.connect(lambda info, error: self._information(worker, info, error))
        worker.finished.connect(self._info_finished)
        self.status.setText(tr("vd_querying", path=row.disk.path))
        self.stop_button.setEnabled(True)
        self._buttons()
        worker.start()

    def _information(self, worker: VirtualDiskInfoWorker, info: VirtualDiskInfo | None, error: str) -> None:
        if self._closed or worker is not self.info_worker or worker.cancel.is_set():
            return
        rows = self.model.rows()
        self.model.set_rows([replace(row, info=info, error=error) if row.disk is worker.disk else row for row in rows])
        self.status.setText(tr("vd_failed", reason=error) if error else tr("vd_information_hint"))

    def _info_finished(self) -> None:
        worker = self.info_worker
        if worker is not None:
            wait_for(worker)
            worker.deleteLater()
            self.info_worker = None
        if not self._closed:
            self.stop_button.setEnabled(False)
            self._buttons()

    def select_recorded(self) -> None:
        """Activate only the original recorded node; external provider paths have no tree action."""
        self._buttons()
        row = self._current()
        if self.select_button.isEnabled() and row is not None:
            self.accept()
            self.selected.emit(row.disk.node)

    def compact_selected(self) -> None:
        """Own the selected frozen disk's review, durable audit and joined lifetime before rescan."""
        self._buttons()
        row = self._current()
        if not self.compact_button.isEnabled() or row is None or self.journal is None:
            return
        dialog = VirtualDiskCompactionDialog(row.disk, self.journal, self.model.unit, self)
        self.compaction = dialog
        dialog.execution_requested.connect(self.execution_requested)
        self._buttons()
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            self.changed |= dialog.changed
            self.compaction = None
            dialog.deleteLater()
            self._buttons()
        if self.changed and not self._closed:
            self.status.setText(tr("vc_stale"))
            self.model.set_rows([replace(item, info=None, error=tr("vc_stale"))
                                 if item.disk is row.disk else item for item in self.model.rows()])

    def stop(self) -> None:
        """Cancel inventory/native replies; active synchronous native calls are joined on close."""
        self.worker.cancel.set()
        if self.info_worker is not None:
            self.info_worker.cancel.set()
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def shutdown(self, *, wait: bool = True) -> None:
        """Ignore late replies and join all owned work before destruction."""
        self._closed = True
        if self.compaction is not None:
            self.compaction.reject()
            self.compaction.shutdown(wait=wait)
        self.worker.cancel.set()
        if self.info_worker is not None:
            self.info_worker.cancel.set()
            if wait:
                wait_for(self.info_worker)
        if wait:
            wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: Close/Escape/activation cannot destroy a current native header query."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
