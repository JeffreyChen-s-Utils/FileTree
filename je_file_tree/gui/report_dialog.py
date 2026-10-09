"""Owned cancellable report preparation/writing while the scanned tree stays under a modal view."""

from __future__ import annotations

from dataclasses import dataclass
import threading

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QDialogButtonBox, QLabel, QPushButton, QVBoxLayout, QWidget

from je_file_tree.core.analysis import AGES, CATEGORIES, Summary
from je_file_tree.core.report import ReportCancelledError, prepare_report, write_html
from je_file_tree.gui.charts import ChartStack
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.report_export import capture_report_charts, encode_charts, write_xlsx
from je_file_tree.gui.scan_worker import ScanOutcome, wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog


def _labels() -> dict[str, str]:
    names = {"title": "report_title", "note": "report_note", "path": "column_path", "bytes": "report_bytes",
             "allocated": "report_allocated", "files": "column_files", "folders": "column_folders",
             "modified": "column_modified", "problem": "column_problem", "created": "report_created",
             "reference": "report_reference", "coverage": "project_coverage", "incomplete": "project_partial",
             "recorded": "project_recorded", "skipped": "report_skipped", "denied": "report_denied",
             "pending": "report_pending", "notes": "report_notes", "summary": "report_summary", "field": "report_field",
             "value": "report_value", "top_folders": "report_top_folders", "largest": "tab_largest",
             "types": "tab_types", "categories": "report_categories", "type": "column_type",
             "age": "column_age", "ages": "tab_age", "no_extension": "no_extension"}
    names.update({"category_" + key: "category_" + key for key in CATEGORIES})
    names.update({"age_" + key: "age_" + key for key in AGES})
    names.update({"accounted_bytes": "column_accounted_size", "accounted_allocated": "column_accounted_allocated"})
    return {key: tr(value) for key, value in names.items()}


@dataclass(frozen=True, slots=True)
class ReportJob:
    """GUI-captured labels/images plus a stable modal scan scope for the worker."""

    outcome: ScanOutcome
    kind: str
    target: str
    labels: dict[str, str]
    charts: list[tuple[str, QImage]]


class ReportWorker(QThread):
    """Prepare immutable scalar tables, then encode/write without GUI/model calls."""

    saved = Signal(int)
    failed = Signal(str)
    canceled = Signal()

    def __init__(self, job: ReportJob, parent: QWidget) -> None:
        super().__init__(parent)
        self.job, self.cancel = job, threading.Event()

    def run(self) -> None:
        """Report success only after atomic replacement; cancellation preserves previous targets."""
        job, outcome = self.job, self.job.outcome
        summary = Summary(outcome.largest, outcome.extensions, outcome.ages, outcome.now)
        try:
            report = prepare_report(outcome.result.root, summary, job.labels, partial=outcome.partial,
                                    cancel=self.cancel)
            if job.kind == "html":
                count = write_html(report, encode_charts(job.charts, self.cancel), job.target, cancel=self.cancel)
            else:
                count = write_xlsx(report, job.target, cancel=self.cancel)
        except ReportCancelledError:
            self.canceled.emit()
            return
        except (OSError, ValueError) as error:
            self.failed.emit(str(error))
            return
        self.saved.emit(count)


class ReportDialog(WorkerDialog):
    """Own the worker and keep scan mutations unavailable until preparation/export completes."""

    def __init__(self, outcome: ScanOutcome, kind: str, target: str, unit: str, charts: ChartStack,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if kind not in ("html", "xlsx"):
            raise ValueError("Unsupported report kind")
        self.setWindowTitle(tr("report_title"))
        self.resize(600, 200)
        self._closed = False
        self.saved = False
        self.status = QLabel(tr("export_running", path=target))
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (self.status, self.stop_button, close):
            layout.addWidget(widget)
        images = capture_report_charts(outcome.result.root, charts, unit, outcome.now) if kind == "html" else []
        self.worker = ReportWorker(ReportJob(outcome, kind, target, _labels(), images), self)
        self.worker.saved.connect(lambda count: self._finished(tr("export_done", count=count, path=target), True))
        self.worker.failed.connect(lambda reason: self._finished(tr("export_failed", reason=reason)))
        self.worker.canceled.connect(lambda: self._finished(tr("scan_cancelled")))
        self.worker.start()

    def _finished(self, message: str, saved: bool = False) -> None:
        if not self._closed:
            self.saved = saved
            self.status.setText(message)
            self.stop_button.setEnabled(False)

    def stop(self) -> None:
        """Ask the owned writer to stop before replacing the destination."""
        self.worker.cancel.set()
        self.stop_button.setEnabled(False)

    def shutdown(self, *, wait: bool = True) -> None:
        """Cancel and join before destroying the modal view, rejecting late replies."""
        self._closed = True
        self.worker.cancel.set()
        if wait:
            wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: finish after preparation/writing has stopped."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
