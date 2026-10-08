"""Fresh foreground scan and ordinary cleanup review for explicitly requested dated observations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
import threading
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QTimer, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QVBoxLayout

from je_file_tree.core.background import MonitorConfig, ScanAttempt
from je_file_tree.core.cleanup import CleanupGroup, find_cleanup
from je_file_tree.core.cleanup_policy import CleanupPolicy
from je_file_tree.core.node import Node
from je_file_tree.core.operations import validate_tree
from je_file_tree.core.recurring import ProposalCancelledError, RecurringProposal, proposal_status
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.recurring_settings import ProposalSettings
from je_file_tree.gui.scan_worker import ScanOutcome, wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog, after_threads

if TYPE_CHECKING:
    from je_file_tree.gui.background_monitor import BackgroundMonitor
    from je_file_tree.gui.main_window import MainWindow


@dataclass(frozen=True, slots=True)
class ReviewBinding:
    """Small GUI-captured settings sent to a worker; they never replace native source validation."""

    policy: CleanupPolicy
    config: MonitorConfig
    attempt: ScanAttempt | None


@dataclass(frozen=True, slots=True)
class RecurringReview:
    """Current actual scan nodes/reasons, bound to a dated report and GUI-only metadata check."""

    report: RecurringProposal
    root: Node
    reasons: dict[Node, CleanupGroup]
    check: Callable[[], str | None]
    store: ProposalSettings

    def matches(self, root: Node, nodes: Sequence[Node]) -> bool:
        """Reject any replaced model or node that did not come from this validated foreground scan."""
        return root is self.root and bool(nodes) and all(node in self.reasons and node.is_in(root) for node in nodes)


class ReviewWorker(QThread):
    """Validate the whole current captured/native tree and resolve bounded rows to actual current nodes."""

    def __init__(self, report: RecurringProposal, root: Node, binding: ReviewBinding, parent: QDialog) -> None:
        super().__init__(parent)
        self.report, self.root, self.binding = report, root, binding
        self.cancel = threading.Event()
        self.status: str | None = None
        self.error = ""
        self.reasons: dict[Node, CleanupGroup] = {}

    def run(self) -> None:
        """A changed/partial/canceled scan never produces a review selection."""
        try:
            binding = self.binding
            self.status = proposal_status(self.report, self.root, binding.policy, binding.config, binding.attempt,
                                          time.time(), cancel=self.cancel)
            if self.status is not None:
                return
            if validate_tree(self.root, cancel=self.cancel) is not None:
                self.status = "paths_changed"
                return
            groups = find_cleanup(self.root, policy=binding.policy, cancel=self.cancel)
            if groups is None:
                return
            wanted = {(os.path.normcase(os.path.normpath(row.path)), row.rule)
                      for row in self.report.baseline.candidates}
            self.reasons = {node: group for group in groups for node in group.nodes
                            if (os.path.normcase(os.path.normpath(node.path)), group.key) in wanted}
            if len(self.reasons) != len(wanted):
                self.status, self.reasons = "paths_changed", {}
        except ProposalCancelledError:
            self.cancel.set()
        except (OSError, ValueError, RecursionError) as error:
            self.status, self.error = "unavailable", str(error)


class ValidationDialog(WorkerDialog):
    """Joinable validation under the owning tab's source-operation guard; Cancel grants no approval."""

    def __init__(self, report: RecurringProposal, root: Node, binding: ReviewBinding, parent: MainWindow) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_recurring"))
        self.label = QLabel(tr("recurring_validating"))
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.buttons)
        self.resize(600, 180)
        self.worker = ReviewWorker(report, root, binding, self)
        self.worker.finished.connect(lambda: after_threads((self.worker,), self._finished, self))
        self.start_timer = QTimer(self)
        self.start_timer.setSingleShot(True)
        self.start_timer.timeout.connect(self.worker.start)
        self.start_timer.start(0)

    def _finished(self) -> None:
        if self.worker.cancel.is_set():
            self.reject()
        elif self.worker.status is None:
            self.accept()
        else:
            self.label.setText(tr("recurring_refused", status=tr("recurring_status_" + self.worker.status))
                               + ("\n" + self.worker.error if self.worker.error else ""))
            self.buttons.setStandardButtons(QDialogButtonBox.StandardButton.Close)

    def shutdown(self, *, wait: bool = True) -> None:
        """Cancel and join before closing, including when the owning workspace quits."""
        self.start_timer.stop()
        self.worker.cancel.set()
        if wait:
            wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: join before returning either acceptance or cancellation."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)


class RecurringFlow(QObject):
    """One explicit rescan intent, discarded on cancellation, replacement or owner close."""

    def __init__(self, monitor: BackgroundMonitor, owner: MainWindow, report: RecurringProposal) -> None:
        super().__init__(owner)
        self.monitor, self.owner, self.report = monitor, owner, report
        self.delivered = False
        self.scan = None

    def start(self) -> None:
        """Use the ordinary foreground scan/progress UI in its own tab; no timer invokes this flow."""
        self.owner.start_scan(self.report.baseline.root)
        self.scan = self.owner._worker
        if self.scan is None:
            self.deleteLater()
            return
        self.scan.succeeded.connect(self._succeeded)
        self.scan.finished.connect(self._finished)

    def _finished(self) -> None:
        if not self.delivered:
            self.deleteLater()

    def _succeeded(self, outcome: ScanOutcome) -> None:
        self.delivered = True
        after_threads((self.scan,), lambda: self._deliver(outcome), self)

    def _deliver(self, outcome: ScanOutcome) -> None:
        owner, root = self.owner, outcome.result.root
        if (owner._closing or owner._worker is not None or owner.operation_busy or outcome.partial
                or owner.results.outcome is not outcome or owner.results.tree_model.root is not root):
            self.deleteLater()
            return
        try:
            self._validate(root)
        finally:
            self.deleteLater()

    def _validate(self, root: Node) -> None:
        owner = self.owner
        binding = self.monitor.review_binding(self.report)
        if binding is None:
            return
        dialog = ValidationDialog(self.report, root, binding, owner)
        owner._path_dialogs.add(dialog)
        owner._update_actions()
        reasons = {}
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                reasons = dict(dialog.worker.reasons)
        finally:
            dialog.shutdown()
            owner._path_dialogs.discard(dialog)
            owner._update_actions()
            dialog.deleteLater()
        if not reasons or owner._closing or owner.results.tree_model.root is not root:
            return
        review = RecurringReview(self.report, root, reasons, lambda: self.monitor.report_status(self.report),
                                 ProposalSettings.capture(self.monitor.settings))
        status = review.check()
        if status is None:
            owner.move_to_trash(list(reasons), proposal=review)
        else:
            QMessageBox.warning(owner, tr("action_recurring"), tr("recurring_refused",
                                status=tr("recurring_status_" + status)))
