"""Owned, opt-out daily update checks with a fixed release link and no installation."""

from __future__ import annotations

import html
import http.client
import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QLockFile, QSettings, QStandardPaths, QThread, QTimer, Signal
from PySide6.QtWidgets import QLabel, QMainWindow

from je_file_tree import __version__
from je_file_tree.core.updates import PROJECT_URL, check_due, fetch_release
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for

ENABLED_KEY = "check_updates"
ATTEMPT_KEY = "update_last_attempt"
_TICK_MS = 60 * 60 * 1000
_START_MS = 30 * 1000
_LOG = logging.getLogger(__name__)


class UpdateWorker(QThread):
    """Keep network reads off the GUI thread and retain failures until the owned worker is joined."""

    ready = Signal(str)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.cancel = threading.Event()
        self.error: str | None = None

    def run(self) -> None:
        """Read metadata once; canceled replies cannot publish a notice."""
        try:
            version = fetch_release(__version__, self.cancel)
        except (OSError, ValueError, UnicodeError, http.client.HTTPException, RecursionError) as error:
            self.error = str(error)
            _LOG.debug("Update check failed: %s", self.error)
            return
        if version and not self.cancel.is_set():
            self.ready.emit(version)


class UpdateNotice(QObject):
    """Claim attempts before networking; constructing a window never starts a request."""

    def __init__(self, settings: QSettings, window: QMainWindow) -> None:
        super().__init__(window)
        self.settings, self.window = settings, window
        self.worker: UpdateWorker | None = None
        self.version = ""
        self.last_error: str | None = None
        self._active, self._closing = False, False
        self.label = QLabel(window)
        self.label.setOpenExternalLinks(True)
        self.label.hide()
        window.statusBar().addPermanentWidget(self.label)
        self.timer = QTimer(self)
        self.timer.setInterval(_TICK_MS)
        self.timer.timeout.connect(self.check)
        self.initial = QTimer(self)
        self.initial.setSingleShot(True)
        self.initial.timeout.connect(self.check)

    def enabled(self) -> bool:
        """Default on; QSettings may represent booleans as strings."""
        value = self.settings.value(ENABLED_KEY, True)
        return value if isinstance(value, bool) else str(value).lower() == "true"

    def start(self) -> None:
        """Enable scheduling only from the running GUI entry point, after the window is shown."""
        if not self._closing:
            self._active = True
            self.configure(self.enabled())

    def configure(self, enabled: bool) -> None:
        """Persist opt-out immediately; disabled/late replies never display a notice."""
        self.settings.setValue(ENABLED_KEY, enabled)
        self.settings.sync()
        self.timer.stop()
        self.initial.stop()
        if enabled and self._active and not self._closing:
            self.timer.start()
            self.initial.start(_START_MS)
        else:
            self.label.hide()
            if self.worker:
                self.worker.cancel.set()

    def _claim(self) -> bool:
        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        if not location:
            raise OSError("Application data location is unavailable")
        folder = Path(location)
        folder.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(folder / "update-check.lock"))
        if not lock.tryLock(0):
            return False
        try:
            self.settings.sync()
            now = time.time()
            if not self.enabled() or not check_due(self.settings.value(ATTEMPT_KEY, None), now):
                return False
            self.settings.setValue(ATTEMPT_KEY, now)
            self.settings.sync()
            if self.settings.status() != QSettings.Status.NoError:
                raise OSError("Could not persist the update attempt")
            return True
        finally:
            lock.unlock()

    def check(self) -> None:
        """Start at most one owned request after a durable cross-process daily claim."""
        if self._closing or not self._active or not self.enabled() or self.worker:
            return
        try:
            if not self._claim():
                return
        except OSError as error:
            self.last_error = str(error)
            _LOG.debug("Update scheduling failed: %s", self.last_error)
            return
        worker = UpdateWorker(self)
        worker.ready.connect(lambda version: self._ready(worker, version))
        worker.finished.connect(lambda: self._finished(worker))
        self.worker = worker
        worker.start()

    def _ready(self, worker: UpdateWorker, version: str) -> None:
        if self.worker is worker and self.enabled() and not self._closing and not worker.cancel.is_set():
            self.version = version
            self.retranslate()
            self.label.show()

    def _finished(self, worker: UpdateWorker) -> None:
        if self.worker is worker:
            self.last_error, self.worker = worker.error, None
        worker.deleteLater()

    def retranslate(self) -> None:
        """Translate the notice while keeping the link fixed and version metadata escaped."""
        if self.version:
            self.label.setText(f'<a href="{PROJECT_URL}{self.version}/">'
                               f'{html.escape(tr("update_available", version=self.version))}</a>')
            self.label.setToolTip(tr("action_check_updates_tip"))

    def shutdown(self) -> None:
        """Stop timers and join the current request before the window is destroyed."""
        self._closing = True
        self.timer.stop()
        self.initial.stop()
        if self.worker:
            worker, self.worker = self.worker, None
            worker.cancel.set()
            wait_for(worker)
            self.last_error = worker.error
