"""A complete lazy list of refused entries, without a screen-sized warning label."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel,
    QPlainTextEdit, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.core.formatting import format_count
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import ListCapture, install_copy
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
            return f"<pre>{escape(row[0].path)}\n{escape(_reason(row))}</pre>"
        return None


def _reason(row: tuple[Node, str]) -> str:
    return tr(f"trash_skip_{row[1]}")


class SkippedEntriesDialog(QDialog):
    """Read-only complete refusals, fixed-size viewport, selectable details and Ctrl+C."""

    def __init__(self, skipped: Sequence[tuple[Node, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("trash_skipped_title"))
        self.resize(960, 540)
        self.model = SkippedModel(self)
        self.model.set_rows(skipped)
        self.summary = QLabel(tr("trash_skipped_summary", count=format_count(len(skipped))))
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.view.setWordWrap(False)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.view.setAccessibleName(tr("trash_skipped_title"))
        install_copy(self.view)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(110)
        self.details.setAccessibleName(tr("details_title"))
        self.view.selectionModel().currentChanged.connect(lambda *_: self._show_details())
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.details)
        shortcut = QKeySequence(QKeySequence.StandardKey.Copy).toString(QKeySequence.SequenceFormat.NativeText)
        hint = QLabel(tr("trash_skipped_hint", shortcut=shortcut))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(close)
        if self.model.rowCount():
            self.view.setCurrentIndex(self.model.index(0, 0))

    def shutdown(self, *, wait: bool = True) -> None:
        """Cancel pending clipboard capture before this notice or its owner closes."""
        for capture in self.findChildren(ListCapture):
            capture.cancel()

    def done(self, result: int) -> None:
        """Qt: a notice grants no approval; dismiss after canceling GUI capture."""
        self.shutdown()
        super().done(result)

    def _show_details(self) -> None:
        row = self.model.row_at(self.view.currentIndex().row())
        self.details.setPlainText("" if row is None else f"{row[0].path}\n{_reason(row)}")
