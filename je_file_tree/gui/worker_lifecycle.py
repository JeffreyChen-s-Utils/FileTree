"""Continue on the GUI thread after owned workers join, without blocking its event loop."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QObject, QThread, QTimer
from shiboken6 import isValid

from je_file_tree.core.pacing import WINDOW


class ThreadFence(QObject):
    """Retain worker references and poll zero-time joins; never terminate an active native call."""

    def __init__(self, workers: Iterable[QThread], done: Callable[[], None], parent: QObject) -> None:
        super().__init__(parent)
        self._workers = tuple(workers)
        self._done: Callable[[], None] | None = done
        self._timer = QTimer(self)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        """Run immediately when already joined, otherwise let normal Qt events drive completion."""
        WINDOW.open()
        self._timer.start()
        self._poll()

    def _poll(self) -> None:
        if any(isValid(worker) and not worker.wait(0) for worker in self._workers):
            return
        self._timer.stop()
        done, self._done = self._done, None
        self._workers = ()
        self.deleteLater()
        if done is not None:
            done()


def after_threads(workers: Iterable[QThread], done: Callable[[], None], parent: QObject) -> ThreadFence:
    """Invoke ``done`` once on the owning GUI thread after every captured thread has joined."""
    fence = ThreadFence(workers, done, parent)
    fence.start()
    return fence
