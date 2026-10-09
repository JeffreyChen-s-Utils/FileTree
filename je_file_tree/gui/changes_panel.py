"""The Changes tab: how each folder changed since a saved scan (Export → Folder tree (JSON))."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableView, QVBoxLayout, QWidget

from je_file_tree.core.compare import FolderChange, SavedScan
from je_file_tree.core.formatting import format_change, format_count, format_size, format_time
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import CompareWorker, wait_for
from je_file_tree.gui.tables import ChangesModel


class ChangesPanel(QWidget):
    """A summary line, a *Stop comparing* button and the changed folders, the biggest growth first.

    Reading the saved scan and comparing run on a ``CompareWorker`` (half a second each on 86,000
    folders); only the latest comparison is shown. ``shown(bool)`` tells whether there is a comparison
    to show, ``failed(str)`` that a file was not a saved scan.
    """

    shown = Signal(bool)
    failed = Signal(str)

    def __init__(self, table: QTableView, model: ChangesModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table = table
        self.model = model
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.stop_button = QPushButton()
        self.stop_button.clicked.connect(self.stop_comparing)
        self._root: Node | None = None
        self._saved: SavedScan | None = None
        self._current: CompareWorker | None = None
        self._running: set[CompareWorker] = set()
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(self.summary, 1)
        bar.addWidget(self.stop_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(table, 1)
        self.retranslate()

    @property
    def saved(self) -> SavedScan | None:
        """The saved scan compared with, or None."""
        return self._saved

    @property
    def busy(self) -> bool:
        """Whether a comparison is running whose result will be shown."""
        return self._current is not None

    def open(self, file: str) -> None:
        """Read the saved scan ``file`` and compare the tree with it (``failed`` when it is not one)."""
        if self._root is not None:
            self._run(CompareWorker(self._root, file=file, parent=self))

    def compare_saved(self, saved: SavedScan) -> None:
        """Compare with worker-loaded local history, including deeply nested saved trees."""
        if self._root is not None:
            self._run(CompareWorker(self._root, saved=saved, parent=self))

    def set_root(self, root: Node | None) -> None:
        """Compare this tree from now on (None while a scan runs: the list waits for the result)."""
        self._root = root
        if root is None:
            self.stop()
            self.model.set_rows([])
            self._update_summary()
            return
        self.refresh()

    def refresh(self) -> None:
        """Compare again after the tree changed."""
        if self._root is not None and self._saved is not None:
            self._run(CompareWorker(self._root, saved=self._saved, parent=self))

    def stop_comparing(self) -> None:
        """Forget the saved scan and hide the comparison."""
        self.stop()
        self._saved = None
        self.model.set_rows([])
        self._update_summary()
        self.shown.emit(False)

    def stop(self, *, wait: bool = False) -> None:
        """Ignore the comparisons still running; with ``wait``, until their threads have ended."""
        self._current = None
        if wait:
            for worker in self._running.copy():
                wait_for(worker)

    def retranslate(self) -> None:
        """Re-read every translated text (and the sizes, after a change of unit)."""
        self.stop_button.setText(tr("changes_stop"))
        self.model.refresh()
        self._update_summary()

    def _run(self, worker: CompareWorker) -> None:
        worker.done.connect(lambda saved, changes: self._done(worker, saved, changes))
        worker.failed.connect(lambda reason: worker is self._current and self._failed(reason))
        worker.finished.connect(lambda: self._running.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._current = worker
        self._running.add(worker)
        self._update_summary()
        worker.start()

    def _done(self, worker: CompareWorker, saved: SavedScan, changes: list[FolderChange]) -> None:
        if worker is not self._current:
            return
        self._current = None
        self._saved = saved
        self.model.set_rows(changes)
        self._update_summary()
        self.shown.emit(True)

    def _failed(self, reason: str) -> None:
        self._current = None
        self._update_summary()
        self.failed.emit(reason)

    def _update_summary(self) -> None:
        self.summary.setText(self._summary_text())

    def _summary_text(self) -> str:
        if self._current is not None:
            return tr("changes_running")
        saved, root = self._saved, self._root
        if saved is None:
            return ""
        if root is None:
            return tr("changes_waiting")
        return tr("changes_summary", path=saved.root or tr("multi_roots"), when=_when(saved.saved),
                  before=format_size(saved.size, self.model.unit), now=format_size(root.size, self.model.unit),
                  change=format_change(root.size - saved.size, self.model.unit),
                  count=format_count(self.model.rowCount()))


def _when(saved: str) -> str:
    """The saving time for the summary line, in the window's date format."""
    try:
        return format_time(datetime.fromisoformat(saved).timestamp())
    except ValueError:
        return tr("changes_unknown_time")
