"""Opt-in service ownership, durable claims, gentle scans and explicit Quit without host notifications."""

from dataclasses import replace
import hashlib
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QSystemTrayIcon

from test_gui import _wait
from je_file_tree.core.background import CapacityObservation, MonitorConfig, load_attempts
from je_file_tree.core.scanner import ScanCancelledError, scan
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting
from je_file_tree.core.history import ScanHistory, load_recurring
from je_file_tree.core.recurring import ProposalCancelledError
from je_file_tree.gui import app as gui_app, background_monitor as service, background_worker as workers
from je_file_tree.gui.background_dialog import BackgroundDialog
from je_file_tree.gui.app import create_workspace
from je_file_tree.gui.history import configured_history
from je_file_tree.gui.recurring_dialog import RecurringDialog
from je_file_tree.gui.scan_worker import wait_for


class _Tray(QSystemTrayIcon):

    def __init__(self, _icon, parent):
        super().__init__(parent)
        self.visible, self.messages, self.tooltip = False, [], ""

    @staticmethod
    def isSystemTrayAvailable():  # noqa: N802 - mirrors the native Qt API without host dispatch
        return True

    @staticmethod
    def supportsMessages():  # noqa: N802 - Qt API
        return True

    def setContextMenu(self, menu):  # noqa: N802 - Qt API
        self.menu = menu

    def setToolTip(self, text):  # noqa: N802 - Qt API
        self.tooltip = text

    def isVisible(self):  # noqa: N802 - Qt API
        return self.visible

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def showMessage(self, *args):  # noqa: N802 - Qt API
        self.messages.append(args)


@pytest.fixture
def monitored(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(service, "QSystemTrayIcon", _Tray)
    monkeypatch.setattr(workers.CapacityWorker, "run", lambda self: None)
    settings = QSettings(str(tmp_path / "background.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    settings.setValue("check_updates", False)
    workspace = create_workspace(settings)
    yield workspace
    workspace.quit_application()
    workspace.deleteLater()


def _enable(workspace, roots=()):
    workspace.start_services()
    workspace.background.configure(MonitorConfig(True, roots=roots))
    return workspace.background


def test_passive_factory_default_off_and_close_to_tray_requires_actual_availability(monitored, qapp, monkeypatch):
    monitor = monitored.background
    assert not monitor.active and not monitor.tray.isVisible() and monitor.scan is None
    assert not monitor.timer.isActive()
    monitored.show()
    _enable(monitored)
    monitored.close()
    assert monitored.isHidden() and not monitored._closing and monitor.can_hide
    monitor.show_window()
    assert not monitored.isHidden()
    monkeypatch.setattr(_Tray, "isSystemTrayAvailable", staticmethod(lambda: False))
    assert not monitor.can_hide
    monitored.close()
    assert monitored._closing and monitor.closing and not monitor.tray.isVisible()


def test_unavailable_tray_never_hides_or_dispatches_scans(monitored, monkeypatch, tmp_path):
    monkeypatch.setattr(_Tray, "isSystemTrayAvailable", staticmethod(lambda: False))
    monitor = _enable(monitored, (str(tmp_path),))
    monitor.tick()
    assert not monitor.can_hide and not monitor.timer.isActive() and monitor.scan is None
    assert "unavailable" in monitor.error and not monitored.settings.contains(service.ATTEMPTS_KEY)


def test_tray_disappearance_restores_hidden_workspace_before_new_background_work(monitored, monkeypatch):
    monitored.show()
    monitor = _enable(monitored)
    monitored.close()
    assert monitored.isHidden()
    monkeypatch.setattr(_Tray, "isSystemTrayAvailable", staticmethod(lambda: False))
    monitor.tick()
    assert not monitored.isHidden() and "unavailable" in monitor.error
    assert monitor.scan is None and monitor.capacity is None


def test_durable_claim_throttles_second_owner_and_corruption_fails_closed(monitored, tmp_path):
    root = str(tmp_path)
    monitored.settings.setValue(service.CONFIG_KEY, MonitorConfig(True, roots=(root,)).dumps())
    first = monitored.background._claim()
    assert first is not None and first.state == "claimed"
    assert monitored.background._claim() is None
    receipts = load_attempts(monitored.settings.value(service.ATTEMPTS_KEY))
    assert receipts[first.key] == first
    monitored.background._finish_attempt(replace(first, state="failed"))
    assert monitored.background._claim() is None
    monitored.settings.setValue(service.ATTEMPTS_KEY, '{"version":1,"attempts":[{"state":"approved"}]}')
    with pytest.raises(ValueError):
        monitored.background._claim()


def test_startup_dialog_cancel_has_no_native_effect_and_accept_is_separate_opt_in(monitored, monkeypatch):
    from je_file_tree.gui import autostart
    from PySide6.QtWidgets import QDialog

    calls = []
    monkeypatch.setattr(autostart, "registration", lambda: autostart.Registration(False, "owned fixture"))
    monkeypatch.setattr(autostart, "set_enabled", calls.append)

    def reject(dialog):
        dialog.enabled.setChecked(True)
        dialog.startup.setChecked(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(BackgroundDialog, "exec", reject)
    monitored.background.configure_dialog()
    assert not calls and not monitored.settings.contains(service.CONFIG_KEY)

    def accept(dialog):
        dialog.enabled.setChecked(True)
        dialog.startup.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(BackgroundDialog, "exec", accept)
    monitored.background.configure_dialog()
    assert calls == [True] and service.configuration(monitored.settings).enabled


def test_disabling_monitor_explicitly_removes_owned_startup_and_failure_stays_visible(monitored, monkeypatch):
    from je_file_tree.gui import autostart
    from PySide6.QtWidgets import QDialog

    _enable(monitored)
    monkeypatch.setattr(autostart, "registration", lambda: autostart.Registration(True, "owned fixture"))
    calls = []

    def remove(enabled):
        calls.append(enabled)
        raise OSError("entry changed before removal")

    monkeypatch.setattr(autostart, "set_enabled", remove)

    def accept(dialog):
        assert dialog.startup.isChecked()
        dialog.enabled.setChecked(False)
        assert not dialog.startup.isChecked()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(BackgroundDialog, "exec", accept)
    monitored.background.configure_dialog()
    assert calls == [False] and not monitored.background.config.enabled
    assert "changed before removal" in monitored.background.error and not monitored.isHidden()


def test_actual_scheduled_history_is_gentle_and_preserves_sources_without_touching_tabs(monitored, qapp, tmp_path):
    source = tmp_path / "scheduled-source"
    source.mkdir()
    file = source / "保留.bin"
    file.write_bytes(b"owned scheduled payload" * 1024)
    proof = file.stat().st_ino, hashlib.sha256(file.read_bytes()).hexdigest()
    monitor = _enable(monitored, (str(source),))
    monitor.tick()
    worker = monitor.scan
    assert worker is not None and worker.options.gentle and worker.options.workers == 1
    _wait(qapp, lambda: monitor.scan is None)
    history = configured_history(monitored.settings).read(str(source))
    assert history.count == 1 and not history.entries[0].incomplete
    assert monitored.current.results.outcome is None
    assert (file.stat().st_ino, hashlib.sha256(file.read_bytes()).hexdigest()) == proof
    receipt = next(iter(load_attempts(monitored.settings.value(service.ATTEMPTS_KEY)).values()))
    assert receipt.state == "complete"
    report = monitor.reports[receipt.key]
    assert monitor.report_status(report) is None and not report.comparison_complete
    assert load_recurring(history.entries[0]).identity == report.baseline.identity
    monitor.tick()
    assert monitor.scan is None


def test_foreground_scan_cancels_and_joins_gentle_scan_before_dispatch(monitored, qapp, tmp_path, monkeypatch):
    source = tmp_path / "scheduled"
    source.mkdir()
    (source / "kept").write_bytes(b"kept")
    entered, ended = threading.Event(), threading.Event()

    def blocking(root, *, options, cancel):
        assert options.gentle and options.workers == 1
        entered.set()
        cancel.wait()
        ended.set()
        raise ScanCancelledError(scan(root))

    monkeypatch.setattr(workers, "scan", blocking)
    monitor = _enable(monitored, (str(source),))
    monitor.tick()
    assert entered.wait(5)
    worker = monitor.scan
    monitored.current.start_scan(str(source))
    assert ended.is_set() and worker.cancel.is_set() and not worker.isRunning()
    assert monitor.scan is None
    _wait(qapp, lambda: monitored.current._worker is None)
    receipt = next(iter(load_attempts(monitored.settings.value(service.ATTEMPTS_KEY)).values()))
    assert receipt.state == "canceled" and (source / "kept").read_bytes() == b"kept"


def test_low_capacity_notifies_once_unknown_stays_unknown_and_only_opens_window(monitored, tmp_path):
    monitor = _enable(monitored)
    monitor.timer.stop()
    root = str(tmp_path)
    for available in (99, 99, None, 99, 100, 99):
        worker = workers.CapacityWorker(monitor)
        worker.rows = (CapacityObservation(root, 1000, available),)
        monitor.capacity = worker
        monitor._capacity_finished(worker)
    assert len(monitor.tray.messages) == 2
    assert "Low available space" in monitor.label.text() and monitor.scan is None
    monitor.tray.messageClicked.emit()
    assert not monitored.isHidden() and monitored.current.results.outcome is None


def test_explicit_quit_joins_native_capacity_work_instead_of_hiding(monitored, tmp_path, monkeypatch):
    entered, ended = threading.Event(), threading.Event()

    def blocking(self):
        entered.set()
        self.cancel.wait()
        ended.set()

    monkeypatch.setattr(workers.CapacityWorker, "run", blocking)
    monitor = _enable(monitored)
    monitor.tick()
    assert entered.wait(5)
    worker = monitor.capacity
    monitored.current.quit_application()
    assert ended.is_set() and not worker.isRunning()
    assert monitor.closing and monitored._closing and not monitor.can_hide


def test_dialog_cancel_and_removed_roots_never_modify_registration_or_sources(monitored, tmp_path):
    config = MonitorConfig(True, roots=(str(tmp_path),))
    monitored.settings.setValue(service.CONFIG_KEY, config.dumps())
    dialog = BackgroundDialog(config, monitored)
    assert dialog.configuration() == config
    dialog.roots.item(0).setSelected(True)
    dialog._remove()
    assert not dialog.configuration().roots
    dialog.reject()
    assert service.configuration(monitored.settings) == config and tmp_path.is_dir()
    dialog.deleteLater()


def test_disabled_history_records_failed_attempt_without_source_dispatch(monitored, tmp_path):
    monitored.settings.setValue("history_enabled", False)
    monitor = _enable(monitored, (str(tmp_path),))
    monitor.tick()
    assert monitor.scan is None and "history" in monitor.error
    receipt = next(iter(load_attempts(monitored.settings.value(service.ATTEMPTS_KEY)).values()))
    assert receipt.state == "failed"


def test_background_entry_skips_elevation_and_only_hides_when_tray_is_available(qapp, monkeypatch):
    calls = []
    monitor = SimpleNamespace(can_hide=True)
    window = SimpleNamespace(background=monitor, show=lambda: calls.append("show"),
                             start_services=lambda: calls.append("services"), hide=lambda: calls.append("hide"))
    monkeypatch.setattr(gui_app, "claim_taskbar_button", lambda: None)
    monkeypatch.setattr(gui_app, "pace_workers", lambda: None)
    monkeypatch.setattr(gui_app, "wants_admin_prompt", lambda _settings: pytest.fail("background asked for elevation"))
    monkeypatch.setattr(gui_app, "create_workspace", lambda *_args: window)
    monkeypatch.setattr(type(qapp), "exec", lambda _self: 0)
    assert gui_app.main(["--background"]) == 0
    assert calls == ["show", "services", "hide"]
    monitor.can_hide = False
    calls.clear()
    assert gui_app.main(["--background"]) == 0 and calls == ["show", "services"]


def test_actual_second_schedule_compares_bound_baseline_without_source_mutations(monitored, qapp, tmp_path):
    source = tmp_path / "排程"
    source.mkdir()
    policy = CleanupPolicy((RuleSetting("crash_dumps", True, 0),))
    monitored.settings.setValue("cleanup_policy", policy.dumps())
    (source / "old.dmp").write_bytes(b"old payload")
    monitor = _enable(monitored, (str(source),))
    monitor.tick()
    _wait(qapp, lambda: monitor.scan is None)
    first = next(iter(monitor.reports.values()))
    assert len(first.baseline.candidates) == 1 and not first.comparison_complete
    (source / "new.dmp").write_bytes(b"new owned payload" * 100)
    proof = {path.name: (path.stat().st_ino, hashlib.sha256(path.read_bytes()).hexdigest())
             for path in source.iterdir()}
    monitor.configure(replace(monitor.config, interval_hours=monitor.config.interval_hours + 1))
    monitor.tick()
    _wait(qapp, lambda: monitor.scan is None)
    second = next(iter(monitor.reports.values()))
    assert second.comparison_complete and [row.path for row in second.new_junk] == [str(source / "new.dmp")]
    assert second.growth[0].path == str(source) and second.growth[0].change == (source / "new.dmp").stat().st_size
    assert monitored.current.results.outcome is None and monitor.report_status(second) is None
    assert proof == {path.name: (path.stat().st_ino, hashlib.sha256(path.read_bytes()).hexdigest())
                     for path in source.iterdir()}
    monitored.settings.setValue("cleanup_policy", CleanupPolicy((RuleSetting("crash_dumps", False, 0),)).dumps())
    assert monitor.report_status(second) == "rule_changed"
    monitored.settings.setValue("cleanup_policy", "invalid")
    assert monitor.report_status(second) == "unavailable" and monitor.error
    monitor.configure(replace(monitor.config, roots=()))
    assert not monitor.reports


def test_invalid_proposal_metadata_keeps_saved_history_and_visible_error(monitored, qapp, tmp_path, monkeypatch):
    source = tmp_path / "kept-source"
    source.mkdir()
    (source / "kept").write_bytes(b"kept")
    monkeypatch.setattr(workers, "load_recurring", lambda _entry: (_ for _ in ()).throw(ValueError("invalid baseline")))
    configured_history(monitored.settings).save(scan(source).root)
    monitor = _enable(monitored, (str(source),))
    monitor.tick()
    _wait(qapp, lambda: monitor.scan is None)
    assert configured_history(monitored.settings).read(str(source)).count == 2
    assert not monitor.reports and "invalid baseline" in monitor.error
    assert next(iter(load_attempts(monitored.settings.value(service.ATTEMPTS_KEY)).values())).state == "complete"
    assert (source / "kept").read_bytes() == b"kept"


def test_cancellation_during_preparation_never_publishes_history_or_report(monitored, tmp_path, monkeypatch):
    source = tmp_path / "owned-source"
    source.mkdir()
    (source / "kept").write_bytes(b"kept")
    config = MonitorConfig(True, roots=(str(source),))
    monitored.settings.setValue(service.CONFIG_KEY, config.dumps())
    attempt = monitored.background._claim()
    store = ScanHistory(tmp_path / "private-history")
    worker = workers.ScheduledWorker(str(source), monitored.current._scan_options(), store, monitored,
                                     proposal_context=(attempt, config.interval_hours))

    def cancel(*_args, **_kwargs):
        worker.cancel.set()
        raise ProposalCancelledError()

    monkeypatch.setattr(workers, "prepare", cancel)
    worker.start()
    wait_for(worker)
    assert worker.state == "canceled" and worker.entry is None and worker.proposal is None
    assert store.read(str(source)).count == 0 and (source / "kept").read_bytes() == b"kept"
    worker.deleteLater()


def test_recurring_readonly_dialog_uses_literal_paths_and_refreshes_expiry(monitored, qapp, tmp_path):
    source = tmp_path / "literal & path"
    source.mkdir()
    (source / "owned.dmp").write_bytes(b"owned")
    monitored.settings.setValue("cleanup_policy", CleanupPolicy((RuleSetting("crash_dumps", True, 0),)).dumps())
    monitor = _enable(monitored, (str(source),))
    monitor.tick()
    _wait(qapp, lambda: monitor.scan is None)
    report = next(iter(monitor.reports.values()))
    status = [None]
    dialog = RecurringDialog((report,), lambda _report: status[0], monitored.current)
    assert "Unknown" in dialog.summary.text() and dialog.current.rowCount() == 1
    assert dialog.current.data(dialog.current.index(0, 0)) == str(source / "owned.dmp")
    assert dialog.current.data(dialog.current.index(0, 1)) == "Crash dumps"
    status[0] = "expired"
    dialog._summary()
    assert "Expired" in dialog.summary.text()
    dialog.shutdown()
    dialog.deleteLater()
    assert (source / "owned.dmp").read_bytes() == b"owned"
    assert not monitored.current._path_dialogs and monitored.current.results.outcome is None
    empty = RecurringDialog((), monitor.report_status, monitored.current)
    assert "No scheduled report" in empty.summary.text()
    empty.shutdown()
    empty.deleteLater()


def test_recurring_view_guard_serializes_tabs_and_never_runs_sources(monitored, monkeypatch):
    owner = monitored.current
    other = monitored.add_tab()
    called = []

    def view(dialog):
        assert monitored.operations.busy and not owner._actions["recurring"].isEnabled()
        assert not other._actions["recurring"].isEnabled()
        called.append(True)
        return 0

    monkeypatch.setattr(RecurringDialog, "exec", view)
    assert owner._actions["recurring"].isEnabled()
    owner.show_recurring()
    assert called == [True] and not monitored.operations.busy
    assert other._actions["recurring"].isEnabled() and owner.results.outcome is None
    owner._analysers.add(object())
    owner.show_recurring()
    assert called == [True]
    owner._analysers.clear()


def test_invalid_scheduled_policy_refuses_dispatch_before_claim(monitored, tmp_path):
    monitored.settings.setValue("cleanup_policy", "invalid")
    monitor = _enable(monitored, (str(tmp_path),))
    monitor.tick()
    assert monitor.scan is None and not monitored.settings.contains(service.ATTEMPTS_KEY)
    assert monitor.error and not monitor.reports
