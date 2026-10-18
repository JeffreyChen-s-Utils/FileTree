"""Message-box details are built only when opened or copied (U-20261018-80)."""

import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QTextEdit
import pytest

from je_file_tree.gui.lazy_details import PLACEHOLDER, full_details, set_lazy_details

_DETAILS = "C:\\source\\<b>literal</b>.txt\n\u2192 D:\\copy\\\u8cc7\u6599\u593e.txt"


@pytest.fixture
def box(qapp):
    calls = []
    question = QMessageBox(QMessageBox.Icon.Question, "title", "Move these entries?",
                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    question.setTextFormat(Qt.TextFormat.PlainText)
    set_lazy_details(question, lambda: calls.append(1) or _DETAILS)
    question.show()
    qapp.processEvents()
    yield question, calls
    question.done(0)
    question.deleteLater()
    qapp.processEvents()


def _details_button(question):
    return next(button for button in question.findChildren(QPushButton)
                if question.buttonRole(button) == QMessageBox.ButtonRole.ActionRole)


def test_nothing_is_built_until_the_details_are_opened_then_only_once(qapp, box):
    question, calls = box
    assert calls == [] and question.detailedText() == PLACEHOLDER
    assert not question.findChild(QTextEdit).isVisible()
    _details_button(question).click()
    qapp.processEvents()
    assert calls == [1] and question.detailedText() == _DETAILS
    assert question.findChild(QTextEdit).isVisible() and question.findChild(QTextEdit).toPlainText() == _DETAILS
    _details_button(question).click()
    _details_button(question).click()
    qapp.processEvents()
    assert calls == [1] and full_details(question) == _DETAILS


def test_the_copy_shortcut_builds_the_details_before_qt_copies_the_box(qapp, box):
    question, calls = box
    other = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a")
    QApplication.sendEvent(question, other)
    assert calls == []
    copy = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier, "\x03")
    assert copy.matches(QKeySequence.StandardKey.Copy)
    QApplication.sendEvent(question, copy)
    assert calls == [1] and question.detailedText() == _DETAILS
    if sys.platform == "win32":  # Qt copies the whole box, hidden details included, only on Windows
        assert _DETAILS.replace("\n", "") in QApplication.clipboard().text().replace("\r", "").replace("\n", "")


def test_full_details_builds_pending_details_and_reads_ordinary_ones(qapp, box):
    question, calls = box
    assert full_details(question) == _DETAILS and calls == [1]
    plain = QMessageBox()
    plain.setDetailedText("ordinary")
    assert full_details(plain) == "ordinary"
    assert full_details(QMessageBox()) == ""


def test_lazy_details_never_use_a_native_dialog_that_would_read_the_placeholder(box):
    question, _calls = box
    assert question.testOption(QMessageBox.Option.DontUseNativeDialog)
