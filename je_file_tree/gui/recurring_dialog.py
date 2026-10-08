"""Bounded dated observations; stored paths are displayed as text and never opened as sources."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QLabel, QTabWidget, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.core.formatting import format_change, format_count, format_size
from je_file_tree.core.recurring import Candidate, Growth, RecurringProposal
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.tables import Column, _TableModel


class CandidatesModel(_TableModel[Candidate]):
    """Scalar candidate paths, rule names and logical bytes; no Node or action role."""

    def build_columns(self) -> Sequence[Column[Candidate]]:
        """Translate built-in reasons while preserving literal paths."""
        return (Column("column_path", lambda row: row.path, lambda row: row.path),
                Column("recurring_rule", lambda row: tr(f"cleanup_{row.rule}"), lambda row: row.rule),
                Column("column_size", lambda row: format_size(row.size, self.unit), lambda row: row.size, True))

    def extra_data(self, row: Candidate, role: int) -> Any:
        """Expose a full literal path tooltip without an actionable source-node role."""
        return row.path if role == Qt.ItemDataRole.ToolTipRole else None


class GrowthModel(_TableModel[Growth]):
    """Observed logical folder growth, which is not a reclaimable-space estimate."""

    def build_columns(self) -> Sequence[Column[Growth]]:
        """Keep missing historical totals explicitly unknown."""
        return (Column("column_path", lambda row: row.path, lambda row: row.path),
                Column("column_before", lambda row: tr("recurring_unknown") if row.before is None else
                       format_size(row.before, self.unit), lambda row: -1 if row.before is None else row.before, True),
                Column("column_now", lambda row: format_size(row.after, self.unit), lambda row: row.after, True),
                Column("column_change", lambda row: format_change(row.change, self.unit),
                       lambda row: row.change, True))

    def extra_data(self, row: Growth, role: int) -> Any:
        """Keep full folder paths available when the visible column is elided."""
        return row.path if role == Qt.ItemDataRole.ToolTipRole else None


def _date(timestamp: float) -> str:
    return _display_date(datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=timestamp))


def _display_date(value: datetime) -> str:
    try:
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except (OSError, OverflowError, ValueError):
        return value.isoformat()


class RecurringDialog(QDialog):
    """Current-session reports for at most the configured roots; source operations are absent."""

    def __init__(self, reports: Sequence[RecurringProposal], status: Callable[[RecurringProposal], str | None],
                 parent: QWidget) -> None:
        super().__init__(parent)
        self.reports, self.status = tuple(reports), status
        self.requested: RecurringProposal | None = None
        self.setWindowTitle(tr("action_recurring"))
        self.resize(980, 620)
        self.roots = QComboBox()
        self.roots.addItems([report.baseline.root for report in self.reports])
        self.roots.setAccessibleName(tr("background_roots"))
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.tabs = QTabWidget()
        self.new_junk, self.current, self.growth = CandidatesModel(self), CandidatesModel(self), GrowthModel(self)
        for key, model in (("recurring_new", self.new_junk), ("recurring_current", self.current),
                           ("recurring_growth", self.growth)):
            self._add_table(key, model)
        hint = QLabel(tr("recurring_hint"))
        hint.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.review = buttons.addButton(tr("recurring_review"), QDialogButtonBox.ButtonRole.ActionRole)
        self.review.clicked.connect(self._request_review)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (self.roots, self.summary, self.tabs, hint, buttons):
            layout.addWidget(widget)
        self.roots.currentIndexChanged.connect(self._select)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._summary)
        self.timer.start()
        self._select()

    def _add_table(self, key: str, model: _TableModel) -> None:
        view = QTableView(self)
        view.setModel(model)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setWordWrap(False)
        view.horizontalHeader().setStretchLastSection(True)
        view.setColumnWidth(0, 470)
        install_copy(view)
        self.tabs.addTab(view, tr(key))

    def _select(self) -> None:
        index = self.roots.currentIndex()
        report = self.reports[index] if 0 <= index < len(self.reports) else None
        self.new_junk.set_rows(report.new_junk if report is not None else ())
        self.current.set_rows(report.baseline.candidates if report is not None else ())
        self.growth.set_rows(report.growth if report is not None else ())
        self._summary()

    def _summary(self) -> None:
        index = self.roots.currentIndex()
        if not 0 <= index < len(self.reports):
            self.review.setEnabled(False)
            self.summary.setText(tr("recurring_empty"))
            return
        report = self.reports[index]
        status = self.status(report)
        self.review.setEnabled(status is None and bool(report.baseline.candidates))
        baseline, context = report.baseline, report.context
        previous = (_display_date(datetime.fromisoformat(report.previous_saved))
                    if report.previous_saved else tr("recurring_unknown"))
        self.summary.setText(tr("recurring_summary", prepared=_date(context.prepared_at), previous=previous,
                                expires=_date(context.expires_at), retained=format_count(len(baseline.candidates)),
                                total=format_count(baseline.candidate_count),
                                coverage=tr("history_complete" if baseline.complete else "history_incomplete"),
                                comparison=tr("history_complete" if report.comparison_complete
                                              else "recurring_unknown"),
                                status=tr("recurring_status_" + (status or "current"))))

    def _request_review(self) -> None:
        index = self.roots.currentIndex()
        if 0 <= index < len(self.reports):
            report = self.reports[index]
            if self.status(report) is None and report.baseline.candidates:
                self.requested = report
                self.accept()

    def shutdown(self) -> None:
        """Stop metadata refresh when the owning workspace closes its modal view."""
        self.timer.stop()
