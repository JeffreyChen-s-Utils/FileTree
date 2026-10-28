"""Browse direct folders from a captured tree without consulting source paths."""

from __future__ import annotations

import heapq
import threading

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QVBoxLayout, QWidget,
)

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog, after_threads, queue_worker, retire_worker

PAGE_SIZE = 200


class LoadedFolderWorker(QThread):
    """Sort one direct folder page on a cancellable worker."""

    ready = Signal(object)

    def __init__(self, node: Node, offset: int, parent: QWidget) -> None:
        super().__init__(parent)
        self.node, self.offset = node, offset
        self.cancel = threading.Event()

    def run(self) -> None:
        """Keep only the requested prefix; never enumerate descendants or source files."""
        count = 0

        def folders():
            nonlocal count
            for index, child in enumerate(self.node.children):
                if self.cancel.is_set():
                    return
                give_way()
                if child.is_dir and not child.is_link:
                    count += 1
                    yield child.name.casefold(), child.name, index, child

        prefix = heapq.nsmallest(self.offset + PAGE_SIZE, folders())
        if not self.cancel.is_set():
            self.ready.emit((tuple(row[3] for row in prefix[self.offset:]), count))


class LoadedFolderDialog(WorkerDialog):
    """Choose a captured folder using independently owned navigation workers."""

    def __init__(self, root: Node, parent: QWidget) -> None:
        super().__init__(parent)
        self.root = self.current = root
        self.selected: Node | None = None
        self.worker: LoadedFolderWorker | None = None
        self._closed = False
        self.offset = 0
        self.rows: tuple[Node, ...] = ()
        self.setWindowTitle(tr('trend_choose_folder'))
        self.resize(640, 460)
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        self.path.setAccessibleName(tr('trend_full_path'))
        self.list = QListWidget()
        self.list.setAccessibleName(tr('trend_loaded_folders'))
        self.list.itemActivated.connect(lambda _item: self.enter())
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.root_button = QPushButton(tr('trend_root'))
        self.up_button = QPushButton(tr('trend_up'))
        self.enter_button = QPushButton(tr('trend_enter'))
        self.previous = QPushButton(tr('trend_previous'))
        self.next = QPushButton(tr('trend_next'))
        self.root_button.clicked.connect(lambda: self.navigate(root))
        self.up_button.clicked.connect(lambda: self.navigate(self.current.parent or root))
        self.enter_button.clicked.connect(self.enter)
        self.previous.clicked.connect(lambda: self.navigate(self.current, max(0, self.offset - PAGE_SIZE)))
        self.next.clicked.connect(lambda: self.navigate(self.current, self.offset + PAGE_SIZE))
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('trend_choose_current'))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('date_cancel'))
        for button in self.buttons.buttons():
            button.setAutoDefault(False)
            button.setDefault(False)
        self.buttons.accepted.connect(self.choose)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.path)
        navigation = QHBoxLayout()
        for button in (self.root_button, self.up_button, self.enter_button, self.previous, self.next):
            button.setAutoDefault(False)
            navigation.addWidget(button)
        layout.addLayout(navigation)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.buttons)
        self.navigate(root)
        self.list.setFocus()

    def navigate(self, node: Node, offset: int = 0) -> None:
        """Replace one page request; a canceled page can never replace a newer folder."""
        if self._closed:
            return
        if self.worker is not None:
            self.worker.cancel.set()
            retire_worker(self.worker, self)
        self.current, self.offset, self.rows = node, offset, ()
        self.path.setText(node.path or '')
        self.list.clear()
        self.status.setText(tr('history_reading'))
        self.up_button.setEnabled(node is not self.root)
        self.previous.setEnabled(False)
        self.next.setEnabled(False)
        self.enter_button.setEnabled(False)
        worker = self.worker = LoadedFolderWorker(node, offset, self)
        worker.ready.connect(lambda result: after_threads((worker,), lambda: self._show(worker, result), self))
        queue_worker(worker, lambda: not self._closed and self.worker is worker and not worker.cancel.is_set(), self)

    def _show(self, worker: LoadedFolderWorker, result: tuple[tuple[Node, ...], int]) -> None:
        if self._closed or worker is not self.worker or worker.cancel.is_set():
            return
        self.rows, total = result
        self.list.addItems([node.name for node in self.rows])
        if self.rows:
            self.list.setCurrentRow(0)
        self.previous.setEnabled(self.offset > 0)
        self.next.setEnabled(self.offset + len(self.rows) < total)
        self.enter_button.setEnabled(bool(self.rows))
        self.status.setText(tr('trend_folder_page', first=self.offset + 1 if self.rows else 0,
                               last=self.offset + len(self.rows), total=total))

    def enter(self) -> None:
        """Open the focused folder's captured direct children."""
        row = self.list.currentRow()
        if 0 <= row < len(self.rows):
            self.navigate(self.rows[row])

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Keep list activation separate from accepting the currently displayed folder."""
        if self.focusWidget() is self.list and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)

    def choose(self) -> None:
        """Accept the folder whose full path is displayed."""
        self.selected = self.current
        self.accept()

    def shutdown(self, *, wait: bool = True) -> None:
        """Cancel every retained page request before dismissal."""
        self._closed = True
        for worker in self.findChildren(LoadedFolderWorker):
            worker.cancel.set()
            if wait:
                wait_for(worker)

    def done(self, result: int) -> None:
        """Keep the dialog alive until its navigation work has joined."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
