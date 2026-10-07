"""Read-only operation history, with unknown crash outcomes and redacted metadata exports."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, QThread, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableView,
    QVBoxLayout, QWidget,
)

from je_file_tree.core.operation_journal import JournalRead, OperationJournal, OperationRecord, export_journal
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import ExportWorker, wait_for

_HEADERS = ("journal_time", "journal_source", "journal_identity", "review_reason", "journal_result",
            "journal_detail", "journal_destination")


def journal_folder() -> Path:
    """Only this application's data directory owns journal retention files."""
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "journal"


class JournalWorker(QThread):
    """Read bounded retained audit segments away from the event loop."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, journal: OperationJournal, parent: QWidget) -> None:
        super().__init__(parent)
        self._journal = journal

    def run(self) -> None:
        """Read latest events, preserving incomplete/corrupt visibility."""
        try:
            self.ready.emit(self._journal.recent())
        except OSError as error:
            self.failed.emit(str(error))


class RecentActions(QDialog):
    """Show the latest 500 actions; exports contain metadata with redacted home prefixes."""

    def __init__(self, journal: OperationJournal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_recent_actions"))
        self.resize(1100, 600)
        self._journal = journal
        self._records: list[OperationRecord] = []
        self._exports: set[ExportWorker] = set()
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels([tr(key) for key in _HEADERS])
        self.view = QTableView()
        self.view.setModel(self.model)
        self.status = QLabel(tr("journal_reading"))
        self.status.setWordWrap(True)
        hint = QLabel(tr("journal_hint"))
        hint.setWordWrap(True)
        self.export_button = QPushButton(tr("journal_export"))
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        bar = QHBoxLayout()
        bar.addWidget(self.export_button)
        bar.addStretch(1)
        bar.addWidget(buttons)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.status)
        layout.addLayout(bar)
        self._worker = JournalWorker(journal, self)
        self._worker.ready.connect(self._show)
        self._worker.failed.connect(lambda reason: self.status.setText(tr("journal_read_failed", reason=reason)))
        self._worker.start()

    def _show(self, result: JournalRead) -> None:
        self._records = result.records
        for record in result.records:
            outcome = record.outcome
            reason = (_record_text(f"cleanup_{record.reason[8:]}", record.reason)
                      if record.reason.startswith("cleanup:") else
                      tr("journal_reason_undo" if record.reason == "undo" else
                         "journal_reason_duplicates" if record.reason == "duplicates" else "review_manual"))
            values = (record.timestamp, record.source, str(record.identity), reason,
                      tr(f"journal_status_{outcome.status}"),
                      _record_text(f"trash_skip_{outcome.detail}", outcome.detail) if outcome.detail else "",
                      outcome.destination or tr("size_unknown"))
            items = []
            for value in values:
                item = QStandardItem(value)
                item.setEditable(False)
                item.setToolTip(value)
                items.append(item)
            self.model.appendRow(items)
        self.view.setColumnWidth(0, 210)
        self.view.setColumnWidth(1, 270)
        self.view.setColumnWidth(4, 180)
        self.export_button.setEnabled(bool(result.records))
        self.status.setText(tr("journal_summary", count=str(len(result.records)), invalid=str(result.invalid),
                               unavailable=str(result.unavailable)))

    def export(self) -> None:
        """Export only the currently shown records, on an atomic-writing worker."""
        file, _ = QFileDialog.getSaveFileName(self, tr("journal_export"), "actions.csv", tr("csv_filter"))
        if not file:
            return
        records = self._records.copy()
        worker = ExportWorker(lambda: export_journal(records, file), self)
        self._exports.add(worker)
        worker.done.connect(lambda _count: self.status.setText(tr("journal_exported")))
        worker.failed.connect(lambda reason: QMessageBox.warning(self, tr("journal_export"),
                                                               tr("export_failed", reason=reason)))
        worker.finished.connect(lambda: self._exports.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def done(self, result: int) -> None:
        """Wait for reads and atomic exports before destroying their dialog."""
        self.shutdown()
        super().done(result)

    def shutdown(self) -> None:
        """Join all current workers, including an export finishing after its dialog closes."""
        wait_for(self._worker)
        for worker in self._exports.copy():
            wait_for(worker)


def _record_text(key: str, original: str) -> str:
    try:
        return tr(key)
    except KeyError:
        return original  # Retained records can describe rules/reasons from a newer release.
