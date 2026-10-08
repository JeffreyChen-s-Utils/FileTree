"""Review an explicit bounded folder list before starting a combined scan."""

import os

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from je_file_tree.core.multi_scan import MAX_ROOTS
from je_file_tree.gui.i18n import tr


class MultiScanDialog(QDialog):
    """Own a literal list of actual folders; accepting freezes those roots for the worker."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.roots: tuple[str, ...] = ()
        self.setWindowTitle(tr("multi_choose"))
        self.resize(700, 420)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("multi_hint"))
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(hint)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list)
        row = QHBoxLayout()
        self.add = QPushButton(tr("multi_add"))
        self.remove = QPushButton(tr("multi_remove"))
        row.addWidget(self.add)
        row.addWidget(self.remove)
        layout.addLayout(row)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.add.clicked.connect(self._add)
        self.remove.clicked.connect(self._remove)
        layout.addWidget(self.buttons)

    def add_root(self, path: str) -> None:
        """Add an explicitly selected existing folder once; bound the inventory before creating rows."""
        normalized = os.path.abspath(path)
        existing = {os.path.normcase(self.list.item(index).text()) for index in range(self.list.count())}
        if os.path.isdir(normalized) and os.path.normcase(normalized) not in existing and self.list.count() < MAX_ROOTS:
            self.list.addItem(normalized)
        self._buttons()

    def _add(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("multi_add"))
        if path:
            self.add_root(path)

    def _remove(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self._buttons()

    def _buttons(self) -> None:
        self.add.setEnabled(self.list.count() < MAX_ROOTS)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.list.count() > 0)

    def accept(self) -> None:
        """Freeze actual source names; no scan starts from an empty list."""
        if self.list.count():
            self.roots = tuple(self.list.item(index).text() for index in range(self.list.count()))
            super().accept()
