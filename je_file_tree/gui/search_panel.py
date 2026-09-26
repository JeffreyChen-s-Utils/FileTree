"""The Search tab: find files and folders anywhere in the scan, by name and by conditions."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.search import Query, SearchResult, accepts
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import SearchWorker
from je_file_tree.gui.search_filters import SearchFilters
from je_file_tree.gui.tables import LargestFilesModel

# Typing has to pause this long before a search starts. Searching a scan of 765,000 entries took
# 0.4-1.2 s (measured 2026-09-26), so it runs on a worker thread and a new search stops the one before.
SEARCH_DELAY_MS = 300


class SearchPanel(QWidget):
    """A search box, conditions, saved searches, a summary line and the matches, largest first.

    Each search runs on a ``SearchWorker``; only the latest one's result is shown. ``set_root(None)``
    disables the panel (while a scan runs); ``rerun`` searches again after the tree changed.
    ``saved_changed(dict)`` hands the saved searches (name: state) to whoever keeps the settings.
    """

    saved_changed = Signal(object)

    def __init__(self, table: QTableView, model: LargestFilesModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table = table
        self.model = model
        self.box = QLineEdit()
        self.box.setClearButtonEnabled(True)
        self.filters = SearchFilters()
        self.filters.changed.connect(self.rerun)
        self.saved = QComboBox()
        self.saved.setMinimumContentsLength(12)
        self._saved_label = QLabel()
        self._save_button = QPushButton()
        self._delete_button = QPushButton()
        self._searches: dict[str, dict[str, Any]] = {}
        self.saved.activated.connect(lambda _index: self._load_saved())
        self._save_button.clicked.connect(self._ask_to_save)
        self._delete_button.clicked.connect(self.delete_saved)
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
        saved_row = QHBoxLayout()
        for widget in (self._saved_label, self.saved, self._save_button, self._delete_button):
            saved_row.addWidget(widget)
        saved_row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self.box)
        layout.addWidget(self.filters)
        layout.addLayout(saved_row)
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
        for widget in (self.box, self.filters, self.saved, self._save_button, self._delete_button):
            widget.setEnabled(root is not None)
        self.rerun()

    def query(self) -> Query:
        """What the box and the conditions ask for."""
        return Query(text=self.box.text(), **self.filters.conditions())

    def set_saved(self, searches: Mapping[str, Any]) -> None:
        """Offer these saved searches (name: state); entries that are not a name and a mapping are left out."""
        self._searches = {name: dict(state) for name, state in searches.items()
                          if isinstance(name, str) and name and isinstance(state, Mapping)}
        self._fill_saved()

    def save(self, name: str) -> None:
        """Save the box and the conditions under ``name`` (replacing a search of that name)."""
        name = name.strip()
        if not name:
            return
        self._searches[name] = {"text": self.box.text(), **self.filters.state()}
        self._fill_saved(select=name)
        self.saved_changed.emit(dict(self._searches))

    def delete_saved(self) -> None:
        """Forget the saved search chosen in the list."""
        name = self.saved.currentData()
        if name in self._searches:
            del self._searches[name]
            self._fill_saved()
            self.saved_changed.emit(dict(self._searches))

    def rerun(self) -> None:
        """Search for what the box holds (after typing, Enter, or a change to the tree)."""
        self._timer.stop()
        self.stop()
        query = self.query()
        if self._root is None or accepts(query, time.time()) is None:
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
        self.filters.retranslate()
        self._saved_label.setText(tr("search_saved"))
        self._save_button.setText(tr("search_save"))
        self._delete_button.setText(tr("search_delete"))
        self._fill_saved(select=self.saved.currentData())
        self.model.refresh()
        self._update_summary()

    def _fill_saved(self, select: str | None = None) -> None:
        self.saved.clear()
        self.saved.addItem(tr("search_saved_none"), None)
        for name in sorted(self._searches, key=str.casefold):
            self.saved.addItem(name, name)
        self.saved.setCurrentIndex(max(self.saved.findData(select), 0) if select else 0)
        self._delete_button.setEnabled(self._root is not None and bool(self._searches))

    def _load_saved(self) -> None:
        state = self._searches.get(self.saved.currentData())
        if state is None:
            return
        self.box.blockSignals(True)
        self.box.setText(str(state.get("text", "")))
        self.box.blockSignals(False)
        self.filters.apply(state)  # searches once, through filters.changed

    def _ask_to_save(self) -> None:
        name, accepted = QInputDialog.getText(self, tr("search_save_title"), tr("search_save_prompt"),
                                              text=self.saved.currentData() or "")
        if accepted:
            self.save(name)

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
