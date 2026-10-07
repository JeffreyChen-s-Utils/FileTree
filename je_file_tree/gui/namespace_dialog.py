"""Every-pair namespace preview, explicit collision choices and cancel/join operation lifecycle."""

from collections.abc import Sequence
import os

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.core.formatting import format_count
from je_file_tree.core.namespace_moves import NamespaceItem, NamespacePlan, NamespaceResult
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.namespace_worker import NamespaceOperationWorker, NamespacePreviewWorker, NamespaceRequest
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel


def namespace_reason(item: NamespaceItem) -> str:
    """Translate stable refusal keys; preserve literal bounded OS error details."""
    return item.detail if item.reason == "error" else tr("namespace_reason_" + (item.reason or "ready"))


class NamespaceModel(_TableModel[NamespaceItem]):
    """Read-only exact source/destination/status rows, with complete text available for copying."""

    def build_columns(self) -> Sequence[Column[NamespaceItem]]:
        """Each displayed destination is the exact name execution may attempt."""
        return (
            Column("namespace_source_name", lambda item: os.path.basename(item.source),
                   lambda item: os.path.basename(item.source).lower()),
            Column("namespace_source", lambda item: item.source, lambda item: item.source.lower()),
            Column("namespace_destination_name", lambda item: os.path.basename(item.destination),
                   lambda item: os.path.basename(item.destination).lower()),
            Column("namespace_destination", lambda item: item.destination, lambda item: item.destination.lower()),
            Column("namespace_status", namespace_reason, namespace_reason),
        )

    def extra_data(self, row: NamespaceItem, role: int) -> str | None:
        """Keep paths and refusal reasons literal in tooltips."""
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{row.source}\n{row.destination}\n{namespace_reason(row)}"
        return None


class NamespaceDialog(QDialog):
    """Review batch paths, confirm eligible rows, freeze controls and join owned workers on close."""

    def __init__(self, root: Node, nodes: Sequence[Node], unit: str, parent: QWidget, *, rename: bool) -> None:
        super().__init__(parent)
        self.root, self.nodes, self.unit, self.rename = root, tuple(nodes), unit, rename
        self._closed = self._stopped = False
        self._reported = False
        self.worker: NamespacePreviewWorker | None = None
        self.operation: NamespaceOperationWorker | None = None
        self.plan: NamespacePlan | None = None
        self.changed = False
        self.setWindowTitle(tr("menu_rename" if rename else "menu_move_folder"))
        self.resize(1140, 650)
        self._build_controls()
        self._build_table()
        layout = QVBoxLayout(self)
        layout.addWidget(self.hint)
        layout.addLayout(self.fields)
        for widget in (self.collision, self.preview_button, self.view, self.status, self.output,
                       self.apply_button, self.stop_button, self.close_buttons):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self._query()

    def _build_controls(self) -> None:
        self.hint = QLabel(tr("namespace_rename_hint" if self.rename else "namespace_move_hint"))
        self.hint.setWordWrap(True)
        self.hint.setTextFormat(Qt.TextFormat.PlainText)
        value = self.nodes[0].name if self.rename and len(self.nodes) == 1 else "{n}-{name}"
        self.destination = QLineEdit(value if self.rename else self.root.path)
        self.destination.setAccessibleName(tr("namespace_pattern" if self.rename else "namespace_destination"))
        self.destination.textChanged.connect(self._invalidate)
        self.browse = QPushButton(tr("menu_move_folder"))
        self.browse.clicked.connect(self._browse)
        self.browse.setVisible(not self.rename)
        self.fields = QHBoxLayout()
        self.fields.addWidget(self.destination, 1)
        self.fields.addWidget(self.browse)
        self.collision = QComboBox()
        for value in ("skip", "rename"):
            self.collision.addItem(tr("namespace_collision_" + value), value)
        self.collision.currentIndexChanged.connect(self._invalidate)
        self.preview_button = QPushButton(tr("namespace_preview"))
        self.preview_button.clicked.connect(self._query)
        self.apply_button = QPushButton(tr("namespace_apply"))
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        self.close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.close_buttons.rejected.connect(self.reject)
        self.status = QLabel(tr("namespace_reading"))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(130)
        self.output.hide()

    def _build_table(self) -> None:
        self.model = NamespaceModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for column, width in enumerate((150, 330, 150, 330, 170)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("menu_move_folder"), self.destination.text())
        if path:
            self.destination.setText(path)

    def _invalidate(self, _value: object = None) -> None:
        if self.operation is not None:
            return
        if self.worker is not None:
            self.worker.cancel.set()
        self.plan = None
        self.model.set_rows([])
        self.apply_button.setEnabled(False)
        self.status.setText(tr("namespace_preview_needed"))

    def _query(self) -> None:
        if self._closed or self.operation is not None:
            return
        if self.worker is not None:
            self.worker.cancel.set()
            wait_for(self.worker)
            self.worker.deleteLater()
        self._stopped, self.plan = False, None
        self.model.set_rows([])
        self.output.hide()
        self.status.setText(tr("namespace_reading"))
        self.apply_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        value = self.destination.text()
        request = NamespaceRequest(self.root, self.nodes, None if self.rename else value,
                                   value if self.rename else None, self.collision.currentData())
        worker = NamespacePreviewWorker(request, self)
        self.worker = worker
        worker.ready.connect(lambda plan: self.worker is worker and self._show(plan))
        worker.failed.connect(lambda reason: self.worker is worker and not worker.cancel.is_set()
                              and self._failed(reason))
        worker.finished.connect(lambda: self.worker is worker and self.operation is None
                                and self.stop_button.setEnabled(False))
        worker.start()

    def _show(self, plan: NamespacePlan) -> None:
        if self._closed or self._stopped or self.worker is None or self.worker.cancel.is_set():
            return
        self.plan = plan
        self.model.set_rows(plan.items)
        eligible = sum(not item.reason for item in plan.items)
        self.status.setText(tr("namespace_summary", total=format_count(len(plan.items)),
                               ready=format_count(eligible), skipped=format_count(len(plan.items) - eligible)))
        self.apply_button.setEnabled(bool(eligible))

    def _apply(self) -> None:
        plan = self.plan
        if self._closed or plan is None or self.operation is not None or self.worker.cancel.is_set():
            return
        eligible = [item for item in plan.items if not item.reason]
        if not eligible:
            return
        question = QMessageBox(QMessageBox.Icon.Question, self.windowTitle(), "",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        question.setTextFormat(Qt.TextFormat.PlainText)
        question.setText(tr("namespace_confirm", count=format_count(len(eligible)),
                            skipped=format_count(len(plan.items) - len(eligible))))
        question.setDetailedText("\n\n".join(f"{item.source}\n→ {item.destination}" for item in eligible))
        question.setDefaultButton(QMessageBox.StandardButton.No)
        if (question.exec() != QMessageBox.StandardButton.Yes or self.plan is not plan
                or self._closed or self.worker.cancel.is_set()):
            return
        self.changed = True
        worker = NamespaceOperationWorker(plan, self)
        self.operation = worker
        for control in (self.destination, self.browse, self.collision, self.preview_button, self.apply_button):
            control.setEnabled(False)
        self.stop_button.setEnabled(True)
        worker.progressed.connect(lambda done, total: not self._closed and self.status.setText(
            tr("namespace_progress", done=format_count(done), total=format_count(total))))
        worker.ready.connect(self._completed)
        worker.refreshing.connect(lambda path: not self._closed and self.status.setText(
            tr("namespace_refreshing", path=path)))
        worker.failed.connect(self._failed)
        worker.finished.connect(lambda: not self._closed and self.stop_button.setEnabled(False))
        worker.start()

    def _completed(self, result: NamespaceResult) -> None:
        if self._closed:
            return
        self._reported = True
        self.status.setText(tr("namespace_done", moved=format_count(len(result.moved)),
                               skipped=format_count(len(result.skipped)), failed=format_count(len(result.failed)))
                            + ("\n" + tr("scan_cancelled") if result.canceled else ""))
        lines = [f"{item.source}\n→ {item.destination}\n{reason}" for item, reason in result.failed]
        lines += [f"{item.source}\n→ {item.destination}\n{namespace_reason(item)}" for item, _ in result.skipped]
        lines += [tr("namespace_refreshed", path=path, files=format_count(files), errors=format_count(errors))
                  for path, files, errors in self.operation.refreshed]
        lines += [tr("namespace_refresh_failed", path=path, reason=reason)
                  for path, reason in self.operation.refresh_errors]
        if lines:
            self.output.setPlainText("\n\n".join(lines))
            self.output.show()

    def _failed(self, reason: str) -> None:
        if not self._closed:
            self.status.setText(tr("namespace_failed", reason=reason))
            self._reported = self.operation is not None

    def stop(self) -> None:
        """Cancel the current preview or stop an operation between entries."""
        if self.operation is not None:
            self.operation.cancel.set()
        elif self.worker is not None:
            self._stopped = True
            self.worker.cancel.set()
            self.apply_button.setEnabled(False)
            self.status.setText(tr("scan_cancelled"))
        self.stop_button.setEnabled(False)

    def shutdown(self) -> None:
        """Join both owned workers before result-tree edits or dialog destruction."""
        self._closed = True
        for worker in (self.worker, self.operation):
            if worker is not None:
                worker.cancel.set()
                wait_for(worker)

    def done(self, result: int) -> None:
        """Qt: closing requests cancellation and waits through the current native operation."""
        self.shutdown()
        self._report_unseen()
        super().done(result)

    def _report_unseen(self) -> None:
        worker = self.operation
        if self._reported or worker is None:
            return
        lines = [f"{path}: {reason}" for path, reason in worker.refresh_errors]
        if worker.result is not None:
            lines += [f"{item.source}\n→ {item.destination}\n{reason}" for item, reason in worker.result.failed]
        if worker.error:
            lines.append(worker.error)
        if lines:
            self._reported = True
            report = QMessageBox(QMessageBox.Icon.Warning, self.windowTitle(), "",
                                 QMessageBox.StandardButton.Ok, self.parentWidget())
            report.setTextFormat(Qt.TextFormat.PlainText)
            report.setText(tr("namespace_closed_errors"))
            report.setDetailedText("\n\n".join(lines))
            report.exec()
