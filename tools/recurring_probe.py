"""Native owned-fixture rescan/review proof, ending at a real No confirmation without source moves."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import hashlib
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from je_file_tree.gui.cleanup_review import CleanupReview
from je_file_tree.gui.recurring_dialog import RecurringDialog
from je_file_tree.gui.recurring_review import ValidationDialog
from je_file_tree.gui.workspace import ScanWorkspace


def _proof(source: Path) -> dict:
    return {path.name: (path.stat().st_dev, path.stat().st_ino, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in source.glob("*.dmp")}


@contextmanager
def _qt_dialogs(app: QApplication) -> Iterator[None]:
    """Keep owned confirmation controls in Qt's native-rendered widgets and restore the process setting."""
    attribute = Qt.ApplicationAttribute.AA_DontUseNativeDialogs
    original = app.testAttribute(attribute)
    app.setAttribute(attribute, True)
    try:
        yield
    finally:
        app.setAttribute(attribute, original)


class _ReviewProbe(QObject):
    def __init__(self, app: QApplication, workspace: ScanWorkspace, count: int, evidence: Path) -> None:
        super().__init__(workspace)
        self.app, self.workspace, self.original = app, workspace, workspace.current
        self.count, self.evidence = count, evidence
        self.state = {"queue": False, "confirmation_canceled": False, "error": ""}
        self.request, self.response, self.watchdog = (QTimer(self) for _ in range(3))
        self.request.timeout.connect(self._choose)
        self.response.timeout.connect(self._respond)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self._timeout)
        app.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - native QObject override
        if (isinstance(obj, QDialog) and obj.parent() in self.workspace.operations.windows
                and event.type() == QEvent.Type.Polish):
            obj.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        return False

    def _choose(self) -> None:
        for dialog in self.app.topLevelWidgets():
            if isinstance(dialog, RecurringDialog) and dialog.parent() is self.original and dialog.isVisible():
                self.request.stop()
                if not dialog.review.isEnabled():
                    self.state["error"] = "Native proposal review was unavailable"
                    dialog.reject()
                else:
                    dialog.review.click()

    def _respond(self) -> None:
        owner = self.workspace.current
        if owner is self.original:
            return
        for dialog in self.app.topLevelWidgets():
            if dialog.parent() is not owner or not dialog.isVisible():
                continue
            if isinstance(dialog, CleanupReview):
                self._queue(dialog)
            elif isinstance(dialog, QMessageBox):
                self._confirmation(dialog)
            elif isinstance(dialog, ValidationDialog) and dialog.worker.status is not None:
                self.state["error"] = "Native source validation refused: " + dialog.worker.status
                dialog.reject()

    def _queue(self, dialog: CleanupReview) -> None:
        if not self.state["queue"]:
            if dialog.model.rowCount() != self.count or dialog.model.checked or not self.workspace.operations.busy:
                self.state["error"] = "Native queue selection/ownership failed"
                dialog.reject()
                return
            self.state["queue"] = True
            dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if button.isEnabled():
            if dialog.summary.height() < dialog.summary.heightForWidth(dialog.summary.width()):
                self.state["error"] = "Native review recovery summary was clipped"
                dialog.reject()
                return
            if not dialog.grab().save(str(self.evidence / "recurring-review-zh-TW.png")):
                self.state["error"] = "Native review capture failed"
                dialog.reject()
            else:
                button.click()

    def _confirmation(self, dialog: QMessageBox) -> None:
        button = dialog.button(QMessageBox.StandardButton.No)
        if button is not None and self.state["queue"]:
            self.state["confirmation_canceled"] = True
            button.click()
        else:
            self.state["error"] = "Native review reported an unexpected confirmation/error: " + dialog.text()
            dialog.reject()

    def _timeout(self) -> None:
        self.state["error"] = "Native review timed out"
        for dialog in self.app.topLevelWidgets():
            if isinstance(dialog, QDialog) and dialog.parent() in self.workspace.operations.windows:
                dialog.reject()

    def shutdown(self) -> None:
        self.request.stop()
        self.response.stop()
        self.watchdog.stop()
        self.app.removeEventFilter(self)
        self.deleteLater()


def validate_review(app: QApplication, workspace: ScanWorkspace, source: Path, evidence: Path,
                    pump: Callable[[QApplication, Callable[[], bool]], None]) -> dict:
    """Exercise actual Qt review/No on the native platform; OS-native alert interaction stays unverified."""
    before = _proof(source)
    with _qt_dialogs(app):
        probe = _ReviewProbe(app, workspace, len(before), evidence)
        try:
            probe.request.start(20)
            probe.response.start(20)
            probe.watchdog.start(30000)
            workspace.background.show_proposals()
            state = probe.state
            pump(app, lambda: bool(state["error"]) or state["confirmation_canceled"] and not workspace.operations.busy)
            if (state["error"] or not state["queue"] or _proof(source) != before
                    or workspace.current._trash_worker is not None):
                raise RuntimeError(state["error"] or "Native review altered source or dispatched a move")
            return {"fresh_foreground_scan": True, "native_review_queue": True, "manual_selection_required": True,
                    "confirmation_canceled": True, "source_preserved": True, "native_trash_move": False,
                    "wrapped_summary_visible": True, "confirmation_backend": "qt_widget",
                    "os_native_alert_verified": False}
        finally:
            probe.shutdown()
