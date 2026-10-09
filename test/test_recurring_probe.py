"""Owned GUI probe confirmations use real No buttons and restore unrelated process dialog settings."""

from types import SimpleNamespace

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMessageBox, QWidget
import pytest

from tools import recurring_probe as probe


@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize("fails", [False, True])
def test_owned_dialog_backend_restores_process_setting_on_success_and_failure(qapp, initial, fails):
    attribute = Qt.ApplicationAttribute.AA_DontUseNativeDialogs
    original = qapp.testAttribute(attribute)
    qapp.setAttribute(attribute, initial)
    try:
        def session():
            with probe._qt_dialogs(qapp):
                assert qapp.testAttribute(attribute)
                if fails:
                    raise RuntimeError("owned probe refusal")

        if fails:
            with pytest.raises(RuntimeError, match="probe refusal"):
                session()
        else:
            session()
        assert qapp.testAttribute(attribute) is initial
    finally:
        qapp.setAttribute(attribute, original)


def test_owned_probe_clicks_actual_no_button_without_substituting_question_result(qapp, tmp_path):
    workspace = QWidget()
    owner = QWidget(workspace)
    workspace.current = owner
    workspace.operations = SimpleNamespace(windows=(owner,))
    review = probe._ReviewProbe(qapp, workspace, 1, tmp_path)
    review.state["queue"] = True
    response, deadline = QTimer(workspace), QTimer(workspace)

    def respond():
        for widget in qapp.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.parent() is owner and widget.isVisible():
                review._confirmation(widget)

    def timeout():
        for widget in qapp.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.parent() is owner:
                widget.reject()

    response.timeout.connect(respond)
    deadline.setSingleShot(True)
    deadline.timeout.connect(timeout)
    try:
        with probe._qt_dialogs(qapp):
            response.start(10)
            deadline.start(5000)
            answer = QMessageBox.question(owner, "Owned confirmation", "Preserve the owned sources?")
        assert answer == QMessageBox.StandardButton.No
        assert review.state["confirmation_canceled"] and not review.state["error"]
    finally:
        response.stop()
        deadline.stop()
        review.shutdown()
        workspace.close()
        workspace.deleteLater()
