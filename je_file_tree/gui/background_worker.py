"""Joinable OS capacity reads and gentle scheduled history scans, with no source mutations."""

from __future__ import annotations

from dataclasses import replace
import stat
import threading
import time

from PySide6.QtCore import QObject, QStorageInfo, QThread

from je_file_tree.core.background import CapacityObservation, MAX_VOLUMES, ScanAttempt
from je_file_tree.core.cleanup_policy import CleanupPolicy
from je_file_tree.core.history import HistoryCancelledError, HistoryEntry, ScanHistory, load_history, load_recurring
from je_file_tree.core.recurring import (
    ProposalCancelledError, ProposalContext, RecurringProposal, policy_version, prepare,
)
from je_file_tree.core.scanner import ScanCancelledError, ScanOptions, ScanResult, scan
from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot


class CapacityWorker(QThread):
    """Copy bounded OS capacity on the worker; never query bins or traverse scanned sources."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.cancel = threading.Event()
        self.rows: tuple[CapacityObservation, ...] = ()
        self.error = ""

    def run(self) -> None:
        """Keep unavailable capacity unknown and retain errors until the owner joins."""
        rows = []
        try:
            for storage in QStorageInfo.mountedVolumes():
                if self.cancel.is_set():
                    return
                storage.refresh()
                if not storage.isValid() or not storage.isReady() or storage.bytesTotal() <= 0:
                    continue
                if len(rows) >= MAX_VOLUMES:
                    raise ValueError("Too many mounted background capacity scopes")
                available = storage.bytesAvailable()
                rows.append(CapacityObservation(storage.rootPath(), storage.bytesTotal(),
                                                available if available >= 0 else None))
            if not self.cancel.is_set():
                self.rows = tuple(rows)
        except (OSError, ValueError) as error:
            self.error = str(error)


class ScheduledWorker(QThread):
    """Scan one explicitly selected root gently and save ordinary bounded local history."""

    def __init__(self, root: str, options: ScanOptions, history: ScanHistory, parent: QObject, *,
                 proposal_context: tuple[ScanAttempt, int] | None = None, policy: CleanupPolicy | None = None) -> None:
        super().__init__(parent)
        self.root, self.history = root, history
        self.options = replace(options, gentle=True, workers=1)
        self.cancel = threading.Event()
        self.result: ScanResult | None = None
        self.entry: HistoryEntry | None = None
        self.state, self.error = "claimed", ""
        self.proposal_context, self.policy = proposal_context, policy or CleanupPolicy()
        self.proposal: RecurringProposal | None = None
        self.proposal_error = ""

    def run(self) -> None:
        """Retain canceled partial results/errors; only an actual saved history entry marks completion."""
        try:
            info = unpack_snapshot(stat_snapshot(self.root))
            if info.is_link or info.attributes & 0x400 or not stat.S_ISDIR(info.mode):
                raise ValueError("Scheduled scan requires an ordinary selected directory")
            self.result = scan(self.root, options=self.options, cancel=self.cancel)
            if self.proposal_context is not None:
                self._prepare_proposal()
            self.entry = self.history.save(self.result.root, cancel=self.cancel,
                                           baseline=self.proposal.baseline if self.proposal is not None else None)
            self.state = "complete"
        except ScanCancelledError as error:
            self.result, self.state = error.partial, "canceled"
        except (HistoryCancelledError, ProposalCancelledError):
            self.state = "canceled"
        except (OSError, ValueError, RecursionError) as error:
            self.state, self.error = "failed", str(error)

    def _prepare_proposal(self) -> None:
        try:
            read = self.history.read(self.root, limit=1, cancel=self.cancel)
            if read.invalid:
                raise ValueError("Invalid history metadata; recurring comparison is unavailable")
            previous, saved = None, None
            if read.entries:
                entry = read.entries[-1]
                previous = load_recurring(entry)
                if (previous is not None and previous.inventory_complete and not entry.incomplete
                        and previous.policy == policy_version(self.policy)):
                    saved = load_history(entry, cancel=self.cancel)
            attempt, interval = self.proposal_context
            context = ProposalContext(attempt, interval, time.time())
            self.proposal = prepare(self.result.root, self.policy, context, previous=previous,
                                    saved=saved, cancel=self.cancel)
        except (OSError, ValueError, RecursionError) as error:
            self.proposal_error = str(error)
