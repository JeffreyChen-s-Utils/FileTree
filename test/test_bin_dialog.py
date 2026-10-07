"""Only explicit two-question approvals reach a mocked native bin operation."""

import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
import pytest

from test_gui import _wait
from test_volumes import _sources
from je_file_tree.gui import bin_dialog as bins
from je_file_tree.gui.bin_dialog import BinDialog


def _dialog(qapp, monkeypatch):
    _sources(monkeypatch)
    monkeypatch.setattr(bins.sys, "platform", "win32")
    dialog = BinDialog("auto")
    _wait(qapp, lambda: not dialog.worker.isRunning())
    dialog.view.setCurrentIndex(dialog.proxy.index(0, 0))
    return dialog


@pytest.mark.parametrize("decline", (0, 1))
def test_either_declined_question_prevents_native_action(qapp, monkeypatch, decline):
    dialog = _dialog(qapp, monkeypatch)
    questions, called = [], []
    def question(_parent, _title, message, _buttons, default):
        assert default == QMessageBox.StandardButton.No
        questions.append(message)
        return QMessageBox.StandardButton.No if len(questions) - 1 == decline else QMessageBox.StandardButton.Yes
    monkeypatch.setattr(bins.QMessageBox, "question", question)
    monkeypatch.setattr(bins, "empty_windows_bin", lambda *args: called.append(args))
    try:
        dialog.empty_selected()
        assert len(questions) == decline + 1 and not called
        assert all("D:/" in message and "123 B" in message and "2" in message for message in questions)
        if decline == 1:
            assert "cannot be undone" in questions[1]
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_approved_native_operation_blocks_close_until_completion(qapp, monkeypatch):
    dialog = _dialog(qapp, monkeypatch)
    entered, release, called = threading.Event(), threading.Event(), []
    monkeypatch.setattr(bins.QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    def native(root, approved):
        called.append((root, approved.count))
        entered.set()
        assert release.wait(10)
    monkeypatch.setattr(bins, "empty_windows_bin", native)
    dialog.empty_selected()
    _wait(qapp, entered.is_set)
    assert not dialog.stop_button.isEnabled() and not dialog.close_box.isEnabled()
    assert not dialog.view.isEnabled() and not dialog.empty_button.isEnabled()
    dialog.reject()
    assert not dialog._closed
    dialog.stop()
    assert dialog._empty_worker is not None
    release.set()
    _wait(qapp, lambda: dialog._empty_worker is None and not dialog.worker.isRunning())
    assert called == [("D:/", 2)] and dialog.close_box.isEnabled()
    dialog.reject()
    dialog._empty_finished("late queued reply")
    assert dialog._closed and not dialog.worker.isRunning()
    dialog.deleteLater()


def test_native_failure_refreshes_metadata_and_displays_plain_error(qapp, monkeypatch):
    dialog = _dialog(qapp, monkeypatch)
    monkeypatch.setattr(bins.QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    def failed(*_args):
        raise OSError("<partial native failure>")
    monkeypatch.setattr(bins, "empty_windows_bin", failed)
    try:
        dialog.empty_selected()
        _wait(qapp, lambda: dialog._empty_worker is None and not dialog.worker.isRunning())
        assert "<partial native failure>" in dialog.status.text()
        assert dialog.status.textFormat() == Qt.TextFormat.PlainText
        assert dialog.model.rowCount() == 1
    finally:
        dialog.reject()
        dialog.deleteLater()
