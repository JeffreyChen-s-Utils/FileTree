"""Cleanup approvals display captured names literally and never turn a refusal into a move."""

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core.protected import PROGRAMS, Protection
from je_file_tree.core.scanner import scan
from je_file_tree.gui import file_actions, scan_worker, trash_worker
from je_file_tree.gui import main_window
from je_file_tree.gui.entry_move_prompt import confirm_entry_move


@pytest.fixture
def observed_prompts(qapp, monkeypatch):
    monkeypatch.setattr(main_window, "confirm_entry_move", confirm_entry_move)
    captured = []
    timer = QTimer()
    def answer():
        dialog = QApplication.activeModalWidget()
        if dialog is None:
            return
        if not isinstance(dialog, QMessageBox):
            captured.append({"unexpected": type(dialog).__name__})
            if isinstance(dialog, QDialog):
                dialog.reject()
            return
        captured.append({"text": dialog.text(), "format": dialog.textFormat(), "icon": dialog.icon(),
                         "buttons": dialog.standardButtons(),
                         "default": dialog.standardButton(dialog.defaultButton())})
        button = (QMessageBox.StandardButton.Yes if dialog.icon() == QMessageBox.Icon.Warning else
                  QMessageBox.StandardButton.No)
        dialog.button(button).click()
    timer.timeout.connect(answer)
    timer.start(1)
    yield captured
    timer.stop()


@pytest.mark.parametrize("kind", ["single", "bulk", "protected"])
def test_move_approval_preserves_literal_names_and_all_source_gates(
        window, qapp, sample_tree, monkeypatch, observed_prompts, kind):
    window.results.show_outcome(scan_worker.analyse(scan(sample_tree)))
    root = window.results.tree_model.root
    original = {name: (sample_tree / name).read_bytes() for name in ("big.bin", "notes.txt")}
    chosen = [next(node for node in root.children if node.name == "big.bin")]
    chosen[0].name = "<b>literal.txt"
    if kind == "bulk":
        chosen.append(next(node for node in root.children if node.name == "notes.txt"))
        chosen[1].name = "<i>second & tab\tline\n.txt"
    window._protected = [Protection(root.path, PROGRAMS)] if kind == "protected" else []
    monkeypatch.setattr(window.results.cleanup, "reasons_for", lambda _nodes: {})
    def forbidden(*_args, **_kwargs):
        pytest.fail("a declined approval dispatched a source operation")
    monkeypatch.setattr(file_actions, "trash_receipt", forbidden)
    monkeypatch.setattr(trash_worker.TrashWorker, "start", forbidden)

    window.move_to_trash(chosen)

    assert len(observed_prompts) == (2 if kind == "protected" else 1)
    assert not any("unexpected" in prompt for prompt in observed_prompts)
    for prompt in observed_prompts:
        assert prompt["format"] == Qt.TextFormat.PlainText
        assert prompt["buttons"] == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        for node in chosen:
            assert node.name in prompt["text"]
    final = observed_prompts[-1]
    assert final["text"] == window._trash_question(chosen)
    assert final["icon"] == QMessageBox.Icon.Question
    assert final["default"] == QMessageBox.StandardButton.NoButton
    if kind == "protected":
        assert observed_prompts[0]["icon"] == QMessageBox.Icon.Warning
        assert observed_prompts[0]["default"] == QMessageBox.StandardButton.No
        assert chosen[0].path in observed_prompts[0]["text"]
    assert window._worker is None and window._trash_worker is None
    assert not window._path_dialogs
    assert {name: (sample_tree / name).read_bytes() for name in original} == original


@pytest.mark.parametrize("protected", [False, True])
@pytest.mark.parametrize("dismissal", ["yes", "no", "return", "escape", "close"])
def test_literal_presenter_preserves_static_reply_default_and_modality(window, qapp, protected, dismissal):
    observations = []
    for literal in (False, True):
        expired = []
        watchdog = QTimer()
        watchdog.setSingleShot(True)
        def abort(expired=expired):
            expired.append(True)
            QApplication.activeModalWidget().reject()
        watchdog.timeout.connect(abort)
        watchdog.start(2000)
        def answer():
            dialog = QApplication.activeModalWidget()
            observations.append((dialog.standardButtons(), dialog.standardButton(dialog.defaultButton()),
                                 dialog.windowModality()))
            if dismissal == "escape":
                QTest.keyClick(dialog, Qt.Key.Key_Escape)
            elif dismissal == "return":
                QTest.keyClick(dialog, Qt.Key.Key_Return)
            elif dismissal == "close":
                dialog.close()
            else:
                button = QMessageBox.StandardButton.Yes if dismissal == "yes" else QMessageBox.StandardButton.No
                dialog.button(button).click()
        QTimer.singleShot(1, answer)
        if literal:
            result = confirm_entry_move(window, "Captured approval", "Captured plain text", protected=protected)
        elif protected:
            result = QMessageBox.warning(window, "Captured approval", "Captured plain text",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
        else:
            result = QMessageBox.question(window, "Captured approval", "Captured plain text")
        watchdog.stop()
        assert not expired, "a presentation test did not dismiss its actual Qt confirmation"
        approved = dismissal == "yes" or dismissal == "return" and not protected
        assert result == (QMessageBox.StandardButton.Yes if approved else QMessageBox.StandardButton.No)
        qapp.processEvents()
    assert observations[0] == observations[1]
