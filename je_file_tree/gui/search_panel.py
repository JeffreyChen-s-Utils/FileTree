"""The Search tab: find files and folders by name anywhere in the scan."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QLineEdit, QTableView, QVBoxLayout, QWidget

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.search import SearchResult, name_matcher
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import SearchWorker
from je_file_tree.gui.tables import LargestFilesModel

# Typing has to pause this long before a search starts. Searching a scan of 765,000 entries took
# 0.4-1.2 s (measured 2026-09-26), so it runs on a worker thread and a new search stops the one before.
SEARCH_DELAY_MS = 300


class SearchPanel(QWidget):
    """A search box, a summary line and the matches, largest first.

    Each search runs on a ``SearchWorker``; only the latest one's result is shown. ``set_root(None)``
    disables the panel (while a scan runs); ``rerun`` searches again after the tree changed.
    """

    def __init__(self, table: QTableView, model: LargestFilesModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table = table
        self.model = model
        self.box = QLineEdit()
        self.box.setClearButtonEnabled(True)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self._root: Node | None = None
        self._current: SearchWorker | None = None
        self._running: set[SearchWorker] = set()
        self._result: SearchResult | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SEARCH_DELAY_MS)
        self._timer.timeout.connect(self.rerun)
        self.box.textChanged.connect(lambda _text: self._timer.start())
        self.box.returnPressed.connect(self.rerun)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self.box)
        layout.addWidget(self.summary)
        layout.addWidget(table, 1)
        self.set_root(None)

    @property
    def busy(self) -> bool:
        """Whether a search is running whose result will be shown."""
        return self._current is not None

    def set_root(self, root: Node | None) -> None:
        """Search beneath ``root`` from now on (None: there is no scan to search, the box is disabled)."""
        self._root = root
        self.box.setEnabled(root is not None)
        self.rerun()

    def rerun(self) -> None:
        """Search for what the box holds (after typing, Enter, or a change to the tree)."""
        self._timer.stop()
        self.stop()
        query = self.box.text()
        if self._root is None or name_matcher(query) is None:
            self._result = None
            self.model.set_rows([])
            self._update_summary()
            return
        worker = SearchWorker(self._root, query, self)
        worker.found.connect(lambda result: self._found(worker, result))
        worker.finished.connect(lambda: self._running.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._current = worker
        self._running.add(worker)
        self._update_summary()
        worker.start()

    def stop(self, *, wait: bool = False) -> None:
        """Stop every search still running; with ``wait``, until their threads have ended."""
        self._current = None
        for worker in list(self._running):
            worker.stop()
            if wait:
                worker.wait()

    def focus(self) -> None:
        """Put the cursor in the search box, its text selected."""
        self.box.setFocus()
        self.box.selectAll()

    def retranslate(self) -> None:
        """Re-read every translated text (and the sizes, after a change of unit)."""
        self.box.setPlaceholderText(tr("search_placeholder"))
        self.model.refresh()
        self._update_summary()

    def _found(self, worker: SearchWorker, result: SearchResult) -> None:
        if worker is not self._current:
            return  # a newer search is running, or the panel was stopped
        self._current = None
        self._result = result
        self.model.set_rows(result.matches)
        self._update_summary()

    def _update_summary(self) -> None:
        self.summary.setText(self._summary_text())

    def _summary_text(self) -> str:
        if self._current is not None:
            return tr("search_running")
        result = self._result
        if result is None:
            return tr("search_hint")
        if result.count == 0:
            return tr("search_none")
        text = tr("search_summary", count=format_count(result.count), size=format_size(result.size, self.model.unit))
        if result.count > len(result.matches):
            text += " " + tr("search_limited", shown=format_count(len(result.matches)))
        return text
