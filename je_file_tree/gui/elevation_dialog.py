"""Own one administrator relaunch without blocking Qt or abandoning a native request."""

from __future__ import annotations

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from je_file_tree.gui import elevation
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog, after_threads


class ElevationWorker(QThread):
    """Run one captured restart request without accessing widgets or translations."""

    def __init__(self, arguments: list[str], parent: QWidget) -> None:
        super().__init__(parent)
        self.arguments = list(arguments)
        self.started_copy = False
        self.error: str | None = None

    def run(self) -> None:
        """Wait for native approval/launch completion; never terminate or retry the call."""
        try:
            self.started_copy = elevation.relaunch_elevated(self.arguments)
        except OSError as error:
            self.error = str(error)


class ElevationDialog(WorkerDialog):
    """Keep the request owned through Escape, closing and either native launch outcome."""

    def __init__(self, arguments: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._closed = False
        self.setWindowTitle(tr("action_elevate"))
        self.status = QLabel(tr("elevate_waiting"))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addWidget(self.buttons)
        self.resize(560, 170)
        self.worker = ElevationWorker(arguments, self)
        self.worker.finished.connect(lambda: after_threads((self.worker,), self._completed, self))
        self.worker.start()

    def _completed(self) -> None:
        if self._closed:
            return
        if self.worker.error is not None:
            self.status.setText(tr("elevate_failed", reason=self.worker.error))
        else:
            self.done(QDialog.DialogCode.Accepted if self.worker.started_copy else QDialog.DialogCode.Rejected)

    def shutdown(self, *, wait: bool = True) -> None:
        """Invalidate UI replies and optionally join; closing cannot cancel Windows approval."""
        self._closed = True
        if wait:
            wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: defer dismissal until the captured launch has completely joined."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
