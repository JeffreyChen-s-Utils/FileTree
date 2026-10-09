"""Opt-in tray lifetime, bounded capacity notifications and serialized gentle history scans."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QLockFile, QObject, QSettings, QStandardPaths, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMenu, QSystemTrayIcon

from je_file_tree.core.background import (
    MonitorConfig, ScanAttempt, SpaceWarnings, claim_scan, due_roots, dump_attempts, load_attempts, load_config,
)
from je_file_tree.core.formatting import format_size
from je_file_tree.core.cleanup_policy import CleanupPolicy, load_policy
from je_file_tree.core.recurring import RecurringProposal, binding_status
from je_file_tree.gui import autostart
from je_file_tree.gui.background_dialog import BackgroundDialog
from je_file_tree.gui.background_worker import CapacityWorker, ScheduledWorker
from je_file_tree.gui.history import configured_history
from je_file_tree.gui.icon import app_icon
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.recurring_dialog import RecurringDialog
from je_file_tree.gui.recurring_review import RecurringFlow, ReviewBinding
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import after_threads

if TYPE_CHECKING:
    from je_file_tree.gui.workspace import ScanWorkspace

CONFIG_KEY = "background_config"
ATTEMPTS_KEY = "background_attempts"
_TICK_MS = 60000


def configuration(settings: QSettings) -> MonitorConfig:
    """Default off; corrupt stored options fail visibly rather than enabling monitoring."""
    text = settings.value(CONFIG_KEY, None)
    return MonitorConfig() if text is None else load_config(text)


def _lock(settings: QSettings) -> QLockFile:
    if settings.format() == QSettings.Format.IniFormat:
        target = Path(settings.fileName()).with_suffix(".background.lock")
    else:
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        if not folder:
            raise OSError("Background scheduling data location is unavailable")
        target = Path(folder) / "background-schedule.lock"
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(target))
    lock.setStaleLockTime(5 * 60 * 1000)
    return lock


class BackgroundMonitor(QObject):
    """One passive workspace service; constructing integrations never starts scans or shows a tray."""

    def __init__(self, workspace: ScanWorkspace) -> None:
        super().__init__(workspace)
        self.workspace, self.settings = workspace, workspace.settings
        self.config = MonitorConfig()
        self.capacity: CapacityWorker | None = None
        self.scan: ScheduledWorker | None = None
        self.attempt: ScanAttempt | None = None
        self._retiring: dict[ScheduledWorker, ScanAttempt | None] = {}
        self.reports: dict[str, RecurringProposal] = {}
        self.warnings = SpaceWarnings()
        self.active, self.closing = False, False
        self.error, self._status, self._detail = "", "background_off", ""
        self.tray = QSystemTrayIcon(app_icon(), workspace)
        self.menu = QMenu(workspace)
        self.show_action, self.settings_action, self.quit_action = (QAction(self) for _ in range(3))
        self.show_action.triggered.connect(self.show_window)
        self.settings_action.triggered.connect(self.configure_dialog)
        self.quit_action.triggered.connect(workspace.quit_application)
        for action in (self.show_action, self.settings_action, self.quit_action):
            self.menu.addAction(action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        self.tray.messageClicked.connect(self.show_window)
        self.label = QLabel(workspace)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setMaximumWidth(350)
        self.label.hide()
        workspace.statusBar().addPermanentWidget(self.label)
        self.timer = QTimer(self)
        self.timer.setInterval(_TICK_MS)
        self.timer.timeout.connect(self.tick)
        self.retranslate()

    @property
    def can_hide(self) -> bool:
        """Never hide an application without an available visible tray and explicit monitor opt-in."""
        return (self.active and not self.closing and self.config.enabled
                and self.tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable())

    def start(self) -> None:
        """Schedule only after the actual application starts its services."""
        self.active = True
        try:
            self.configure(configuration(self.settings))
        except (OSError, ValueError) as error:
            self._failed(str(error))

    def configure_dialog(self) -> None:
        """Review explicit preferences; cancel leaves both saved options and native state unchanged."""
        try:
            config = configuration(self.settings)
        except (ValueError, OSError) as error:
            self._failed(str(error))
            config = MonitorConfig()
        startup, startup_error = None, ""
        try:
            startup = autostart.registration()
        except (OSError, ValueError) as error:
            startup_error = tr("background_startup_error", detail=str(error))
        dialog = BackgroundDialog(config, self.workspace, startup=startup, startup_error=startup_error)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.configure(dialog.configuration())
                if (startup is not None and dialog.startup.isChecked() != startup.installed
                        and self.settings.status() == QSettings.Status.NoError):
                    try:
                        autostart.set_enabled(dialog.startup.isChecked())
                    except (OSError, ValueError) as error:
                        self.show_window()
                        self._failed(tr("background_startup_error", detail=str(error)))
        finally:
            dialog.deleteLater()

    def configure(self, config: MonitorConfig) -> None:
        """Persist opt-in and join previous work; changing settings never installs automatic startup."""
        self._stop_workers()
        self.timer.stop()
        self.tray.hide()
        self.settings.setValue(CONFIG_KEY, config.dumps())
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            self.config = replace(self.config, enabled=False)
            self.show_window()
            self._failed("Could not save background monitoring preferences")
            return
        self.config = config
        self._retain_reports(config)
        self.error = ""
        if not config.enabled or not self.active or self.closing:
            self._set_status("background_off")
            if self.workspace.isHidden() and not self.closing:
                self.show_window()
            self.label.hide()
            return
        self.label.show()
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._failed(tr("background_no_tray"))
            return
        self.tray.show()
        self.timer.start()
        self._set_status("background_ready")
        QTimer.singleShot(0, self.tick)

    def show_window(self) -> None:
        """Restore the owning workspace; a tray message never approves or performs clean-up."""
        if not self.closing:
            self.workspace.showNormal()
            self.workspace.raise_()
            self.workspace.activateWindow()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def tick(self) -> None:
        """Capacity reads stay off the GUI thread; scheduled source scans wait for every tab to be idle."""
        if not self.can_hide:
            if (not self.closing and self.active and self.config.enabled and self.tray.isVisible()
                    and not QSystemTrayIcon.isSystemTrayAvailable()):
                self.show_window()
                self._failed(tr("background_no_tray"))
            return
        if self.capacity is None:
            worker = CapacityWorker(self)
            worker.finished.connect(lambda: after_threads((worker,), lambda: self._capacity_finished(worker), self))
            self.capacity = worker
            worker.start()
        if (self.scan is not None or self._retiring or self.workspace.operations.busy
                or QApplication.activeModalWidget() is not None
                or any(window._worker is not None or window._analysers or window._undo.available
                       for window in self.workspace.operations.windows)):
            return
        self._start_scan()

    def _start_scan(self) -> None:
        try:
            policy = self._policy()
            attempt = self._claim()
            if attempt is None:
                return
            self.reports.pop(attempt.key, None)
            config = configuration(self.settings)
            self._retain_reports(config)
            history = configured_history(self.settings)
            if history is None:
                self._finish_attempt(replace(attempt, state="failed"))
                self._failed(tr("background_history_disabled"))
                return
        except (OSError, ValueError) as error:
            self._failed(str(error))
            return
        worker = ScheduledWorker(attempt.root, self.workspace.current._scan_options(), history, self,
                                 proposal_context=(attempt, config.interval_hours), policy=policy)
        worker.finished.connect(lambda: after_threads((worker,), lambda: self._scan_finished(worker, attempt), self))
        self.attempt, self.scan = attempt, worker
        self._set_status("background_scanning", attempt.root)
        worker.start()

    def _policy(self) -> CleanupPolicy:
        text = self.settings.value("cleanup_policy", None)
        return CleanupPolicy() if text is None else load_policy(text)

    def _retain_reports(self, config: MonitorConfig) -> None:
        selected = {claim_scan(config, root, time.time()).key for root in config.roots}
        self.reports = {key: report for key, report in self.reports.items() if key in selected}

    def report_status(self, report: RecurringProposal) -> str | None:
        """Recheck only bounded settings/receipt metadata; no filesystem traversal on the GUI thread."""
        try:
            self.settings.sync()
            attempts = load_attempts(self.settings.value(ATTEMPTS_KEY, dump_attempts({})))
            return binding_status(report, self._policy(), configuration(self.settings),
                                  attempts.get(report.context.attempt.key), time.time())
        except (OSError, ValueError) as error:
            self._failed(str(error))
            return "unavailable"

    def review_binding(self, report: RecurringProposal) -> ReviewBinding | None:
        """Capture strict current review metadata before worker-side source validation."""
        try:
            self.settings.sync()
            attempts = load_attempts(self.settings.value(ATTEMPTS_KEY, dump_attempts({})))
            policy, config = self._policy(), configuration(self.settings)
            return ReviewBinding(policy, config, attempts.get(report.context.attempt.key))
        except (OSError, ValueError) as error:
            self._failed(str(error))
            return None

    def show_proposals(self) -> None:
        """Show current-session bounded observations while serializing all source-operation owners."""
        if (self.closing or self.workspace.operations.busy
                or any(window._worker is not None or window._analysers
                       for window in self.workspace.operations.windows)):
            return
        self.quiesce()
        owner = self.workspace.current
        dialog = RecurringDialog(tuple(self.reports.values()), self.report_status, owner)
        owner._path_dialogs.add(dialog)
        owner._update_actions()
        requested = None
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                requested = dialog.requested
        finally:
            dialog.shutdown()
            owner._path_dialogs.discard(dialog)
            owner._update_actions()
            dialog.deleteLater()
        if requested is not None and not self.closing and self.report_status(requested) is None:
            owner = self.workspace.add_tab()
            if owner is None:
                self._failed(tr("recurring_tabs_full"))
            else:
                RecurringFlow(self, owner, requested).start()

    def _claim(self) -> ScanAttempt | None:
        lock = _lock(self.settings)
        if not lock.tryLock(0):
            return None
        try:
            self.settings.sync()
            config = configuration(self.settings)
            attempts = load_attempts(self.settings.value(ATTEMPTS_KEY, dump_attempts({})))
            now = time.time()
            due = due_roots(config, attempts, now)
            if not due:
                return None
            attempt = claim_scan(config, due[0], now)
            selected = {claim_scan(config, root, now).key for root in config.roots}
            attempts = {key: value for key, value in attempts.items() if key in selected}
            attempts[attempt.key] = attempt
            self._save_attempts(attempts)
            return attempt
        finally:
            lock.unlock()

    def _save_attempts(self, attempts: dict[str, ScanAttempt]) -> None:
        self.settings.setValue(ATTEMPTS_KEY, dump_attempts(attempts))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError("Could not persist the background scan claim")

    def _finish_attempt(self, attempt: ScanAttempt) -> None:
        lock = _lock(self.settings)
        if not lock.tryLock(0):
            raise OSError("Background scan receipt is locked by another process")
        try:
            self.settings.sync()
            attempts = load_attempts(self.settings.value(ATTEMPTS_KEY, dump_attempts({})))
            current = attempts.get(attempt.key)
            if current is not None and (current.claimed_at, current.schedule_id) == (
                    attempt.claimed_at, attempt.schedule_id):
                attempts[attempt.key] = attempt
                self._save_attempts(attempts)
        finally:
            lock.unlock()

    def _capacity_finished(self, worker: CapacityWorker) -> None:
        if worker is not self.capacity:
            return
        self.capacity = None
        if not self.closing and not worker.cancel.is_set():
            if worker.error:
                self._failed(worker.error)
            else:
                try:
                    for row in self.warnings.observe(worker.rows, self.config.threshold):
                        text = tr("background_low_space", root=row.root,
                                  free=format_size(row.available), percent=str(round(100 * row.available / row.total)))
                        self._set_status("background_warning", text)
                        if QSystemTrayIcon.supportsMessages():
                            self.tray.showMessage(tr("app_title"), text, QSystemTrayIcon.MessageIcon.Warning)
                except ValueError as error:
                    self._failed(str(error))
        worker.deleteLater()

    def _scan_finished(self, worker: ScheduledWorker, attempt: ScanAttempt) -> None:
        if worker is not self.scan:
            return
        self.scan, self.attempt = None, None
        try:
            self._finish_attempt(replace(attempt, state=worker.state))
        except (OSError, ValueError) as error:
            self._failed(str(error))
            worker.deleteLater()
            return
        if not self.closing:
            if worker.state == "complete" and worker.proposal is not None:
                self.reports[attempt.key] = worker.proposal
            if worker.error:
                self._failed(worker.error)
            elif worker.state == "canceled":
                self._set_status("background_canceled", worker.root)
            elif worker.proposal_error:
                self._failed(tr("recurring_prepare_failed", detail=worker.proposal_error))
            else:
                self._set_status("background_saved_partial" if worker.entry.incomplete else "background_saved",
                                 worker.root)
        worker.deleteLater()

    def _stop_workers(self) -> None:
        capacity, self.capacity = self.capacity, None
        if capacity is not None:
            capacity.cancel.set()
            wait_for(capacity)
            capacity.deleteLater()
        self.quiesce()

    def quiesce(self, *, wait: bool = True) -> tuple[ScheduledWorker, ...]:
        """Cancel gentle scanning before foreground scans/source reviews, retaining its claimed period."""
        scan, self.scan = self.scan, None
        if scan is not None:
            scan.cancel.set()
            attempt, self.attempt = self.attempt, None
            self._retiring[scan] = attempt
            after_threads((scan,), lambda: self._retired_scan(scan, attempt), self)
        retiring = tuple(self._retiring)
        if wait:
            for pending in retiring:
                wait_for(pending)
                # Publish its final receipt before any subsequent foreground dispatch.
                if pending in self._retiring:
                    self._retired_scan(pending, self._retiring[pending])
        return retiring

    def _retired_scan(self, scan: ScheduledWorker, attempt: ScanAttempt | None) -> None:
        if scan not in self._retiring:
            return
        self._retiring.pop(scan)
        if attempt is not None:
            try:
                self._finish_attempt(replace(attempt, state=scan.state))
            except (OSError, ValueError) as error:
                self._failed(str(error))
        if scan.error:
            self._failed(scan.error)
        scan.deleteLater()

    def shutdown(self) -> None:
        """Explicit Quit joins every native call and scan; close-to-tray is a separate workspace choice."""
        self.closing = True
        self.timer.stop()
        self.tray.hide()
        self._stop_workers()

    def _failed(self, detail: str) -> None:
        self.error = detail
        self.settings.setValue("background_last_error", detail[:4096])
        self.label.show()
        self._set_status("background_error", detail)

    def _set_status(self, key: str, detail: str = "") -> None:
        self._status, self._detail = key, detail
        self.retranslate()

    def retranslate(self) -> None:
        """Translate owned tray actions and plain-text status without changing schedule timestamps."""
        for action, key in ((self.show_action, "background_show"), (self.settings_action, "action_background_monitor"),
                            (self.quit_action, "action_quit")):
            action.setText(tr(key))
        self.label.setText(tr(self._status, detail=self._detail))
        self.tray.setToolTip(tr("app_title") + "\n" + self.label.text()[:160])
        self.label.setToolTip(self.label.text())
