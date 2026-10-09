"""Project and managed-store inventories, sharing the application's reviewed Trash workflow."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDialogButtonBox, QLabel, QPushButton,
                              QTableView, QVBoxLayout, QWidget)

from je_file_tree.core.cleanup_policy import CleanupPolicy
from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.projects import Project, Projects, projects
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel
from je_file_tree.gui.tree_model import NODE_ROLE


class ProjectsModel(_TableModel[Project]):
    """Known source/other, Git and generated logical bytes, plus recorded allocation and coverage."""

    def build_columns(self) -> Sequence[Column[Project]]:
        """Project/store path, kinds, known breakdown, disk estimate and incomplete flag."""
        return (Column("project_path", lambda row: row.node.path, lambda row: row.node.path),
                Column("project_kind", lambda row: ", ".join(tr("project_git_kind" if kind == "git"
                                                               else "project_" + kind) for kind in row.kinds),
                       lambda row: row.kinds),
                Column("project_other", lambda row: format_size(row.other, self.unit), lambda row: row.other,
                       numeric=True),
                Column("project_git", lambda row: format_size(row.git, self.unit), lambda row: row.git, numeric=True),
                Column("project_generated", lambda row: format_size(row.generated, self.unit),
                       lambda row: row.generated, numeric=True),
                Column("column_allocated", lambda row: format_size(row.node.allocated, self.unit),
                       lambda row: row.node.allocated, numeric=True),
                Column("project_coverage", lambda row: tr("project_partial" if row.incomplete else "project_recorded"),
                       lambda row: row.incomplete))

    def extra_data(self, row: Project, role: int) -> Any:
        """Allow activation to select the scanned project node in the main tree."""
        return row.node if role == NODE_ROLE else None


class ProjectsWorker(QThread):
    """Survey recorded project data and current policy/coverage without accessing files."""

    ready = Signal(object)

    def __init__(self, root: Node, policy: CleanupPolicy, partial: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.policy, self.partial, self.cancel = root, policy, partial, threading.Event()

    def run(self) -> None:
        """Emit only a complete, uncanceled inventory."""
        result = projects(self.root, policy=self.policy, partial=self.partial, cancel=self.cancel)
        if result is not None and not self.cancel.is_set():
            self.ready.emit(result)


class ProjectsDialog(WorkerDialog):
    """Review eligible generated entries only through MainWindow.move_to_trash."""

    selected = Signal(object)
    review_requested = Signal(object)

    def __init__(self, root: Node, unit: str, policy: CleanupPolicy, *, partial: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_projects"))
        self.resize(1200, 610)
        self._closed = False
        self.model = ProjectsModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(4, Qt.SortOrder.DescendingOrder)
        for column, width in enumerate((330, 155, 145, 110, 125, 110, 125)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        self.view.doubleClicked.connect(self._select)
        self.view.selectionModel().currentChanged.connect(self._buttons)
        hint = QLabel(tr("project_hint"))
        hint.setWordWrap(True)
        self.status = QLabel(tr("project_reading"))
        self.status.setWordWrap(True)
        self.review = QPushButton(tr("project_review"))
        self.review.setEnabled(False)
        self.review.clicked.connect(self.review_generated)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (hint, self.view, self.status, self.review, self.stop_button, close):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self.worker = ProjectsWorker(root, policy, partial, self)
        self.worker.ready.connect(self._show)
        self.worker.start()

    def _show(self, result: Projects) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self.model.set_rows(result.rows)
        self.status.setText(tr("project_summary", shown=format_count(len(result.rows)),
                               count=format_count(result.count)))
        self.stop_button.setEnabled(False)
        self._buttons()

    def _buttons(self) -> None:
        index = self.view.currentIndex()
        row = self.model.row_at(self.proxy.mapToSource(index).row()) if index.isValid() else None
        enabled = row is not None and bool(row.reviewable.nodes) and not self.worker.cancel.is_set()
        self.review.setEnabled(enabled)
        self.review.setToolTip(tr("project_review_count", shown=format_count(len(row.reviewable.nodes)),
                                 count=format_count(row.reviewable.count)) if row is not None else "")

    def _select(self, index) -> None:
        node = index.data(NODE_ROLE)
        if isinstance(node, Node):
            self.selected.emit(node)
            self.accept()

    def review_generated(self) -> None:
        """Close this view and ask the central queue to review at most 1,000 eligible entries."""
        index = self.view.currentIndex()
        row = self.model.row_at(self.proxy.mapToSource(index).row()) if index.isValid() else None
        if row is None or not row.reviewable.nodes or self.worker.cancel.is_set():
            return
        self.accept()
        self.review_requested.emit(list(row.reviewable.nodes))

    def stop(self) -> None:
        """Cancel the inventory and leave no incomplete result enabled for review."""
        self.worker.cancel.set()
        self.review.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def shutdown(self, *, wait: bool = True) -> None:
        """Reject late replies and join before the modal view is destroyed."""
        self._closed = True
        self.worker.cancel.set()
        if wait:
            wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: finish only after the recorded-data worker ends."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
