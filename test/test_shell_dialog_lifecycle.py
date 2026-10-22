"""Explorer settings must keep GUI timers and ownership live during native calls."""

import threading
import time

import pytest
from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox
from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export

from je_file_tree.gui import shell_integration as shell
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.shell_dialog import ShellIntegrationDialog


def _pump(app, done):
    deadline = time.monotonic() + 5
    while not done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.001)
    assert done(), "shell settings continuation did not complete"


def _dispose(dialog, app, release):
    release.set()
    dialog.reject()
    _pump(app, lambda: all(worker.wait(0) for worker in dialog.findChildren(QThread)))
    app.processEvents()
    dialog.deleteLater()


def test_held_read_keeps_timers_live_and_cancel_discards_reply(qapp, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    threads, changes, finished, ticks = [], [], [], []

    def read():
        threads.append(QThread.currentThread())
        entered.set()
        release.wait(5)
        return True

    monkeypatch.setattr(shell, "installed", read)
    monkeypatch.setattr(shell, "set_enabled", lambda *args: changes.append(args))
    dialog = ShellIntegrationDialog()
    dialog.finished.connect(finished.append)
    dialog.show()
    try:
        _pump(qapp, entered.is_set)
        assert len(threads) == 1 and threads[0] is not qapp.thread()
        assert not dialog.enabled.isEnabled()
        assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
        dialog.accept()
        assert not changes
        QTimer.singleShot(10, lambda: ticks.append(True))
        _pump(qapp, lambda: bool(ticks))
        dialog.reject()
        assert not finished and dialog.isVisible()
        release.set()
        _pump(qapp, lambda: bool(finished))
        assert finished == [QDialog.DialogCode.Rejected]
        assert not dialog.enabled.isChecked() and not changes
    finally:
        _dispose(dialog, qapp, release)


@pytest.mark.parametrize("close", ["reject", "close", "done", "escape"])
def test_held_save_has_one_captured_request_and_joins_before_close(qapp, monkeypatch, close):
    entered, release = threading.Event(), threading.Event()
    threads, changes, finished, ticks = [], [], [], []
    monkeypatch.setattr(shell, "installed", lambda: False)

    def write(*args):
        changes.append(args)
        threads.append(QThread.currentThread())
        entered.set()
        release.wait(5)

    monkeypatch.setattr(shell, "set_enabled", write)
    dialog = ShellIntegrationDialog()
    dialog.finished.connect(finished.append)
    dialog.show()
    try:
        _pump(qapp, dialog.enabled.isEnabled)
        dialog.enabled.setChecked(True)
        dialog.accept()
        _pump(qapp, entered.is_set)
        assert threads[0] is not qapp.thread()
        dialog.enabled.setChecked(False)
        dialog.accept()
        assert changes == [(True, tr("shell_scan"))]
        QTimer.singleShot(10, lambda: ticks.append(True))
        _pump(qapp, lambda: bool(ticks))
        if close == "done":
            dialog.done(QDialog.DialogCode.Rejected)
        elif close == "escape":
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        else:
            getattr(dialog, close)()
        assert not finished and dialog.isVisible()
        release.set()
        _pump(qapp, lambda: bool(finished))
        assert finished == [QDialog.DialogCode.Rejected]
        assert changes == [(True, tr("shell_scan"))]
        assert all(worker.wait(0) for worker in dialog.findChildren(QThread))
    finally:
        _dispose(dialog, qapp, release)


def test_failed_read_stays_literal_and_never_enables_save(qapp, monkeypatch):
    changes = []
    reason = "<b>blocked & unavailable</b>\nregistry"

    def read():
        raise PermissionError(reason)

    monkeypatch.setattr(shell, "installed", read)
    monkeypatch.setattr(shell, "set_enabled", lambda *args: changes.append(args))
    dialog = ShellIntegrationDialog()
    try:
        _pump(qapp, lambda: reason in dialog.status.text())
        assert dialog.status.textFormat() == Qt.TextFormat.PlainText
        assert reason in dialog.status.text()
        assert not dialog.enabled.isEnabled()
        dialog.accept()
        assert not changes
    finally:
        _dispose(dialog, qapp, threading.Event())


@pytest.mark.parametrize("saving", [False, True])
def test_owner_closing_retains_dialog_guard_and_native_worker(window, qapp, monkeypatch, saving):
    from je_file_tree.gui import main_window

    entered, release = threading.Event(), threading.Event()
    changes, observed, errors = [], [], []

    def held():
        entered.set()
        release.wait(5)
        return False

    def write(*args):
        changes.append(args)
        held()

    monkeypatch.setattr(shell, "supported", lambda: True)
    monkeypatch.setattr(shell, "installed", (lambda: False) if saving else held)
    monkeypatch.setattr(shell, "set_enabled", write)
    original_exec = ShellIntegrationDialog.exec

    def exec_with_close(dialog):
        def close_when_held():
            try:
                if saving:
                    _pump(qapp, dialog.enabled.isEnabled)
                    dialog.enabled.setChecked(True)
                    dialog.accept()
                _pump(qapp, entered.is_set)
                observed.append(dialog in window._settings_dialogs and not window.operation_busy)
                window.close()
                observed.append(window._close_waiting and not window._close_ready)
                QTimer.singleShot(20, release.set)
            except AssertionError as error:
                errors.append(str(error))
                release.set()
                dialog.reject()
        QTimer.singleShot(0, close_when_held)
        return original_exec(dialog)

    monkeypatch.setattr(main_window.ShellIntegrationDialog, "exec", exec_with_close)
    try:
        window.edit_shell_integration()
        _pump(qapp, lambda: window._close_ready)
        assert not errors and observed == [True, True]
        assert release.is_set() and not window._settings_dialogs
        assert changes == ([(True, tr("shell_scan"))] if saving else [])
        assert all(worker.wait(0) for worker in window.findChildren(QThread))
    finally:
        release.set()


def test_opening_shell_settings_keeps_an_existing_live_reader(window, qapp, tmp_path, monkeypatch):
    from je_file_tree.core.scanner import scan
    from je_file_tree.gui import change_watch, scan_worker

    (tmp_path / "kept").write_bytes(b"fixture")
    window.results.show_outcome(scan_worker.analyse(scan(tmp_path)))
    entered, release = threading.Event(), threading.Event()

    def watch(_root, _changed, _cancel, *, ready):
        ready("directory_changes")
        entered.set()
        release.wait(5)

    monkeypatch.setattr(change_watch, "watch", watch)
    monkeypatch.setattr(change_watch, "supported", lambda: True)
    monkeypatch.setattr(shell, "supported", lambda: True)
    monkeypatch.setattr(shell, "installed", lambda: False)
    window._actions["follow_changes"].setChecked(True)
    _pump(qapp, entered.is_set)
    reader = window._follow.worker
    original_exec = ShellIntegrationDialog.exec

    def canceled_settings(dialog):
        QTimer.singleShot(10, dialog.reject)
        return original_exec(dialog)

    monkeypatch.setattr(ShellIntegrationDialog, "exec", canceled_settings)
    try:
        window.edit_shell_integration()
        assert not reader.cancel.is_set()
        assert window._follow.worker is reader and reader.isRunning()
        assert (tmp_path / "kept").read_bytes() == b"fixture"
    finally:
        release.set()
        window._follow.shutdown()
