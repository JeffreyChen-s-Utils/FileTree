"""Owned workers capture immutable preview options and explicit namespace approvals."""

from dataclasses import dataclass
import os
import threading

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from je_file_tree.core.namespace_moves import NamespacePlan, NamespaceResult, execute_namespace, prepare_namespace
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanCancelledError, scan


@dataclass(frozen=True, slots=True)
class NamespaceRequest:
    """Frozen source tree, selected nodes and one literal destination mode."""

    root: Node
    nodes: tuple[Node, ...]
    directory: str | None
    pattern: str | None
    collision: str


class NamespacePreviewWorker(QThread):
    """Prepare every bounded outermost pair off the GUI thread, without payload reads or mutations."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, request: NamespaceRequest, parent: QWidget) -> None:
        super().__init__(parent)
        self.request, self.cancel = request, threading.Event()

    def run(self) -> None:
        """Canceled requests never publish late approvals."""
        try:
            request = self.request
            plan = prepare_namespace(request.root, request.nodes, directory=request.directory,
                                     pattern=request.pattern, collision=request.collision, cancel=self.cancel)
            if plan is not None and not self.cancel.is_set():
                self.ready.emit(plan)
        except (OSError, ValueError) as exc:
            if not self.cancel.is_set():
                self.failed.emit(str(exc))


class NamespaceOperationWorker(QThread):
    """Execute only a captured user-approved plan, stopping between entries and retaining outcomes."""

    ready = Signal(object)
    failed = Signal(str)
    progressed = Signal(int, int)
    refreshing = Signal(str)

    def __init__(self, plan: NamespacePlan, parent: QWidget) -> None:
        super().__init__(parent)
        self.plan, self.cancel = plan, threading.Event()
        self.result: NamespaceResult | None = None
        self.refreshed: list[tuple[str, int, int]] = []
        self.refresh_errors: list[tuple[str, str]] = []
        self.error = ""

    def run(self) -> None:
        """Retain completed outcomes even if closing suppresses their queued GUI reply."""
        try:
            self.result = execute_namespace(self.plan, cancel=self.cancel, progress=self.progressed.emit)
            self._refresh_external()
            self.ready.emit(self.result)
        except (OSError, ValueError) as exc:
            self.error = str(exc)
            self.failed.emit(str(exc))

    def _refresh_external(self) -> None:
        for parent in sorted(self.result.parents):
            try:
                inside = os.path.commonpath((parent, self.plan.root.path)) == self.plan.root.path
            except ValueError:
                inside = False
            if inside:
                continue  # The main window rebuilds the whole current root after joining this worker.
            self.refreshing.emit(parent)
            try:
                result = scan(parent, cancel=self.cancel)
                self.refreshed.append((parent, result.root.file_count, len(result.errors)))
            except (OSError, ValueError, ScanCancelledError) as exc:
                self.refresh_errors.append((parent, str(exc)))
