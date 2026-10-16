"""Owned administrator relaunch keeps Qt live and waits for one native request."""

import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog
import pytest

from test_gui import _wait
from je_file_tree.gui.elevation_dialog import ElevationDialog, ElevationWorker
from je_file_tree.gui.i18n import tr

from test_elevation import window as window  # noqa: PLC0414 - isolated settings and teardown
from je_file_tree.gui import elevation


def test_relaunch_wait_keeps_the_gui_timer_live(window, qapp, monkeypatch):
    gui = threading.get_ident()
    release = threading.Event()
    threads, ticks = [], []

    def relaunch(_arguments):
        threads.append(threading.get_ident())
        release.wait(2)
        return False

    monkeypatch.setattr(elevation, "relaunch_elevated", relaunch)
    timer = QTimer(window)
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    native_release = threading.Timer(.15, release.set)
    native_release.start()
    try:
        window.restart_as_admin()
        assert threads and threads[0] != gui, "administrator launch blocked the GUI thread"
        assert ticks, "the GUI heartbeat stopped during native administrator approval"
    finally:
        release.set()
        native_release.join()
        timer.stop()


@pytest.mark.parametrize("started", [False, True])
def test_close_waits_for_launch_and_success_still_closes_the_original(window, qapp, monkeypatch, started):
    entered, release = threading.Event(), threading.Event()
    calls, closed, observations = [], [], []

    def relaunch(arguments):
        calls.append(list(arguments))
        entered.set()
        release.wait(3)
        return started

    monkeypatch.setattr(elevation, "relaunch_elevated", relaunch)
    monkeypatch.setattr(window, "close", lambda: closed.append(threading.get_ident()))
    window._last_path = "captured folder"
    timer = QTimer(window)
    timer.setInterval(5)

    def close_request():
        if not entered.is_set() or observations:
            return
        dialog = next(iter(window._settings_dialogs))
        window._last_path = "later folder"
        window.restart_as_admin()
        dialog.reject()
        observations.append((dialog._finish_waiting, dialog.worker.isRunning(), window._actions["elevate"].isEnabled()))
        QTimer.singleShot(50, release.set)

    timer.timeout.connect(close_request)
    timer.start()
    fallback = threading.Timer(2, release.set)
    fallback.start()
    try:
        window.restart_as_admin()
        assert observations == [(True, True, False)]
        assert calls == [["captured folder"]]
        assert bool(closed) is started
        assert not closed or closed == [threading.get_ident()]
        assert not window._settings_dialogs and window._actions["elevate"].isEnabled()
        assert not any(worker.isRunning() for worker in window.findChildren(ElevationWorker))
    finally:
        release.set()
        fallback.cancel()
        fallback.join()
        timer.stop()


def test_native_errors_are_plain_text_and_do_not_retry(window, qapp, monkeypatch):
    calls = []

    def fail(_arguments):
        calls.append(True)
        raise OSError("<b>permission & failure</b>")

    monkeypatch.setattr(elevation, "relaunch_elevated", fail)
    dialog = ElevationDialog([], window)
    dialog.show()
    try:
        _wait(qapp, lambda: dialog.worker.wait(0) and dialog.worker.error is not None
              and dialog.status.text() == tr("elevate_failed", reason=dialog.worker.error))
        from PySide6.QtCore import Qt
        assert dialog.status.textFormat() == Qt.TextFormat.PlainText
        assert "<b>permission & failure</b>" in dialog.status.text()
        assert calls == [True] and not dialog.worker.started_copy
        dialog.reject()
    finally:
        dialog.shutdown()
        dialog.deleteLater()


def test_parent_close_waits_for_native_call_without_late_status(window, qapp, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    observations = []

    def relaunch(_arguments):
        entered.set()
        release.wait(3)
        return False

    monkeypatch.setattr(elevation, "relaunch_elevated", relaunch)
    timer = QTimer(window)
    timer.setInterval(5)

    def close_parent():
        if entered.is_set() and not observations:
            window.close()
            observations.append((window._closing, window._close_ready))
            QTimer.singleShot(50, release.set)

    timer.timeout.connect(close_parent)
    timer.start()
    fallback = threading.Timer(2, release.set)
    fallback.start()
    try:
        window.restart_as_admin()
        _wait(qapp, lambda: window._close_ready)
        assert observations == [(True, False)]
        assert window.statusBar().currentMessage() == tr("closing_workers")
    finally:
        release.set()
        fallback.cancel()
        fallback.join()
        timer.stop()


def test_busy_or_closing_windows_do_not_launch(window, monkeypatch):
    calls = []
    monkeypatch.setattr(elevation, "relaunch_elevated", lambda _args: calls.append(True) or False)
    guard = QDialog(window)
    window._path_dialogs.add(guard)
    try:
        window._update_actions()
        assert not window._actions["elevate"].isEnabled()
        window.restart_as_admin()
    finally:
        window._path_dialogs.discard(guard)
        guard.deleteLater()
    window._closing = True
    try:
        window.restart_as_admin()
    finally:
        window._closing = False
    assert not calls
