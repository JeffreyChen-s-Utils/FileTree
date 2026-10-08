"""Joinable OS capacity reads and gentle scheduled history scans, with no source mutations."""

from __future__ import annotations

from dataclasses import replace
import stat
import threading

from PySide6.QtCore import QObject, QStorageInfo, QThread

from je_file_tree.core.background import CapacityObservation, MAX_VOLUMES
from je_file_tree.core.history import HistoryCancelledError, HistoryEntry, ScanHistory
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

    def __init__(self, root: str, options: ScanOptions, history: ScanHistory, parent: QObject) -> None:
        super().__init__(parent)
        self.root, self.history = root, history
        self.options = replace(options, gentle=True, workers=1)
        self.cancel = threading.Event()
        self.result: ScanResult | None = None
        self.entry: HistoryEntry | None = None
        self.state, self.error = "claimed", ""

    def run(self) -> None:
        """Retain canceled partial results/errors; only an actual saved history entry marks completion."""
        try:
            info = unpack_snapshot(stat_snapshot(self.root))
            if info.is_link or info.attributes & 0x400 or not stat.S_ISDIR(info.mode):
                raise ValueError("Scheduled scan requires an ordinary selected directory")
            self.result = scan(self.root, options=self.options, cancel=self.cancel)
            self.entry = self.history.save(self.result.root, cancel=self.cancel)
            self.state = "complete"
        except ScanCancelledError as error:
            self.result, self.state = error.partial, "canceled"
        except HistoryCancelledError:
            self.state = "canceled"
        except (OSError, ValueError, RecursionError) as error:
            self.state, self.error = "failed", str(error)
