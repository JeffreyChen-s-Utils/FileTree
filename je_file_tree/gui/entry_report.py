"""Read-only modal entry reports with lazy rows and cancelable clipboard capture."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel,
    QPlainTextEdit, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import ListCapture, install_copy


def literal_tooltip(text: str) -> str:
    """Render literal paths/reasons in Qt's rich-text tooltip engine."""
    return f"<pre>{escape(text)}</pre>"


class EntryReportDialog(QDialog):
    """Shared complete read-only model view; closing a report grants no source approval."""

    def __init__(self, model: QAbstractItemModel, title: str, summary: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(960, 540)
        self.model = model
        self.model.setParent(self)
        self.summary = QLabel(summary)
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
        self.view.setAccessibleName(title)
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
        row = self.view.currentIndex().row()
        if row < 0:
            self.details.clear()
            return
        values = [self.model.index(row, column).data() for column in range(self.model.columnCount())]
        self.details.setPlainText("\n".join("" if value is None else str(value) for value in values))
