"""A complete lazy list of refused entries, without a screen-sized warning label."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from je_file_tree.core.formatting import format_count
from je_file_tree.core.node import Node
from je_file_tree.gui.entry_report import EntryReportDialog, literal_tooltip
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.tables import Column, _TableModel


class SkippedModel(_TableModel[tuple[Node, str]]):
    """Original refused-entry order; derive paths and translated reasons on request."""

    def build_columns(self) -> Sequence[Column[tuple[Node, str]]]:
        """Path and refusal reason, with no file-operation Node roles."""
        return (
            Column("column_path", lambda row: row[0].path, lambda row: row[0].path),
            Column("column_problem", _reason, _reason),
        )

    def extra_data(self, row: tuple[Node, str], role: int) -> str | None:
        """Full plain-text path/reason in tooltips."""
        if role == Qt.ItemDataRole.ToolTipRole:
            return literal_tooltip(f"{row[0].path}\n{_reason(row)}")
        return None


def _reason(row: tuple[Node, str]) -> str:
    return tr(f"trash_skip_{row[1]}")


class SkippedEntriesDialog(EntryReportDialog):
    """Complete refused rows in the shared read-only entry report."""

    def __init__(self, skipped: Sequence[tuple[Node, str]], parent: QWidget | None = None) -> None:
        model = SkippedModel()
        model.set_rows(skipped)
        super().__init__(model, tr("trash_skipped_title"),
                         tr("trash_skipped_summary", count=format_count(len(skipped))), parent)
