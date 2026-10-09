"""Only explicit two-question approvals reach a mocked native bin operation."""

import threading
from dataclasses import replace

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QMessageBox
import pytest

from test_gui import _wait
from test_volumes import _sources, _storage
from je_file_tree.gui import bin_dialog as bins
from je_file_tree.gui.bin_dialog import BinDialog
from je_file_tree.core.bin_empty import BinEmptyPlan, BinEmptyResult, BinScope
from je_file_tree.core.finder_bin import FinderEmptyPlan, FinderScope
from je_file_tree.core.trash_size import TrashUsage


def _dialog(qapp, monkeypatch):
    _sources(monkeypatch)
    monkeypatch.setattr(bins.sys, "platform", "win32")
    dialog = BinDialog("auto")
    _wait(qapp, lambda: not dialog.worker.isRunning())
    dialog.view.setCurrentIndex(dialog.proxy.index(0, 0))
    return dialog


def test_scope_question_uses_literal_paths_and_default_no(qapp, monkeypatch):
    text = "/owned/<b>literal</b>/files\n123 B, 2 items"
    def inspect(box):
        assert box.textFormat() == Qt.TextFormat.PlainText
        assert box.text() == text
        assert box.defaultButton() is box.button(QMessageBox.StandardButton.No)
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(bins.QMessageBox, "exec", inspect)
    assert bins.ask_bin(None, "review", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No


@pytest.mark.parametrize("decline", (0, 1))
def test_either_declined_question_prevents_native_action(qapp, monkeypatch, decline):
    dialog = _dialog(qapp, monkeypatch)
    questions, called = [], []
    def question(_parent, _title, message, _buttons, default):
        assert default == QMessageBox.StandardButton.No
        questions.append(message)
        return QMessageBox.StandardButton.No if len(questions) - 1 == decline else QMessageBox.StandardButton.Yes
    monkeypatch.setattr(bins, "ask_bin", question)
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
    monkeypatch.setattr(bins, "ask_bin", lambda *_args: QMessageBox.StandardButton.Yes)
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
    monkeypatch.setattr(bins, "ask_bin", lambda *_args: QMessageBox.StandardButton.Yes)
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


def _linux_dialog(qapp, monkeypatch):
    dialog = _dialog(qapp, monkeypatch)
    monkeypatch.setattr(bins.sys, "platform", "linux")
    scope = BinScope("/owned-volume/.Trash-123", b"fixture", (), (), 123, 2)
    plan = BinEmptyPlan("/owned-volume", 123, (scope,), TrashUsage(123, 2, True))
    monkeypatch.setattr(bins, "prepare_bin_empty", lambda _root, **_kwargs: plan)
    return dialog, plan


@pytest.mark.parametrize("decline", (0, 1, None))
def test_linux_exact_scopes_two_questions_partial_refresh(qapp, monkeypatch, decline):
    dialog, plan = _linux_dialog(qapp, monkeypatch)
    questions, called, attempted = [], [], []
    def question(_parent, _title, message, _buttons, default):
        assert default == QMessageBox.StandardButton.No
        questions.append(message)
        return QMessageBox.StandardButton.No if len(questions) - 1 == decline else QMessageBox.StandardButton.Yes
    def empty(approved):
        called.append(approved)
        return BinEmptyResult(1, ("<fixture remaining>",))
    monkeypatch.setattr(bins, "ask_bin", question)
    monkeypatch.setattr(bins, "empty_posix_bin", empty)
    dialog.emptied.connect(attempted.append)
    try:
        dialog.empty_selected()
        _wait(qapp, lambda: dialog._approval_worker is None and dialog._empty_worker is None
              and not dialog.worker.isRunning())
        assert len(questions) == (2 if decline is None else decline + 1)
        assert all("/owned-volume/.Trash-123/files" in message and "/owned-volume/.Trash-123/info" in message
                   and "123 B" in message and "2" in message for message in questions)
        assert called == ([plan] if decline is None else [])
        assert attempted == ([plan.root] if decline is None else [])
        if decline is None:
            assert "<fixture remaining>" in dialog.status.text()
            assert dialog.status.textFormat() == Qt.TextFormat.PlainText
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_linux_incomplete_plan_never_opens_confirmation(qapp, monkeypatch):
    dialog, plan = _linux_dialog(qapp, monkeypatch)
    monkeypatch.setattr(bins, "prepare_bin_empty", lambda *_args, **_kwargs: replace(
        plan, usage=TrashUsage(123, 2, False, "<fixture orphan receipt>")))
    questions = []
    monkeypatch.setattr(bins, "ask_bin", lambda *args: questions.append(args))
    try:
        dialog.empty_selected()
        _wait(qapp, lambda: dialog._approval_worker is None)
        assert not questions and "<fixture orphan receipt>" in dialog.status.text()
        assert dialog.status.textFormat() == Qt.TextFormat.PlainText
    finally:
        dialog.reject()
        dialog.deleteLater()


@pytest.mark.parametrize("close", (False, True))
def test_linux_stop_or_close_joins_survey_without_late_approval(qapp, monkeypatch, close):
    dialog, plan = _linux_dialog(qapp, monkeypatch)
    entered, finished, questions = threading.Event(), threading.Event(), []
    def prepare(_root, *, cancel):
        entered.set()
        assert cancel.wait(10)
        finished.set()
        return plan
    monkeypatch.setattr(bins, "prepare_bin_empty", prepare)
    monkeypatch.setattr(bins, "ask_bin", lambda *args: questions.append(args))
    dialog.empty_selected()
    _wait(qapp, entered.is_set)
    dialog.reject() if close else dialog.stop()
    _wait(qapp, finished.is_set)
    _wait(qapp, lambda: not dialog._finish_waiting)
    assert finished.is_set() and not questions
    if not close:
        assert dialog._approval_worker is None and dialog.view.isEnabled()
        dialog.reject()
        _wait(qapp, lambda: not dialog._finish_waiting)
    dialog.deleteLater()


@pytest.mark.parametrize("decline", (0, 1, None))
def test_finder_confirmation_is_global_and_rechecks_with_native_provider(qapp, monkeypatch, decline):
    dialog = _dialog(qapp, monkeypatch)
    monkeypatch.setattr(bins.sys, "platform", "darwin")
    scope = FinderScope("/owned-home/.Trash", b"fixture", (), 123, 2)
    plan = FinderEmptyPlan(("/", "/owned-volume"), 123, (scope,), TrashUsage(123, 2, True))
    monkeypatch.setattr(bins, "prepare_finder_empty", lambda _provider, **_kwargs: plan)
    questions, called = [], []
    def question(_parent, _title, text, _buttons, default):
        assert default == QMessageBox.StandardButton.No
        assert "all mounted volumes" in _title
        questions.append(text)
        return QMessageBox.StandardButton.No if len(questions) - 1 == decline else QMessageBox.StandardButton.Yes
    def empty(approved, provider):
        called.append(approved)
        assert provider is bins.finder_roots
        raise OSError("<fixture automation denied>")
    monkeypatch.setattr(bins, "ask_bin", question)
    monkeypatch.setattr(bins, "empty_finder_bin", empty)
    try:
        dialog.view.setCurrentIndex(QModelIndex())
        dialog.empty_selected()
        _wait(qapp, lambda: dialog._approval_worker is None and dialog._empty_worker is None
              and not dialog.worker.isRunning())
        assert len(questions) == (2 if decline is None else decline + 1)
        assert all("ALL mounted volumes" in text and scope.directory in text and "/owned-volume" in text
                   and "123 B" in text for text in questions)
        assert called == ([plan] if decline is None else [])
        if decline is None:
            assert "<fixture automation denied>" in dialog.status.text()
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_finder_mount_provider_refuses_unavailable_or_omitted_roots(monkeypatch):
    _sources(monkeypatch, [_storage("/"), _storage("/owned-volume")])
    assert bins.finder_roots() == ("/", "/owned-volume")
    _sources(monkeypatch, [_storage("/"), _storage("/unready", ready=False)])
    with pytest.raises(ValueError, match="unavailable"):
        bins.finder_roots()
    _sources(monkeypatch, [_storage("/"), _storage("/owned-volume")])
    monkeypatch.setattr(bins, "MAX_ROOTS", 1)
    with pytest.raises(ValueError, match="complete"):
        bins.finder_roots()
