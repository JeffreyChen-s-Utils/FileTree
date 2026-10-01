"""The *Skip while scanning* dialog: folder name patterns and folder paths that scans leave out."""

from __future__ import annotations

import os
from collections.abc import Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from je_file_tree.gui.i18n import tr


class ExclusionsDialog(QDialog):
    """Edits the exclusions: add a name pattern, add a folder, remove the selected lines."""

    def __init__(self, patterns: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("exclusions_title"))
        self.resize(520, 380)
        hint = QLabel(tr("exclusions_hint"))
        hint.setWordWrap(True)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for pattern in patterns:
            self.add(pattern)
        add_name = QPushButton(tr("exclusions_add_name"))
        add_folder = QPushButton(tr("exclusions_add_folder"))
        remove = QPushButton(tr("exclusions_remove"))
        add_name.clicked.connect(self._ask_name)
        add_folder.clicked.connect(self._ask_folder)
        remove.clicked.connect(self.remove_selected)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        side = QVBoxLayout()
        for button in (add_name, add_folder, remove):
            side.addWidget(button)
        side.addStretch(1)
        middle = QHBoxLayout()
        middle.addWidget(self.list, 1)
        middle.addLayout(side)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(middle, 1)
        layout.addWidget(buttons)

    def patterns(self) -> list[str]:
        """The exclusions as listed."""
        return [self.list.item(row).text() for row in range(self.list.count())]

    def add(self, pattern: str) -> None:
        """Add ``pattern`` unless it is blank or already listed (case ignored)."""
        pattern = pattern.strip()
        if pattern and pattern.casefold() not in {existing.casefold() for existing in self.patterns()}:
            self.list.addItem(pattern)

    def remove_selected(self) -> None:
        """Remove the selected lines."""
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def _ask_name(self) -> None:
        text, accepted = QInputDialog.getText(self, tr("exclusions_add_name"), tr("exclusions_name_prompt"))
        if accepted:
            self.add(text)

    def _ask_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("exclusions_add_folder"))
        if folder:
            self.add(os.path.normpath(folder))
