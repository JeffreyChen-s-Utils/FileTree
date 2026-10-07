"""Lazy read-only Users tab over captured file owners, with replaceable owned analysis threads."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_share, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.owners import OwnerInventory, OwnerStat, owner_stats
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel


class UsersModel(_TableModel[OwnerStat]):
    """Numeric-sort owner totals, with a translated explicit unknown-identity row."""

    def build_columns(self) -> Sequence[Column[OwnerStat]]:
        """Expose account, stable identity, named logical/allocation bytes, file count and logical share."""
        return (
            Column("column_owner", lambda row: row.name or tr("owner_unknown"), lambda row: row.name),
            Column("column_owner_id", lambda row: row.identifier or tr("owner_unknown"), lambda row: row.identifier),
            Column("column_size", lambda row: format_size(row.size, self.unit), lambda row: row.size, True),
            Column("column_allocated", lambda row: format_size(row.allocated, self.unit),
                   lambda row: row.allocated, True),
            Column("column_files", lambda row: format_count(row.files), lambda row: row.files, True),
            Column("column_share", lambda row: format_share(row.share), lambda row: row.share, True),
        )

    def extra_data(self, row: OwnerStat, role: int) -> str | None:
        """Keep a full account name and stable identity accessible when the visible cell is elided."""
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.name + "\n" + row.identifier if row.identifier else tr("owner_unknown")
        return None


class UsersWorker(QThread):
    """Aggregate and resolve account names outside the GUI; cancellation emits no partial inventory."""

    ready = Signal(object)

    def __init__(self, root: Node, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.cancel = root, threading.Event()

    def run(self) -> None:
        """Query recorded ownership and suppress replies canceled during the final account lookup."""
        result = owner_stats(self.root, cancel=self.cancel)
        if result is not None and not self.cancel.is_set():
            self.ready.emit(result)


class UsersPanel(QWidget):
    """One whole-root owner view, refreshed after mutations and queried only while active."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = UsersModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.view.setColumnWidth(1, 250)
        self.view.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        install_copy(self.view)
        self.status, self.hint = QLabel(), QLabel()
        for label in (self.status, self.hint):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.refresh_button, self.stop_button = QPushButton(), QPushButton()
        self.refresh_button.clicked.connect(self.refresh)
        self.stop_button.clicked.connect(self.stop)
        self._root: Node | None = None
        self._inventory: OwnerInventory | None = None
        self._current: UsersWorker | None = None
        self._running: set[UsersWorker] = set()
        self._active = self._partial = False
        bar = QHBoxLayout()
        bar.addWidget(self.status, 1)
        bar.addWidget(self.refresh_button)
        bar.addWidget(self.stop_button)
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.hint)
        layout.addWidget(self.view, 1)
        self.retranslate()

    @property
    def busy(self) -> bool:
        """Whether the currently displayed scope still has an analysis in progress."""
        return self._current is not None

    def set_root(self, root: Node | None, *, partial: bool = False) -> None:
        """Invalidate old groups after a scan/branch replacement/move, preserving whole-root scope."""
        self._root, self._partial = root, partial
        self.refresh()

    def set_active(self, active: bool) -> None:
        """Run lazy analysis on tab activation; hiding cancels only an unfinished query."""
        self._active = active
        if not active:
            self.stop()
        elif self._inventory is None and not self.busy:
            self.refresh()

    def refresh(self) -> None:
        """Reaggregate recorded files; no scanned-file owner queries occur here."""
        self.stop()
        self._inventory = None
        self.model.set_rows([])
        if self._active and self._root is not None:
            worker = UsersWorker(self._root, self)
            self._current = worker
            self._running.add(worker)
            worker.ready.connect(lambda rows: self._show(worker, rows))
            worker.finished.connect(lambda: self._finished(worker))
            worker.finished.connect(worker.deleteLater)
            worker.start()
        self.retranslate()

    def stop(self, *, wait: bool = False) -> None:
        """Cancel owned analyses and optionally join current OS account lookups before destruction."""
        self._current = None
        for worker in self._running.copy():
            worker.cancel.set()
            if wait:
                wait_for(worker)
        self.retranslate()

    def set_unit(self, unit: str = AUTO_UNIT) -> None:
        """Format cached rows and summary in the chosen unit."""
        self.model.unit = unit
        self.retranslate()

    def retranslate(self) -> None:
        """Refresh translated captions and unknown identities without requerying accounts."""
        self.model.refresh()
        self.refresh_button.setText(tr("owners_refresh"))
        self.stop_button.setText(tr("action_stop"))
        self.stop_button.setEnabled(self.busy)
        self.refresh_button.setEnabled(self._root is not None and not self.busy)
        self.hint.setText(tr("owners_hint"))
        if self.busy:
            self.status.setText(tr("owners_reading"))
        elif self._inventory is None:
            self.status.setText(tr("owners_unqueried"))
        else:
            row = self._inventory
            text = tr("owners_summary", count=format_count(row.count), shown=format_count(len(row.rows)),
                      files=format_count(row.files), size=format_size(row.size, self.model.unit),
                      unknown_files=format_count(row.unknown_files), unknown_size=format_size(row.unknown_size,
                                                                                            self.model.unit))
            self.status.setText(text + ("\n" + tr("owners_partial") if row.incomplete or self._partial else ""))

    def _show(self, worker: UsersWorker, rows: OwnerInventory) -> None:
        if self._current is worker and not worker.cancel.is_set():
            self._inventory = rows
            self.model.set_rows(rows.rows)

    def _finished(self, worker: UsersWorker) -> None:
        self._running.discard(worker)
        if self._current is worker:
            self._current = None
            self.retranslate()
