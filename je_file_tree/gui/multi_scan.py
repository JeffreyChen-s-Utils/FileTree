"""Review an explicit bounded folder list before starting a combined scan."""

import os

from PySide6.QtWidgets import (QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from je_file_tree.core.multi_scan import MAX_ROOTS
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.folder_validation import FolderWorker
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog, after_threads, queue_worker


class MultiScanDialog(WorkerDialog):
    """Own a literal list of actual folders; accepting freezes those roots for the worker."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.roots: tuple[str, ...] = ()
        self._closed = False
        self._pending: dict[str, FolderWorker] = {}
        self._workers: set[FolderWorker] = set()
        self._order: list[str] = []
        self.setWindowTitle(tr("multi_choose"))
        self.resize(700, 420)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("multi_hint"))
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(hint)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list)
        row = QHBoxLayout()
        self.add = QPushButton(tr("multi_add"))
        self.remove = QPushButton(tr("multi_remove"))
        row.addWidget(self.add)
        row.addWidget(self.remove)
        layout.addLayout(row)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.add.clicked.connect(self._add)
        self.remove.clicked.connect(self._remove)
        layout.addWidget(self.buttons)

    def add_root(self, path: str) -> None:
        """Validate a selected folder off the GUI thread; reserve bounded slots for pending checks."""
        if self._closed:
            return
        normalized = os.path.abspath(path)
        existing = {os.path.normcase(self.list.item(index).text()) for index in range(self.list.count())}
        key = os.path.normcase(normalized)
        if key in existing or key in self._pending or self.list.count() + len(self._pending) >= MAX_ROOTS:
            return
        worker = FolderWorker((normalized,), self)
        self._pending[key] = worker
        self._workers.add(worker)
        self._order.append(key)
        worker.checked.connect(lambda found: after_threads((worker,), lambda: self._checked(worker, key, found), self))
        worker.finished.connect(lambda: after_threads((worker,), lambda: self._retire(worker), self))
        queue_worker(worker, lambda: not self._closed and self._pending.get(key) is worker
                     and not worker.cancel.is_set(), self)
        self._buttons()

    def _checked(self, worker: FolderWorker, key: str, found: str | None) -> None:
        if self._closed or self._pending.get(key) is not worker or worker.cancel.is_set():
            return
        self._pending.pop(key)
        if found is None:
            self._order.remove(key)
        else:
            earlier = set(self._order[:self._order.index(key)])
            position = sum(os.path.normcase(self.list.item(index).text()) in earlier
                           for index in range(self.list.count()))
            self.list.insertItem(position, found)
        self._buttons()

    def _retire(self, worker: FolderWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
            worker.deleteLater()

    def _add(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("multi_add"))
        if path:
            self.add_root(path)

    def _remove(self) -> None:
        for item in self.list.selectedItems():
            self._order.remove(os.path.normcase(item.text()))
            self.list.takeItem(self.list.row(item))
        self._buttons()

    def _buttons(self) -> None:
        self.add.setEnabled(self.list.count() + len(self._pending) < MAX_ROOTS)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(self.list.count() > 0)

    def accept(self) -> None:
        """Freeze actual source names; no scan starts from an empty list."""
        if self.list.count():
            self.roots = tuple(self.list.item(index).text() for index in range(self.list.count()))
            super().accept()

    def shutdown(self, *, wait: bool = True) -> None:
        """Retain canceled folder queries until join; dismiss without blocking normal GUI events."""
        self._closed = True
        for worker in tuple(self._workers):
            worker.cancel.set()
            if wait:
                wait_for(worker)

    def done(self, result: int) -> None:
        """Keep the first dismissal decision until every owned folder query has terminated."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
