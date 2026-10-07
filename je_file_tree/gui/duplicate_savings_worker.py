"""Cancelable allocation estimates for the current duplicate search result."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QThread, Signal

from je_file_tree.core.duplicates import DuplicateGroup, estimate_duplicate_savings
from je_file_tree.core.node import Node


class DuplicateSavingsWorker(QThread):
    """Emit estimates only after every requested group is accounted for, or stop without a result."""

    done = Signal(object)

    def __init__(self, groups: list[DuplicateGroup], root: Node, limit: int,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._groups = groups
        self._root = root
        self._limit = limit
        self._cancel = threading.Event()

    def stop(self) -> None:
        """Cancel between groups and entries."""
        self._cancel.set()

    def run(self) -> None:
        """Compute without hashing or downloading file contents."""
        result = estimate_duplicate_savings(self._groups, self._root, limit=self._limit, cancel=self._cancel)
        if result is not None:
            self.done.emit(result)
