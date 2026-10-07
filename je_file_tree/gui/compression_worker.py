"""Owned worker for explicitly confirmed compression operations, with cancelable native commands."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from je_file_tree.core.compression_ops import compress_files
from je_file_tree.core.node import Node


class CompactWorker(QThread):
    """Run only captured reviewed files; callers must join this worker before destroying its owner."""

    ready = Signal(object)
    failed = Signal(str)
    progressed = Signal(int, int)

    def __init__(self, root: Node, files: Sequence[Node], mode: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.root, self.files, self.mode = root, tuple(files), mode
        self.cancel = threading.Event()

    def run(self) -> None:
        """Publish partial results even after Stop, so completed mutations stay visible."""
        try:
            result = compress_files(self.root, self.files, self.mode, cancel=self.cancel,
                                    progress=self.progressed.emit)
        except (OSError, ValueError) as exc:
            self.failed.emit(str(exc))
        else:
            self.ready.emit(result)
