"""Two-question, single-drive Windows Recycle Bin emptying through the native OS API."""

from __future__ import annotations

import re
import sys

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.trash_size import TrashUsage, empty_windows_bin
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.volumes import Volume, VolumesDialog


class EmptyBinWorker(QThread):
    """Call only the native, approved single-drive API; do not terminate permanent operations midway."""

    completed = Signal(str)

    def __init__(self, root: str, approved: TrashUsage, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.approved = root, approved

    def run(self) -> None:
        """Recheck approved totals and report native errors, including partial emptying."""
        try:
            empty_windows_bin(self.root, self.approved)
        except (OSError, ValueError) as error:
            self.completed.emit(str(error))
            return
        self.completed.emit("")


class BinDialog(VolumesDialog):
    """Current bin metadata and explicit Windows emptying; other platforms remain read-only."""

    def __init__(self, unit: str, parent: QWidget | None = None) -> None:
        super().__init__(unit, parent)
        self._empty_worker: EmptyBinWorker | None = None
        self.last_error = ""
        self.setWindowTitle(tr("action_bins"))
        self.hint.setText(tr("bin_hint"))
        self.empty_button = QPushButton(tr("bin_empty"))
        self.empty_button.setEnabled(False)
        self.empty_button.setVisible(sys.platform == "win32")
        self.empty_button.clicked.connect(self.empty_selected)
        self.layout().insertWidget(self.layout().count() - 1, self.empty_button)
        self.view.selectionModel().currentChanged.connect(self._buttons)

    def _show(self, rows: list[Volume], count: int) -> None:
        super()._show(rows, count)
        if not self._closed and not self.worker.cancel.is_set():
            self._buttons()
            if self.last_error:
                self.status.setText(tr("bin_failed", reason=self.last_error))
                self.status.setTextFormat(Qt.TextFormat.PlainText)

    def _selected(self) -> Volume | None:
        row = self.view.currentIndex().data(Qt.ItemDataRole.UserRole)
        return row if isinstance(row, Volume) else None

    def _buttons(self) -> None:
        row = self._selected()
        enabled = (sys.platform == "win32" and self._empty_worker is None and not self.worker.cancel.is_set()
                   and row is not None and row.trash.complete and row.trash.count > 0
                   and re.fullmatch(r"[A-Za-z]:[/\\]", row.root) is not None)
        self.empty_button.setEnabled(enabled)

    def empty_selected(self) -> None:
        """Ask twice with the current drive/size/count and irreversibility before starting deletion."""
        self._buttons()
        row = self._selected()
        if not self.empty_button.isEnabled() or row is None:
            return
        fields = dict(root=row.root, size=format_size(row.trash.size, self.model.unit),
                      count=format_count(row.trash.count))
        for key in ("bin_first", "bin_irreversible"):
            answer = QMessageBox.question(self, tr("bin_empty"), tr(key, **fields),
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.empty_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.close_box.setEnabled(False)
        self.view.setEnabled(False)
        self.status.setText(tr("bin_running", root=row.root))
        worker = EmptyBinWorker(row.root, row.trash, self)
        worker.completed.connect(self._empty_finished)
        self._empty_worker = worker
        worker.start()

    def _empty_finished(self, reason: str) -> None:
        worker = self._empty_worker
        if worker is not None:
            wait_for(worker)
            worker.deleteLater()
        self._empty_worker = None
        if self._closed:
            return
        self.last_error = reason
        self.close_box.setEnabled(True)
        self.view.setEnabled(True)
        self.refresh()

    def _scan(self, index) -> None:
        if self._empty_worker is None:
            super()._scan(index)

    def stop(self) -> None:
        """Stop surveys only; an active OS emptying call cannot be canceled."""
        if self._empty_worker is None:
            super().stop()
            self.empty_button.setEnabled(False)

    def done(self, result: int) -> None:
        """Wait for an active native emptying operation before permitting close."""
        if self._empty_worker is None:
            super().done(result)

    def shutdown(self) -> None:
        """Join any native operation and the current metadata survey before destruction."""
        if self._empty_worker is not None:
            wait_for(self._empty_worker)
        super().shutdown()
