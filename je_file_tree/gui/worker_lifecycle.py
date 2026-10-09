"""Continue on the GUI thread after owned workers join, without blocking its event loop."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QObject, QThread, QTimer
from PySide6.QtWidgets import QDialog, QWidget
from shiboken6 import isValid


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


def retire_worker(worker: QThread, parent: QObject) -> None:
    """Release a replaced, already canceled worker only after a full nonblocking join."""
    after_threads((worker,), worker.deleteLater, parent)


def queue_worker(worker: QThread, current: Callable[[], bool], parent: QObject,
                 discarded: Callable[[], None] | None = None) -> None:
    """Coalesce replacements behind retained workers; canceled/stale requests never start."""
    provider = getattr(parent, "pending_source_workers", None)
    sources = () if provider is None else provider()
    previous = (pending for pending in (*parent.findChildren(QThread), *sources) if pending is not worker)
    def dispatch() -> None:
        if current():
            worker.start()
        elif discarded is not None:
            discarded()
    after_threads(previous, dispatch, parent)


class WorkerDialog(QDialog):
    """Retain a modal operation guard until canceled workers have joined with the GUI still live."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._finish_waiting = False
        self._finish_ready = False

    def shutdown(self, *, wait: bool = True) -> None:
        """Subclasses invalidate replies/cancel work; join only when ``wait`` is requested."""
        raise NotImplementedError("Worker dialogs must define their owned cancellation lifecycle")

    def pending_source_workers(self) -> tuple[QThread, ...]:
        """Collect the owning window's canceled readers before any approved native execution."""
        provider = getattr(self.parent(), "pending_source_workers", None)
        return () if provider is None else provider()

    def defer_done(self, result: int) -> bool:
        """Defer dismissal until all descendant workers join; retain the first close decision."""
        if self._finish_ready:
            return False
        if self._finish_waiting:
            return True
        self.shutdown(wait=False)
        workers = tuple(self.findChildren(QThread))
        if all(not isValid(worker) or worker.wait(0) for worker in workers):
            return False
        self._finish_waiting = True
        self.setEnabled(False)
        after_threads(workers, lambda: self._finish_done(result), self)
        return True

    def _finish_done(self, result: int) -> None:
        self._finish_waiting = False
        self._finish_ready = True
        self.setEnabled(True)
        try:
            self.done(result)
        finally:
            self._finish_ready = False
