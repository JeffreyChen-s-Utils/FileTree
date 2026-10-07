"""Frozen captured Trash plans and an owned, audited inverse-operation worker."""

from dataclasses import dataclass, field, replace
import os
import sys
import threading
import time
import uuid

from PySide6.QtCore import QObject, QThread, Signal

from je_file_tree.core.mounts import mount_points
from je_file_tree.core.node import Node
from je_file_tree.core.operation_journal import OperationJournal, OperationOutcome, OperationRecord
from je_file_tree.core.trash_restore import RestorePlan, RestoreResult, TrashOrigin, prepare_restore, restore
from je_file_tree.core.windows_restore import WindowsRestorePlan, prepare_windows_restore, restore_windows


@dataclass(frozen=True, slots=True)
class UndoEntry:
    """One complete captured native plan and its original approval, independent of detached scan nodes."""

    plan: RestorePlan | WindowsRestorePlan
    record: OperationRecord
    parent: Node | None


@dataclass(slots=True)
class UndoBatch:
    """Observed per-item restoration and durable-audit failures, retained before queued signal delivery."""

    results: list[RestoreResult] = field(default_factory=list)
    journal_errors: list[str] = field(default_factory=list)


def prepare_undo(origin: TrashOrigin, actual: str | None,
                 cancel: threading.Event) -> RestorePlan | WindowsRestorePlan:
    """Prepare only the platform's recognized exact current-user destination, without restoring it."""
    if os.path.lexists(origin.path):
        raise ValueError("Undo original path is occupied, including any copy redirect")
    if os.name == "nt":
        return prepare_windows_restore(origin, actual=actual, cancel=cancel)
    if not sys.platform.startswith("linux") or actual is None:
        raise ValueError("Native Undo is unavailable for this platform or missing Trash destination")
    volumes = [path for path in mount_points() if os.path.commonpath((origin.path, path)) == path]
    if not volumes:
        raise ValueError("Undo source has no recognized mounted volume")
    return prepare_restore(origin, actual, max(volumes, key=len), cancel=cancel)


class UndoWorker(QThread):
    """Join native calls; cancel between items and never infer success from a Shell return alone."""

    done = Signal(object)

    def __init__(self, entries: tuple[UndoEntry, ...], journal: OperationJournal, deadline: float,
                 window: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.entries, self.journal, self.deadline, self.window = entries, journal, deadline, window
        self.cancel_event = threading.Event()
        self.result: UndoBatch | None = None

    def cancel(self) -> None:
        """Skip unstarted entries; a running native restoration remains joined."""
        self.cancel_event.set()

    def run(self) -> None:
        """Persist new inverse approvals before restoring; keep original Trash audit events intact."""
        result = UndoBatch()
        batch = uuid.uuid4().hex
        records = [replace(entry.record, id=uuid.uuid4().hex, batch=batch, reason="undo")
                   .finished(OperationOutcome("approved")) for entry in self.entries]
        if time.monotonic() > self.deadline or self.cancel_event.is_set():
            result.results = [RestoreResult(False, entry.plan.origin.path, entry.plan.trashed,
                                            "Undo expired or canceled before restoration") for entry in self.entries]
        elif self._append(records, result):
            for entry, record in zip(self.entries, records, strict=True):
                observed = self._restore(entry)
                result.results.append(observed)
                outcome = OperationOutcome("restored" if observed.restored else "failed", observed.error,
                                           observed.source if observed.restored else observed.trashed)
                if not self._append([record.finished(outcome)], result):
                    self.cancel_event.set()
        else:
            result.results = [RestoreResult(False, entry.plan.origin.path, entry.plan.trashed,
                                            "Undo approval could not be recorded") for entry in self.entries]
        self.result = result
        self.done.emit(result)

    def _restore(self, entry: UndoEntry) -> RestoreResult:
        plan = entry.plan
        if self.cancel_event.is_set():
            return RestoreResult(False, plan.origin.path, plan.trashed, "Undo canceled before restoration")
        if isinstance(plan, WindowsRestorePlan):
            return restore_windows(plan, window=self.window, cancel=self.cancel_event)
        return restore(plan, cancel=self.cancel_event)

    def _append(self, records: list[OperationRecord], result: UndoBatch) -> bool:
        try:
            self.journal.append(records)
        except (OSError, ValueError) as exc:
            result.journal_errors.append(str(exc))
            return False
        return True
