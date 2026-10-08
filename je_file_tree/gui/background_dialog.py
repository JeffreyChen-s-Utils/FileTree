"""Explicit default-off monitor preferences and bounded chosen-folder schedules."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QMessageBox, QPushButton, QSpinBox, QWidget,
)

from je_file_tree.core.background import MAX_ROOTS, MonitorConfig
from je_file_tree.gui.i18n import tr


class BackgroundDialog(QDialog):
    """Changing a schedule never approves clean-up or registers automatic startup."""

    def __init__(self, config: MonitorConfig, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_background_monitor"))
        self.enabled = QCheckBox(tr("background_enable"))
        self.enabled.setChecked(config.enabled)
        self.threshold = QSpinBox()
        self.threshold.setRange(1, 50)
        self.threshold.setSuffix(" %")
        self.threshold.setValue(config.threshold)
        self.interval = QSpinBox()
        self.interval.setRange(1, 720)
        self.interval.setValue(config.interval_hours)
        self.roots = QListWidget()
        self.roots.addItems(config.roots)
        add = QPushButton(tr("background_add"))
        remove = QPushButton(tr("background_remove"))
        add.clicked.connect(self._add)
        remove.clicked.connect(self._remove)
        controls = QHBoxLayout()
        controls.addWidget(add)
        controls.addWidget(remove)
        hint = QLabel(tr("background_hint"))
        hint.setWordWrap(True)
        layout = QFormLayout(self)
        layout.addRow(hint)
        layout.addRow(self.enabled)
        layout.addRow(tr("background_threshold"), self.threshold)
        layout.addRow(tr("background_interval"), self.interval)
        layout.addRow(tr("background_roots"), self.roots)
        layout.addRow(controls)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.resize(600, 450)

    def configuration(self) -> MonitorConfig:
        """Freeze the explicit choices; no filesystem traversal or command execution is performed."""
        return MonitorConfig(self.enabled.isChecked(), self.threshold.value(), self.interval.value(),
                             tuple(self.roots.item(index).text() for index in range(self.roots.count())))

    def _add(self) -> None:
        if self.roots.count() >= MAX_ROOTS:
            QMessageBox.warning(self, tr("action_background_monitor"), tr("background_limit"))
            return
        path = QFileDialog.getExistingDirectory(self, tr("background_add"))
        if path:
            self.roots.addItem(os.path.abspath(path))

    def _remove(self) -> None:
        for item in self.roots.selectedItems():
            self.roots.takeItem(self.roots.row(item))

    def _accept(self) -> None:
        try:
            self.configuration()
        except ValueError as error:
            QMessageBox.warning(self, tr("action_background_monitor"), tr("background_error", detail=str(error)))
            return
        self.accept()
