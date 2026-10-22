"""Edit Explorer registration explicitly; opening this dialog never changes the registry."""

from __future__ import annotations

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QCheckBox, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from je_file_tree.gui import shell_integration
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog, after_threads


class ShellSettingsWorker(QThread):
    """Read or explicitly apply one captured current-user Explorer registration request."""

    def __init__(self, enabled: bool | None, label: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.enabled, self.label = enabled, label
        self.installed = False
        self.error: str | None = None

    def run(self) -> None:
        """Run native registry/Shell calls without reading widgets or translating on this thread."""
        try:
            if self.enabled is None:
                self.installed = shell_integration.installed()
            else:
                shell_integration.set_enabled(self.enabled, self.label)
        except OSError as error:
            self.error = str(error)


class ShellIntegrationDialog(WorkerDialog):
    """Apply only explicit Save; keep the dialog alive until its native request joins."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._closed = False
        self._readable = False
        self._worker: ShellSettingsWorker | None = None
        self.setWindowTitle(tr("action_shell_integration"))
        self.enabled = QCheckBox(tr("shell_enabled"))
        hint = QLabel(tr("shell_hint"))
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.enabled)
        layout.addWidget(hint)
        layout.addWidget(self.status)
        layout.addWidget(self.buttons)
        self.resize(560, 230)
        self._start(None)

    def _start(self, enabled: bool | None) -> None:
        self.enabled.setEnabled(False)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
        self.status.setText(tr("shell_reading" if enabled is None else "shell_saving"))
        worker = ShellSettingsWorker(enabled, tr("shell_scan"), self)
        self._worker = worker
        worker.finished.connect(lambda: after_threads((worker,), lambda: self._completed(worker), self))
        worker.start()

    def _completed(self, worker: ShellSettingsWorker) -> None:
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()
        if self._closed:
            return
        if worker.error is not None:
            self.status.setText(tr("shell_failed", reason=worker.error))
        elif worker.enabled is None:
            self._readable = True
            self.enabled.setChecked(worker.installed)
            self.status.clear()
        else:
            super().accept()
            return
        self.enabled.setEnabled(self._readable)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(self._readable)

    def accept(self) -> None:
        """Capture one Save request; failed writes keep their literal error and permit another Save."""
        if self._closed or not self._readable or self._worker is not None:
            return
        self._start(self.enabled.isChecked())

    def shutdown(self, *, wait: bool = True) -> None:
        """Invalidate replies and optionally join; a started native write is never terminated or undone."""
        self._closed = True
        if self._worker is not None:
            self.status.setText(tr("shell_waiting"))
            if wait:
                wait_for(self._worker)

    def done(self, result: int) -> None:
        """Qt: defer Cancel, Escape and window closing until the native call has joined."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
