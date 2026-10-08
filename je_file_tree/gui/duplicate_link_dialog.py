"""Explicit hard-link review, complete literal paths and cancel/join lifetime for owned workers."""

from collections.abc import Sequence

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialogButtonBox, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.core.duplicate_link_ops import LinkOutcome, LinkResult
from je_file_tree.core.duplicate_links import LinkPlan
from je_file_tree.core.duplicates import DuplicateGroup
from je_file_tree.core.formatting import format_count
from je_file_tree.core.node import Node
from je_file_tree.core.operation_journal import OperationJournal
from je_file_tree.gui.duplicate_link_worker import LinkOperationWorker, LinkPreviewWorker
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog, queue_worker
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel


def link_reason(reason: str) -> str:
    """Translate existing refusal keys and keep native error text literal."""
    if not reason:
        return tr("namespace_reason_ready")
    try:
        return tr("trash_skip_" + reason)
    except KeyError:
        return reason


class LinkModel(_TableModel[LinkOutcome]):
    """Exact reviewed copy/keeper paths and observed status, copied without editing."""

    def build_columns(self) -> Sequence[Column[LinkOutcome]]:
        """Refused paths remain visible alongside eligible rows."""
        return (
            Column("link_copy", lambda row: row.pair.copy_path, lambda row: row.pair.copy_path.lower()),
            Column("link_keeper", lambda row: row.pair.keeper_path, lambda row: row.pair.keeper_path.lower()),
            Column("namespace_status", self._status, self._status),
        )

    @staticmethod
    def _status(row: LinkOutcome) -> str:
        return (tr("journal_status_linked") + ("; " + row.error if row.error else "")
                if row.linked else link_reason(row.error))

    def extra_data(self, row: LinkOutcome, role: int) -> str | None:
        """Keep complete paths/error/retained artifacts available in literal tooltips."""
        if role == Qt.ItemDataRole.ToolTipRole:
            return "\n".join((row.pair.copy_path, row.pair.keeper_path, self._status(row), *row.retained))
        return None


class DuplicateLinksDialog(WorkerDialog):
    """Review explicit keepers, require default-No approval and retain partial native results on close."""

    def __init__(self, root: Node, groups: Sequence[DuplicateGroup], journal: OperationJournal,
                 parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.journal = root, journal
        self.plan: LinkPlan | None = None
        self.operation: LinkOperationWorker | None = None
        self.changed = False
        self._closed = self._reported = False
        self.setWindowTitle(tr("link_title"))
        self.resize(1120, 650)
        self._build()
        self.worker = LinkPreviewWorker(root, tuple(groups), self)
        self.worker.ready.connect(self._show)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(lambda: not self._closed and self.operation is None
                                     and self.stop_button.setEnabled(False))
        self.worker.start()

    def _build(self) -> None:
        hint = QLabel(tr("link_hint"))
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)
        self.model = LinkModel(self)
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(self.model)
        proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        for number, width in enumerate((410, 410, 230)):
            self.view.setColumnWidth(number, width)
        install_copy(self.view)
        self.status = QLabel(tr("namespace_reading"))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(150)
        self.output.hide()
        self.apply_button = QPushButton(tr("link_apply"))
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (hint, self.view, self.status, self.output, self.apply_button, self.stop_button, close):
            layout.addWidget(widget, 1 if widget is self.view else 0)

    def _show(self, plan: LinkPlan) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self.plan = plan
        self.model.set_rows([LinkOutcome(pair, False, link_reason(pair.reason)) for pair in plan.pairs])
        ready = sum(not pair.reason for pair in plan.pairs)
        self.status.setText(tr("link_summary", total=format_count(len(plan.pairs)), ready=format_count(ready),
                               skipped=format_count(len(plan.pairs) - ready)))
        self.apply_button.setEnabled(bool(ready))

    def _apply(self) -> None:
        plan = self.plan
        if self._closed or plan is None or self.operation is not None or self.worker.cancel.is_set():
            return
        ready = sum(not pair.reason for pair in plan.pairs)
        if not ready:
            return
        question = QMessageBox(QMessageBox.Icon.Question, self.windowTitle(), "",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        question.setTextFormat(Qt.TextFormat.PlainText)
        question.setText(tr("link_confirm", count=format_count(ready), skipped=format_count(len(plan.pairs) - ready)))
        question.setDetailedText("\n\n".join(f"{pair.copy_path}\n→ {pair.keeper_path}\n{link_reason(pair.reason)}"
                                              for pair in plan.pairs))
        question.setDefaultButton(QMessageBox.StandardButton.No)
        if (question.exec() != QMessageBox.StandardButton.Yes or self._closed or self.plan is not plan
                or self.worker.cancel.is_set()):
            return
        self.changed = True
        self.apply_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.operation = LinkOperationWorker(plan, self.journal, self)
        self.operation.progressed.connect(lambda path: not self._closed and self.status.setText(
            tr("link_progress", path=path)))
        self.operation.ready.connect(self._completed)
        self.operation.finished.connect(lambda: not self._closed and self.stop_button.setEnabled(False))
        worker = self.operation
        queue_worker(worker, lambda: not self._closed and self.operation is worker
                     and self.plan is plan and not worker.cancel.is_set(), self)

    def _completed(self, result: LinkResult) -> None:
        if self._closed:
            return
        self._reported = True
        self.model.set_rows(result.outcomes)
        linked = sum(outcome.linked for outcome in result.outcomes)
        self.status.setText(tr("link_done", linked=format_count(linked),
                               other=format_count(len(result.outcomes) - linked))
                            + ("\n" + tr("scan_cancelled") if result.canceled else ""))
        self.output.setPlainText("\n\n".join(self._lines()))
        self.output.show()

    def _lines(self) -> list[str]:
        worker = self.operation
        if worker is None:
            return []
        lines = [f"{row.pair.copy_path}\n→ {row.pair.keeper_path}\n"
                 + (tr("journal_status_linked") if row.linked else tr("link_not_linked"))
                 + ("\n" + link_reason(row.error) if row.error else "")
                 + ("\n" + tr("link_retained", paths="\n".join(row.retained)) if row.retained else "")
                 for row in worker.result.outcomes]
        lines += [tr("journal_write_failed", reason=reason) for reason in worker.journal_errors]
        if worker.error:
            lines.append(worker.error)
        return lines

    def _failed(self, reason: str) -> None:
        if not self._closed and not self.worker.cancel.is_set():
            self.status.setText(tr("namespace_failed", reason=reason))

    def stop(self) -> None:
        """Cancel hashing/unstarted rows; an active native call remains owned and joined."""
        if self.operation is not None:
            self.operation.cancel.set()
        else:
            self.worker.cancel.set()
            self.plan = None
            self.apply_button.setEnabled(False)
            self.status.setText(tr("scan_cancelled"))
        self.stop_button.setEnabled(False)

    def shutdown(self, *, wait: bool = True) -> None:
        """Join preview and execution before a result tree may be replaced or destroyed."""
        self._closed = True
        for worker in (self.worker, self.operation):
            if worker is not None:
                worker.cancel.set()
                if wait:
                    wait_for(worker)

    def done(self, result: int) -> None:
        """Qt: stop, join and report unobserved retained/partial outcomes before dismissal."""
        if self.defer_done(result):
            return
        self.shutdown()
        if self.operation is not None and not self._reported:
            lines = self._lines()
            if lines:
                report = QMessageBox(QMessageBox.Icon.Warning, self.windowTitle(), "",
                                     QMessageBox.StandardButton.Ok, self.parentWidget())
                report.setTextFormat(Qt.TextFormat.PlainText)
                report.setText(tr("namespace_closed_errors"))
                report.setDetailedText("\n\n".join(lines))
                report.exec()
            self._reported = True
        super().done(result)
