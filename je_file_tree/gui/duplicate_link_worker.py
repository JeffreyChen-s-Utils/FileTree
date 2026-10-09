"""Owned preview/execution workers with frozen paths, durable approvals and retained partial results."""

from dataclasses import replace
import threading
import uuid

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from je_file_tree.core.duplicate_link_ops import LinkOutcome, LinkResult, execute_links
from je_file_tree.core.duplicate_links import LinkPair, LinkPlan, prepare_links
from je_file_tree.core.duplicates import DuplicateGroup
from je_file_tree.core.node import Node
from je_file_tree.core.operation_journal import OperationJournal, OperationOutcome, OperationRecord


class LinkPreviewWorker(QThread):
    """Freeze bounded explicit-keeper decisions before the GUI may review them; never mutate files."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, root: Node, groups: tuple[DuplicateGroup, ...], parent: QWidget) -> None:
        super().__init__(parent)
        self.root = root
        self.groups = tuple(replace(group, files=list(group.files), proofs=dict(group.proofs)) for group in groups)
        self.cancel = threading.Event()

    def run(self) -> None:
        """Canceled preview workers never publish late review authority."""
        try:
            plan = prepare_links(self.root, self.groups, cancel=self.cancel)
            if plan is not None and not self.cancel.is_set():
                self.ready.emit(plan)
        except (OSError, ValueError) as exc:
            if not self.cancel.is_set():
                self.failed.emit(str(exc))


class LinkOperationWorker(QThread):
    """Persist approvals before native operations and preserve actual outcomes before queued delivery."""

    ready = Signal(object)
    progressed = Signal(str)

    def __init__(self, plan: LinkPlan, journal: OperationJournal, parent: QWidget) -> None:
        super().__init__(parent)
        self.plan, self.journal = plan, journal
        self.cancel = threading.Event()
        self.result = LinkResult()
        self.journal_errors: list[str] = []
        self.error = ""
        batch = uuid.uuid4().hex
        self.records = {pair.copy: replace(OperationRecord.approved(batch, pair.copy, "duplicate_links"),
                                           source=pair.copy_path) for pair in plan.pairs}

    def run(self) -> None:
        """Approval failure prevents all replacements; audit failure cancels remaining rows."""
        if not self._append(list(self.records.values())):
            self.result.outcomes = [LinkOutcome(pair, False, "Link approval could not be recorded")
                                    for pair in self.plan.pairs]
        else:
            try:
                self.result = execute_links(self.plan, cancel=self.cancel, progress=self._progress,
                                            completed=self._completed)
            except (OSError, ValueError) as exc:
                self.error = str(exc)
                self.cancel.set()
                seen = {outcome.pair.copy for outcome in self.result.outcomes}
                for pair in self.plan.pairs:
                    if pair.copy not in seen:
                        self._completed(LinkOutcome(pair, False, "Execution interrupted: " + self.error))
        self.result.canceled = self.cancel.is_set()
        self.ready.emit(self.result)

    def _progress(self, pair: LinkPair) -> None:
        self.progressed.emit(pair.copy_path)

    def _completed(self, observed: LinkOutcome) -> None:
        self.result.outcomes.append(observed)
        status = "linked" if observed.linked else "skipped" if observed.pair.reason else "failed"
        detail = "\n".join((observed.error, *observed.retained)).strip()
        outcome = OperationOutcome(status, detail, observed.pair.keeper_path if observed.linked else None)
        if not self._append([self.records[observed.pair.copy].finished(outcome)]):
            self.cancel.set()

    def _append(self, records: list[OperationRecord]) -> bool:
        if self.journal_errors:
            return False  # A failed durable audit stops the batch; never repeat lock timeouts for skipped rows.
        try:
            self.journal.append(records)
        except (OSError, ValueError) as exc:
            self.journal_errors.append(str(exc))
            return False
        return True
