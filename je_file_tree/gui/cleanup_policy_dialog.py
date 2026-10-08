"""Edit declarative clean-up policy and preview its effect without filesystem actions."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from je_file_tree.core.cleanup import DETAILS, find_cleanup
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting, load_policy
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui.cleanup_text import explanation
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog

_IMPORT_LIMIT = 256_000


class PolicyPreviewWorker(QThread):
    """Compare two policies over one tree, sharing its coverage survey and cancellation flag."""

    ready = Signal(object)

    def __init__(self, root: Node, before: CleanupPolicy, after: CleanupPolicy, parent: QWidget) -> None:
        super().__init__(parent)
        self._root, self._before, self._after = root, before, after
        self._cancel = threading.Event()

    def stop(self) -> None:
        """Cancel both candidate walks; stopped previews never authorize Save."""
        self._cancel.set()

    def run(self) -> None:
        """Emit counts and logical bytes added/removed relative to the previous policy."""
        coverage = coverage_of(self._root)
        before = find_cleanup(self._root, policy=self._before, coverage=coverage, cancel=self._cancel)
        after = find_cleanup(self._root, policy=self._after, coverage=coverage, cancel=self._cancel)
        if before is None or after is None or self._cancel.is_set():
            return
        old = {node for group in before for node in group.nodes}
        new = {node for group in after for node in group.nodes}
        added, removed = new - old, old - new
        self.ready.emit((len(added), sum(node.size for node in added), len(removed),
                         sum(node.size for node in removed), coverage.complete))


class CleanupPolicyDialog(WorkerDialog):
    """A policy editor whose Save button requires a current read-only preview."""

    def __init__(self, policy: CleanupPolicy, root: Node | None, unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_cleanup_policy"))
        self.resize(780, 650)
        self._before, self._root, self._unit = policy, root, unit
        self._current: PolicyPreviewWorker | None = None
        self._running: set[PolicyPreviewWorker] = set()
        self._previewed: CleanupPolicy | None = None
        self.table = QTableWidget(len(DETAILS), 3)
        self.table.setHorizontalHeaderLabels([tr("policy_enabled"), tr("review_rule"), tr("policy_age")])
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 470)
        self.table.setColumnWidth(2, 150)
        self._controls: dict[str, tuple[QCheckBox, QSpinBox]] = {}
        self.exclusions = QPlainTextEdit()
        self.exclusions.setMaximumHeight(100)
        self.preview_status = QLabel(tr("policy_preview_needed"))
        self.preview_status.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.preview_button = QPushButton(tr("policy_preview"))
        self.preview_button.clicked.connect(self.preview)
        self.import_button = QPushButton(tr("policy_import"))
        self.import_button.clicked.connect(self._import)
        bar = QHBoxLayout()
        bar.addWidget(self.import_button)
        bar.addWidget(self.preview_button)
        bar.addStretch(1)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("policy_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(self.table, 1)
        layout.addWidget(QLabel(tr("policy_exclusions")))
        layout.addWidget(self.exclusions)
        layout.addLayout(bar)
        layout.addWidget(self.preview_status)
        layout.addWidget(self.buttons)
        self._build_rows()
        self._load(policy)
        self.exclusions.textChanged.connect(self._changed)
        self._changed()

    def _build_rows(self) -> None:
        for row, key in enumerate(DETAILS):
            check, age = QCheckBox(), QSpinBox()
            age.setRange(0, 36500)
            age.setAccessibleName(tr("policy_age_for", rule=tr(f"cleanup_{key}")))
            check.setAccessibleName(tr("policy_enabled_for", rule=tr(f"cleanup_{key}")))
            item = QTableWidgetItem(tr(f"cleanup_{key}"))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(explanation(key))
            self.table.setCellWidget(row, 0, check)
            self.table.setItem(row, 1, item)
            self.table.setCellWidget(row, 2, age)
            self._controls[key] = check, age
            check.toggled.connect(self._changed)
            age.valueChanged.connect(self._changed)

    def _load(self, policy: CleanupPolicy) -> None:
        for key, (check, age) in self._controls.items():
            setting = policy.setting(key)
            check.setChecked(setting.enabled)
            age.setValue(setting.minimum_age)
        self.exclusions.setPlainText("\n".join(policy.exclusions))

    def policy(self) -> CleanupPolicy:
        """Validate every current control, including absolute path/name exclusions."""
        settings = tuple(RuleSetting(key, check.isChecked(), age.value())
                         for key, (check, age) in self._controls.items())
        paths = tuple(line.strip() for line in self.exclusions.toPlainText().splitlines() if line.strip())
        return CleanupPolicy(settings, paths)

    def _changed(self) -> None:
        if self._current is not None:
            self._current.stop()
        self._current = None
        self._previewed = None
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
        self.preview_status.setText(tr("policy_preview_needed"))

    def preview(self) -> None:
        """Preview the editor snapshot on a worker; changed settings discard older replies."""
        self._changed()
        try:
            policy = self.policy()
        except ValueError:
            self.preview_status.setText(tr("policy_invalid"))
            return
        if self._root is None:
            self._previewed = policy
            self.preview_status.setText(tr("policy_no_scan"))
            self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(True)
            return
        worker = PolicyPreviewWorker(self._root, self._before, policy, self)
        self._current = worker
        self._running.add(worker)
        worker.ready.connect(lambda value: self._shown(worker, policy, value))
        worker.finished.connect(lambda: self._running.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self.preview_status.setText(tr("policy_preview_running"))
        worker.start()

    def _shown(self, worker: PolicyPreviewWorker, policy: CleanupPolicy, value: tuple) -> None:
        if self._current is None or worker is not self._current:
            return
        self._current = None
        self._previewed = policy
        added, size, removed, removed_size, complete = value
        text = tr("policy_preview_result", added=format_count(added), size=format_size(size, self._unit),
                  removed=format_count(removed), removed_size=format_size(removed_size, self._unit))
        if not complete:
            text += " " + tr("policy_preview_partial")
        self.preview_status.setText(text)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(True)

    def accept(self) -> None:
        """Require an unchanged, validated preview even for programmatic acceptance."""
        try:
            current = self.policy()
        except ValueError:
            self.preview_status.setText(tr("policy_invalid"))
            return
        if current == self._previewed:
            super().accept()

    def done(self, result: int) -> None:
        """Join every preview thread before closing the editor."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)

    def shutdown(self, *, wait: bool = True) -> None:
        """Cancel and join previews, including replaced workers."""
        self._current = None
        for worker in self._running.copy():
            worker.stop()
            if wait:
                wait_for(worker)

    def _import(self) -> None:
        file, _ = QFileDialog.getOpenFileName(self, tr("policy_import"), "", tr("json_filter"))
        if not file:
            return
        try:
            with Path(file).open(encoding="utf-8") as stream:
                policy = load_policy(stream.read(_IMPORT_LIMIT + 1))
        except (OSError, ValueError, RecursionError):
            QMessageBox.warning(self, tr("policy_import"), tr("policy_invalid"))
            return
        self._load(policy)
        self._changed()
