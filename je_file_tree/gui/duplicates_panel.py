"""The Duplicates tab: files with the same content, grouped, with the space the extra copies take."""

from __future__ import annotations

import os

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from je_file_tree.core.duplicates import DEFAULT_MIN_SIZE, DuplicateGroup, DuplicateProgress, DuplicateResult
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_size, format_time
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import DuplicatesWorker
from je_file_tree.gui.tree_model import NODE_ROLE

MIN_SIZES = (1, 100 * 1024, DEFAULT_MIN_SIZE, 10 * 1024 * 1024, 100 * 1024 * 1024)
LISTED_GROUPS = 1000
_COLUMNS = ("column_name", "column_size", "column_folder", "column_modified")
_COLUMN_WIDTHS = {0: 200, 1: 80, 3: 125}
_FOLDER_COLUMN = 2
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class DuplicatesPanel(QWidget):
    """Looks for duplicates on request (a ``DuplicatesWorker``) and lists the groups, oldest copy first.

    ``set_root(None)`` stops a search and disables the panel (while a scan runs); ``prune`` drops
    files that left the tree (moved to the Recycle Bin, or in a rescanned folder).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.unit = AUTO_UNIT
        self.model = QStandardItemModel(self)
        self.view = _build_view(self.model)
        self.min_size = QComboBox()
        self.start_button = QPushButton()
        self.stop_button = QPushButton()
        self.select_extra = QPushButton()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self._size_label = QLabel()
        self._busy = QProgressBar()
        self._busy.setRange(0, 0)
        self._busy.setMaximumWidth(120)
        self._root: Node | None = None
        self._worker: DuplicatesWorker | None = None
        self._groups: list[DuplicateGroup] = []
        self._found: DuplicateResult | None = None
        self._progress: DuplicateProgress | None = None
        self._stopped = False
        self._assemble()
        self.retranslate()
        self.set_root(None)

    # --- public API -------------------------------------------------------

    @property
    def groups(self) -> list[DuplicateGroup]:
        """The groups found, as they stand after files left the tree."""
        return self._groups

    @property
    def running(self) -> bool:
        """Whether a search is running."""
        return self._worker is not None

    def set_root(self, root: Node | None) -> None:
        """Look for duplicates beneath ``root`` from now on (None: nothing to search, the panel is idle)."""
        self.stop()
        self._root = root
        self._groups = []
        self._found = None
        self._stopped = False
        self._rebuild()
        self._update()

    def start(self) -> None:
        """Start looking for duplicates of the size chosen or larger."""
        if self._root is None or self._worker is not None:
            return
        worker = DuplicatesWorker(self._root, int(self.min_size.currentData()), self)
        worker.progressed.connect(lambda progress: worker is self._worker and self._show_progress(progress))
        worker.succeeded.connect(lambda result: worker is self._worker and self._show_result(result))
        worker.cancelled.connect(lambda: worker is self._worker and self._finish(stopped=True))
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self._progress = None
        self._stopped = False
        self._update()
        worker.start()

    def stop(self, *, wait: bool = False) -> None:
        """Stop a running search (``wait``: until its thread has ended); what was found so far is dropped."""
        worker = self._worker
        if worker is None:
            return
        worker.stop()
        if wait:
            worker.wait()
        self._worker = None
        self._stopped = True
        self._update()

    def prune(self) -> None:
        """Drop files that are no longer in the tree, and groups left with a single file."""
        root = self._root
        if root is None or not self._groups:
            return
        kept = []
        for group in self._groups:
            files = [node for node in group.files if node.is_in(root)]
            if len(files) > 1:
                kept.append(DuplicateGroup(group.size, files))
        self._groups = kept
        self._rebuild()
        self._update()

    def select_extra_copies(self) -> None:
        """Select every file but the oldest of each group, ready for Delete."""
        selection = QItemSelection()
        for row in range(self.model.rowCount()):
            group = self.model.index(row, 0)
            count = self.model.rowCount(group)
            if count > 1:
                first = self.model.index(1, 0, group)
                last = self.model.index(count - 1, len(_COLUMNS) - 1, group)
                selection.select(first, last)
        self.view.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.view.setFocus()

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit``."""
        self.unit = unit
        self._rebuild()
        self._update()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self._size_label.setText(tr("duplicates_min_size"))
        current = self.min_size.currentData()
        self.min_size.blockSignals(True)
        self.min_size.clear()
        for size in MIN_SIZES:
            self.min_size.addItem(tr("duplicates_any_size") if size <= 1 else format_size(size), size)
        position = self.min_size.findData(current if current is not None else DEFAULT_MIN_SIZE)
        self.min_size.setCurrentIndex(max(0, position))
        self.min_size.blockSignals(False)
        self.start_button.setText(tr("duplicates_find"))
        self.stop_button.setText(tr("duplicates_stop"))
        self.select_extra.setText(tr("duplicates_select_extra"))
        self.select_extra.setToolTip(tr("duplicates_select_extra_tip"))
        self._rebuild()
        self._update()

    # --- building ---------------------------------------------------------

    def _assemble(self) -> None:
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(lambda: self.stop())  # noqa: PLW0108 - clicked(bool) must not reach stop()
        self.select_extra.clicked.connect(self.select_extra_copies)
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        for widget in (self._size_label, self.min_size, self.start_button, self.stop_button, self._busy):
            bar.addWidget(widget)
        bar.addStretch(1)
        bar.addWidget(self.select_extra)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.status)
        layout.addWidget(self.view, 1)

    def _rebuild(self) -> None:
        """Fill the list from ``_groups`` (the groups with the most extra space, up to ``LISTED_GROUPS``)."""
        self.model.clear()
        self.model.setHorizontalHeaderLabels([tr(key) for key in _COLUMNS])
        for group in self._groups[:LISTED_GROUPS]:
            head = QStandardItem(tr("duplicates_group", count=format_count(len(group.files)),
                                    size=format_size(group.size, self.unit),
                                    extra=format_size(group.extra, self.unit)))
            head.setEditable(False)
            for node in sorted(group.files, key=lambda file: (file.modified, file.path)):
                head.appendRow(_row(node.name, format_size(node.size, self.unit), os.path.dirname(node.path),
                                    format_time(node.modified), node=node))
            self.model.appendRow(head)
        for row in range(self.model.rowCount()):
            self.view.setFirstColumnSpanned(row, QModelIndex(), True)  # a group's line runs across the columns
        for column, width in _COLUMN_WIDTHS.items():
            self.view.setColumnWidth(column, width)
        self.view.header().setSectionResizeMode(_FOLDER_COLUMN, QHeaderView.ResizeMode.Stretch)
        self.view.expandAll()

    # --- a search ---------------------------------------------------------

    def _show_progress(self, progress: DuplicateProgress) -> None:
        self._progress = progress
        self._update()

    def _show_result(self, result: DuplicateResult) -> None:
        self._found = result
        self._groups = list(result.groups)
        self._rebuild()
        self._finish(stopped=False)

    def _finish(self, *, stopped: bool) -> None:
        self._worker = None
        self._stopped = stopped
        self._update()

    def _update(self) -> None:
        running = self._worker is not None
        self.min_size.setEnabled(self._root is not None and not running)
        self.start_button.setEnabled(self._root is not None and not running)
        self.stop_button.setEnabled(running)
        self._busy.setVisible(running)
        self.select_extra.setEnabled(bool(self._groups) and not running)
        self.status.setText(self._status_text())

    def _status_text(self) -> str:
        if self._worker is not None:
            progress = self._progress
            if progress is None:
                return tr("duplicates_starting")
            return tr("duplicates_running", files=format_count(progress.files_read),
                      total=format_count(progress.files_total), read=format_size(progress.bytes_read, self.unit),
                      bytes=format_size(progress.bytes_total, self.unit))
        if self._stopped:
            return tr("duplicates_stopped")
        if self._found is None:
            return tr("duplicates_hint")
        if not self._groups:
            return tr("duplicates_none")
        extra = sum(group.extra for group in self._groups)
        text = tr("duplicates_summary", groups=format_count(len(self._groups)), extra=format_size(extra, self.unit))
        if len(self._groups) > LISTED_GROUPS:
            text += " " + tr("duplicates_limited", shown=format_count(LISTED_GROUPS))
        if self._found.skipped:
            text += " " + tr("duplicates_skipped", count=format_count(self._found.skipped))
        return text


def _build_view(model: QStandardItemModel) -> QTreeView:
    view = QTreeView()
    view.setModel(model)
    view.setUniformRowHeights(True)
    view.setAlternatingRowColors(True)
    view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    view.header().setStretchLastSection(False)
    return view


def _row(*texts: str, node: Node | None = None) -> list[QStandardItem]:
    """One row of items; a file's row carries its node (``NODE_ROLE``) and its path as the tooltip."""
    items = []
    for column, text in enumerate(texts):
        item = QStandardItem(text)
        item.setEditable(False)
        if column == 1:
            item.setTextAlignment(_RIGHT)
        if node is not None:
            item.setData(node, NODE_ROLE)
            item.setToolTip(node.path)
        items.append(item)
    return items
