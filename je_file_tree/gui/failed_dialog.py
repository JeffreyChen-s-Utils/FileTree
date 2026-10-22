"""Complete lazy Trash failures and observed open-file diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QWidget

from je_file_tree.core.formatting import format_count
from je_file_tree.core.lock_holders import LockReport
from je_file_tree.core.node import Node
from je_file_tree.gui.entry_report import EntryReportDialog, literal_tooltip
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.tables import Column, _TableModel


class FailedModel(_TableModel[Node]):
    """Every failed Node in result order, with captured diagnostics formatted on demand."""

    def __init__(self, failed: Sequence[Node], holders: Mapping[Node, LockReport],
                 parent: QObject | None = None) -> None:
        self._reports = {node: holders[node] for node in failed if node in holders}
        super().__init__(parent)
        self.set_rows(failed)

    def build_columns(self) -> Sequence[Column[Node]]:
        """Full path and diagnostic text, with no file-operation Node roles."""
        return (
            Column("column_path", lambda node: node.path, lambda node: node.path),
            Column("column_problem", self._reason, self._reason),
        )

    def extra_data(self, row: Node, role: int) -> str | None:
        """Render filename/process markup and whitespace literally in tooltips."""
        return literal_tooltip(f"{row.path}\n{self._reason(row)}") if role == Qt.ItemDataRole.ToolTipRole else None

    def _reason(self, node: Node) -> str:
        report = self._reports.get(node)
        parts = [tr("trash_failed", name=node.name)]
        if report is not None and report.holders:
            programs = ", ".join(tr("trash_holder", name=holder.name, pid=str(holder.pid))
                                 for holder in report.holders)
            parts.append(tr("trash_holders", path=node.path, programs=programs))
        if report is None or report.incomplete or report.error:
            parts.append(tr("trash_holders_limited", path=node.path))
        if report is not None and report.error:
            parts.append(tr("trash_holders_error", reason=report.error))
        return "\n".join(parts)


class FailedEntriesDialog(EntryReportDialog):
    """Read-only failure results; observed processes do not establish the failure's cause."""

    def __init__(self, failed: Sequence[Node], holders: Mapping[Node, LockReport],
                 parent: QWidget | None = None) -> None:
        super().__init__(FailedModel(failed, holders), tr("trash_failed_title"),
                         tr("trash_failed_summary", count=format_count(len(failed))), parent)
