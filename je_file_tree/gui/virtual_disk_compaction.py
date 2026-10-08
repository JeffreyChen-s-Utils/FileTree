"""Explicit detached-disk review with durable approval, retained native outcomes and joined workers."""

import threading
import uuid

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (QDialogButtonBox, QLabel, QMessageBox, QPlainTextEdit,
                              QPushButton, QVBoxLayout, QWidget)

from je_file_tree.core.formatting import format_size
from je_file_tree.core.node import Node
from je_file_tree.core.operation_journal import OperationJournal, OperationOutcome, OperationRecord
from je_file_tree.core.virtual_disk_compaction import (
    CompactionOutcome, CompactionPlan, execute_compaction, prepare_compaction,
)
from je_file_tree.core.virtual_disks import VirtualDisk
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog, queue_worker


class CompactionPreviewWorker(QThread):
    """Prepare frozen read-only source/header/runtime authority; canceled replies grant no approval."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, disk: VirtualDisk, parent: QWidget) -> None:
        super().__init__(parent)
        self.disk, self.cancel = disk, threading.Event()

    def run(self) -> None:
        """No writable disk open occurs before explicit review and durable approval."""
        try:
            plan = prepare_compaction(self.disk, cancel=self.cancel)
            if not self.cancel.is_set():
                self.ready.emit(plan)
        except (OSError, ValueError) as exc:
            if not self.cancel.is_set():
                self.failed.emit(str(exc))


class DiskCompactionWorker(QThread):
    """Durable approval precedes execution; actual results persist before queued GUI delivery."""

    ready = Signal(object)

    def __init__(self, plan: CompactionPlan, journal: OperationJournal, parent: QWidget) -> None:
        super().__init__(parent)
        self.plan, self.journal, self.cancel = plan, journal, threading.Event()
        self.result = CompactionOutcome()
        self.journal_errors: list[str] = []
        disk = plan.info.disk
        recorded = Node(disk.path, False, snapshot=disk.snapshot)
        self.record = OperationRecord.approved(uuid.uuid4().hex, recorded, "virtual_disk_compaction")

    def run(self) -> None:
        """Approval failure blocks the native operation; later audit errors retain actual completion."""
        if not self._append(self.record):
            self.result = CompactionOutcome(error=tr("vc_audit_refused"))
        else:
            self.result = execute_compaction(self.plan, machine_stopped=True, cancel=self.cancel)
            status = "compacted" if self.result.compacted else "failed" if self.result.attempted else "skipped"
            detail = tr("vc_audit_detail", before=self.result.before, after=self.result.after,
                        error=self.result.error)
            self._append(self.record.finished(OperationOutcome(status, detail)))
        self.ready.emit(self.result)

    def _append(self, record: OperationRecord) -> bool:
        try:
            self.journal.append([record])
        except (OSError, ValueError) as exc:
            self.journal_errors.append(str(exc))
            return False
        return True


class VirtualDiskCompactionDialog(WorkerDialog):
    """One exact disk, default-No stopped-machine review, retained outcomes and owned native lifetime."""

    execution_requested = Signal()

    def __init__(self, disk: VirtualDisk, journal: OperationJournal, unit: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.journal, self.unit = journal, unit
        self.plan: CompactionPlan | None = None
        self.operation: DiskCompactionWorker | None = None
        self._closed = self._reported = False
        self.setWindowTitle(tr("vc_title"))
        self.resize(820, 590)
        self._build(disk)
        self.worker = CompactionPreviewWorker(disk, self)
        self.worker.ready.connect(self._show)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(lambda: not self._closed and self.operation is None
                                     and self.stop_button.setEnabled(False))
        self.worker.start()

    @property
    def changed(self) -> bool:
        """Whether a writable operation was attempted, including failed/partial native outcomes."""
        return self.operation is not None and self.operation.result.attempted

    def _build(self, disk: VirtualDisk) -> None:
        hint = QLabel(tr("vc_hint"))
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)
        self.details = QPlainTextEdit(disk.path)
        self.details.setReadOnly(True)
        self.status = QLabel(tr("vc_preparing"))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.apply_button = QPushButton(tr("vc_apply"))
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (hint, self.details, self.status, self.apply_button, self.stop_button, close):
            layout.addWidget(widget, 1 if widget is self.details else 0)

    def _show(self, plan: CompactionPlan) -> None:
        if self._closed or self.worker.cancel.is_set() or plan.info.disk is not self.worker.disk:
            return
        self.plan = plan
        info = plan.info
        self.details.setPlainText(tr("vc_details", path=info.disk.path,
                                     identifier=str(uuid.UUID(bytes_le=info.identifier)),
                                     capacity=format_size(info.virtual_size, self.unit),
                                     physical=format_size(info.physical_size, self.unit),
                                     source=info.disk.name))
        self.status.setText(tr("vc_ready"))
        self.apply_button.setEnabled(True)

    def apply(self) -> None:
        """Review the exact frozen path and stopped-machine requirement with default-No approval."""
        plan = self.plan
        if self._closed or plan is None or self.worker.cancel.is_set() or self.operation is not None:
            return
        question = QMessageBox(QMessageBox.Icon.Warning, self.windowTitle(), "",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        question.setTextFormat(Qt.TextFormat.PlainText)
        question.setText(tr("vc_confirm", path=plan.info.disk.path))
        question.setDetailedText(self.details.toPlainText())
        question.setDefaultButton(QMessageBox.StandardButton.No)
        if (question.exec() != QMessageBox.StandardButton.Yes or self._closed or self.plan is not plan
                or self.worker.cancel.is_set()):
            return
        self.execution_requested.emit()
        self.apply_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status.setText(tr("vc_running"))
        self.operation = DiskCompactionWorker(plan, self.journal, self)
        self.operation.ready.connect(self._completed)
        self.operation.finished.connect(lambda: not self._closed and self.stop_button.setEnabled(False))
        worker = self.operation
        queue_worker(worker, lambda: not self._closed and self.operation is worker
                     and self.plan is plan and not worker.cancel.is_set(), self)

    def _lines(self) -> str:
        worker = self.operation
        if worker is None:
            return ""
        result = worker.result
        before = tr("size_unknown") if result.before is None else format_size(result.before, self.unit)
        after = tr("size_unknown") if result.after is None else format_size(result.after, self.unit)
        status = tr("journal_status_compacted" if result.compacted else "vc_not_compacted")
        detail = tr("vc_done", status=status, before=before, after=after)
        if result.error:
            detail += "\n" + tr("vc_failed", reason=result.error)
        for reason in worker.journal_errors:
            detail += "\n" + tr("journal_write_failed", reason=reason)
        return detail

    def _completed(self, _result: CompactionOutcome) -> None:
        if not self._closed:
            self._reported = True
            self.status.setText(self._lines())

    def _failed(self, reason: str) -> None:
        if not self._closed and not self.worker.cancel.is_set():
            self.status.setText(tr("vc_failed", reason=reason))

    def stop(self) -> None:
        """Cancel preparation/unstarted execution; an active native call remains joined and reported."""
        if self.operation is not None:
            self.operation.cancel.set()
            self.status.setText(tr("vc_waiting"))
        else:
            self.worker.cancel.set()
            self.plan = None
            self.apply_button.setEnabled(False)
            self.status.setText(tr("scan_cancelled"))
        self.stop_button.setEnabled(False)

    def shutdown(self, *, wait: bool = True) -> None:
        """Join all work and retain actual results before any source tree can be replaced."""
        self._closed = True
        for worker in (self.worker, self.operation):
            if worker is not None:
                worker.cancel.set()
                if wait:
                    wait_for(worker)

    def done(self, result: int) -> None:
        """Qt: join and show unobserved actual completion/partial errors before dismissal."""
        if self.defer_done(result):
            return
        self.shutdown()
        if self.operation is not None and not self._reported:
            report = QMessageBox(QMessageBox.Icon.Information, self.windowTitle(), "",
                                 QMessageBox.StandardButton.Ok, self.parentWidget())
            report.setTextFormat(Qt.TextFormat.PlainText)
            report.setText(self._lines())
            report.setDetailedText(self.details.toPlainText())
            report.exec()
            self._reported = True
        super().done(result)
