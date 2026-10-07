"""Validate and move an approved batch without blocking Qt's event loop."""

from __future__ import annotations

import threading
import uuid

from PySide6.QtCore import QObject, QThread, Signal

from je_file_tree.core.node import Node
from je_file_tree.core.lock_holders import find_holders
from je_file_tree.core.operations import move_batch
from je_file_tree.core.operations import MoveReceipt, MoveResult
from je_file_tree.core.operation_journal import JournalApproval, OperationOutcome, OperationRecord
from je_file_tree.core.duplicates import DuplicateGroup
from je_file_tree.core.duplicate_decisions import check_group
from je_file_tree.core.protected import Protection
from je_file_tree.gui import file_actions


class TrashWorker(QThread):
    """Emit one MoveResult after a confirmed batch; cancellation is checked between entries."""

    done = Signal(object)

    def __init__(self, root: Node, nodes: list[Node], places: list[Protection],
                 approvals: dict[Node, Protection | None], parent: QObject | None = None, *,
                 decisions: list[DuplicateGroup] | None = None, audit: JournalApproval | None = None) -> None:
        super().__init__(parent)
        self._root = root
        self._nodes = nodes
        self._places = places
        self._approvals = approvals
        self._cancel = threading.Event()
        self._decisions = decisions or []
        self._audit = _AuditBatch(audit, self._cancel)

    def cancel(self) -> None:
        """Stop validation and skip every remaining entry."""
        self._cancel.set()

    def run(self) -> None:
        """Thread body; the GUI changes its model only after receiving the result."""
        if self._audit.begin(self._nodes):
            result = self._move_checked()
            self._audit.finish(result)
        else:
            result = MoveResult(skipped=[(node, "journal") for node in self._nodes],
                                parents=[node.parent for node in self._nodes if node.parent is not None])
        result.journal_errors.extend(self._audit.errors)
        for node in result.failed:
            if self._cancel.is_set():
                break
            result.holders[node] = find_holders(node, cancel=self._cancel)
        self.done.emit(result)

    def _move_checked(self) -> MoveResult:
        remaining = set(self._nodes)
        result = MoveResult()
        for group in self._decisions:
            selected = [node for node in group.files if node in remaining]
            if not selected:
                continue
            reason = ("duplicate_keep" if group.kept in remaining else
                      check_group(group, self._root, places=self._places, cancel=self._cancel, rehash=True))
            if reason is not None:
                result.skipped.extend((node, reason) for node in selected)
                result.parents.extend(node.parent for node in selected if node.parent is not None)
            else:
                _merge(result, self._move(selected))
            remaining.difference_update(selected)
        _merge(result, self._move([node for node in self._nodes if node in remaining]))
        return result

    def _move(self, nodes: list[Node]) -> MoveResult:
        return move_batch(self._root, nodes, self._audit.move, places=self._places,
                          approved=self._approvals, cancel=self._cancel)


def _merge(target: MoveResult, source: MoveResult) -> None:
    target.moved.extend(source.moved)
    target.skipped.extend(source.skipped)
    target.failed.extend(source.failed)
    target.parents.extend(node for node in source.parents if node not in target.parents)
    target.destinations.update(source.destinations)


class _AuditBatch:
    def __init__(self, approval: JournalApproval | None, cancel: threading.Event) -> None:
        self.approval, self.cancel = approval, cancel
        self.events: dict[str, OperationRecord] = {}
        self.recorded: set[str] = set()
        self.errors: list[str] = []

    def begin(self, nodes: list[Node]) -> bool:
        if self.approval is None:
            return True
        batch = uuid.uuid4().hex
        self.events = {node.path: OperationRecord.approved(batch, node, self.approval.reasons.get(node, "manual"))
                       for node in nodes}
        return self._append(list(self.events.values()))

    def move(self, path: str) -> MoveReceipt:
        try:
            raw = file_actions.trash_receipt(path)
        except OSError:
            raw = False
        receipt = raw if isinstance(raw, MoveReceipt) else MoveReceipt(bool(raw))
        if self.approval is not None:
            outcome = OperationOutcome("moved" if receipt.success else "failed", destination=receipt.destination)
            if self._append([self.events[path].finished(outcome)]):
                self.recorded.add(path)
            else:
                self.cancel.set()  # Preserve the observed result, but stop any remaining moves.
        return receipt

    def finish(self, result: MoveResult) -> None:
        if self.approval is None:
            return
        outcomes = {node.path: OperationOutcome("moved", destination=result.destinations.get(node))
                    for node in result.moved}
        outcomes.update((node.path, OperationOutcome("failed")) for node in result.failed)
        outcomes.update((node.path, OperationOutcome("skipped", reason)) for node, reason in result.skipped)
        pending = [record.finished(outcomes[path]) for path, record in self.events.items()
                   if path not in self.recorded and path in outcomes]
        self._append(pending)

    def _append(self, records: list[OperationRecord]) -> bool:
        try:
            self.approval.journal.append(records)
        except (OSError, ValueError) as error:
            self.errors.append(str(error))
            return False
        return True
