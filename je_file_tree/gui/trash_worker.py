"""Validate and move an approved batch without blocking Qt's event loop."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QThread, Signal

from je_file_tree.core.node import Node
from je_file_tree.core.operations import move_batch
from je_file_tree.core.protected import Protection
from je_file_tree.gui import file_actions


class TrashWorker(QThread):
    """Emit one MoveResult after a confirmed batch; cancellation is checked between entries."""

    done = Signal(object)

    def __init__(self, root: Node, nodes: list[Node], places: list[Protection],
                 approvals: dict[Node, Protection | None], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = root
        self._nodes = nodes
        self._places = places
        self._approvals = approvals
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Stop validation and skip every remaining entry."""
        self._cancel.set()

    def run(self) -> None:
        """Thread body; the GUI changes its model only after receiving the result."""
        result = move_batch(self._root, self._nodes, file_actions.move_to_trash,
                            places=self._places, approved=self._approvals, cancel=self._cancel)
        self.done.emit(result)
