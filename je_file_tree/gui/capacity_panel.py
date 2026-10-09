"""A compact capacity summary and an explicit ledger of known and unknown amounts."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from je_file_tree.core.capacity import CapacityLedger
from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.gui.i18n import tr


class CapacityPanel(QWidget):
    """Render a worker-computed ledger; changing the tree invalidates it immediately."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ledger: CapacityLedger | None = None
        self.unit = "auto"
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        self.details = QPushButton()
        self.details.clicked.connect(self._show_details)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.summary, 1)
        layout.addWidget(self.details)
        self.set_ledger(None)

    def set_ledger(self, ledger: CapacityLedger | None) -> None:
        """Replace a ledger, or hide stale figures while waiting for a rescan."""
        self.ledger = ledger
        self.setVisible(ledger is not None)
        self.retranslate()

    def retranslate(self) -> None:
        """Refresh the language and current size unit."""
        self.details.setText(tr("capacity_details"))
        ledger = self.ledger
        if ledger is not None:
            self.summary.setText(tr("capacity_summary", used=self._size(ledger.used), free=self._size(ledger.free),
                                    unique=self._size(ledger.unique_allocated), status=tr("capacity_" + ledger.status)))
            self.summary.setToolTip(tr("capacity_explanation"))

    def _size(self, amount: int | None) -> str:
        return tr("size_unknown") if amount is None else format_size(amount, self.unit)

    def _show_details(self) -> None:
        ledger = self.ledger
        if ledger is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("capacity_details"))
        dialog.resize(640, 600)
        layout = QVBoxLayout(dialog)
        state = QLabel(tr("capacity_" + ledger.status))
        state.setWordWrap(True)
        layout.addWidget(state)
        form = QFormLayout()
        for key in ("total", "used", "free", "unavailable_free", "named_allocated", "unique_allocated",
                    "hard_link_overcount", "recycle_bin_seen", "foreign_allocated_seen", "unaccounted",
                    "metadata_bytes", "omitted_bytes", "other_volumes_bytes"):
            value = QLabel(self._size(getattr(ledger, key)))
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(tr("capacity_row_" + key), value)
        form.addRow(tr("capacity_row_mounts"), QLabel(format_count(ledger.mounted_folders)))
        coverage = ledger.coverage
        form.addRow(tr("capacity_row_coverage"), QLabel(tr("capacity_coverage", skipped=coverage.skipped_folders,
                      inaccessible=coverage.inaccessible_folders, pending=coverage.pending_folders)))
        layout.addLayout(form)
        explanation = QLabel(tr("capacity_explanation"))
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(explanation)
        if not ledger.recycle_bin_complete:
            hint = QLabel(tr("capacity_bin_partial"))
            hint.setWordWrap(True)
            layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
