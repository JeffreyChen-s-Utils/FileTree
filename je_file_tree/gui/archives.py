"""Own lazy archive metadata workers and display their virtual rows in the folder tree."""

from __future__ import annotations

import threading
from dataclasses import replace

from PySide6.QtCore import QObject, QThread, Signal

from je_file_tree.archive_formats import rar_members, seven_zip_members
from je_file_tree.core.archives import ArchiveCancelledError, ArchiveInventory, VirtualEntry, read_archive, zip_members
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tree_model import FolderTreeModel

MAX_ARCHIVE_WORKERS = 2


class ArchiveWorker(QThread):
    """Read only the captured archive's headers; cancellation is checked between parser reads."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, node: Node, parent: QObject) -> None:
        super().__init__(parent)
        self.node = node
        self.captured = replace(node, name=node.path, parent=None)
        self.cancel = threading.Event()

    def run(self) -> None:
        """Never call any extraction API or filesystem action on a member."""
        readers = {".zip": zip_members, ".7z": seven_zip_members, ".rar": rar_members}
        suffix = "." + self.captured.name.rsplit(".", 1)[-1].lower()
        try:
            result = read_archive(self.captured, reader=readers[suffix], cancel=self.cancel)
            for child in result.children:
                child.parent = self.node
        except ArchiveCancelledError:
            return
        except (OSError, ImportError) as exc:
            self.failed.emit(str(exc))
            return
        if not self.cancel.is_set():
            self.ready.emit(result)


class ArchiveController(QObject):
    """Bound concurrent inventories; invalidate stale replies and join every worker on close."""

    def __init__(self, model: FolderTreeModel, parent: QObject) -> None:
        super().__init__(parent)
        self.model = model
        self._workers: set[ArchiveWorker] = set()
        self._current: dict[Node, ArchiveWorker] = {}
        self._closed = False
        model.archive_requested.connect(self._request)
        model.archives_invalidated.connect(self.invalidate)

    def busy(self, node: Node) -> bool:
        """Whether this real archive has an active metadata request."""
        return node in self._current

    def _request(self, node: Node) -> None:
        if self._closed or len(self._workers) >= MAX_ARCHIVE_WORKERS:
            self.model.set_archive(node, [VirtualEntry(tr("archive_busy"), False, parent=node)])
            return
        worker = ArchiveWorker(node, self)
        self._current[node] = worker
        self._workers.add(worker)
        worker.ready.connect(lambda inventory: self._ready(worker, inventory))
        worker.failed.connect(lambda reason: self._failed(worker, reason))
        worker.finished.connect(lambda: self._workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _valid(self, worker: ArchiveWorker) -> bool:
        return (not self._closed and not worker.cancel.is_set() and self.model.root is not None
                and worker.node.is_in(self.model.root) and self._current.get(worker.node) is worker)

    def _ready(self, worker: ArchiveWorker, inventory: ArchiveInventory) -> None:
        if not self._valid(worker):
            return
        self._current.pop(worker.node)
        children = inventory.children
        if inventory.rejected:
            children = [*children, VirtualEntry(tr("archive_rejected", count=inventory.rejected), False,
                                                parent=worker.node)]
        if not children:
            children = [VirtualEntry(tr("archive_empty"), False, parent=worker.node)]
        self.model.set_archive(worker.node, children)

    def _failed(self, worker: ArchiveWorker, reason: str) -> None:
        if self._valid(worker):
            self._current.pop(worker.node)
            self.model.archive_error(worker.node, reason)

    def stop(self, node: Node) -> None:
        """Stop this archive's reads, retaining the real source and showing its incomplete state."""
        worker = self._current.pop(node, None)
        if worker is not None:
            worker.cancel.set()
            self.model.set_archive(node, [VirtualEntry(tr("archive_stopped"), False, parent=node)])

    def invalidate(self) -> None:
        """Discard replies before a new scan or real tree mutation."""
        self._current.clear()
        for worker in self._workers:
            worker.cancel.set()

    def shutdown(self) -> None:
        """Stop and join owned library calls before the view is destroyed."""
        self._closed = True
        self.invalidate()
        for worker in self._workers.copy():
            wait_for(worker)
