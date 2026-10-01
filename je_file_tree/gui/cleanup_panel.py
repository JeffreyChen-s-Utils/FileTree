"""The Clean up tab's suggestions: groups of places whose contents can usually go, found after every scan."""

from __future__ import annotations

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from je_file_tree.core.cleanup import CleanupGroup
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui import grouped_list
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import CleanupWorker, wait_for


class CleanupPanel(QWidget):
    """The suggestions of ``core.cleanup``, one group per kind, with buttons to select them for Delete.

    A ``CleanupWorker`` finds them when a scan is shown (``set_root``) and again after the tree
    changed (``refresh``); only the latest search is shown.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.unit = AUTO_UNIT
        self.model = QStandardItemModel(self)
        self.view = grouped_list.build_view(self.model)
        self.status = QLabel()
        self.status.setWordWrap(True)
        # a long line would otherwise claim its whole width and squeeze the folder tree beside the tabs
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.select_all = QPushButton()
        self.select_group = QPushButton()
        self.select_all.clicked.connect(self.select_all_entries)
        self.select_group.clicked.connect(self.select_current_group)
        self._root: Node | None = None
        self._groups: list[CleanupGroup] = []
        self._current: CleanupWorker | None = None
        self._running: set[CleanupWorker] = set()
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(self.status, 1)
        bar.addWidget(self.select_group)
        bar.addWidget(self.select_all)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.view, 1)
        self.retranslate()

    @property
    def groups(self) -> list[CleanupGroup]:
        """The groups on screen, the largest first."""
        return self._groups

    @property
    def busy(self) -> bool:
        """Whether a search for suggestions is running whose result will be shown."""
        return self._current is not None

    def set_root(self, root: Node | None) -> None:
        """Suggest from ``root`` (None while a scan runs: the list waits)."""
        self.stop()
        self._root = root
        self._groups = []
        self._rebuild()
        self.refresh()

    def refresh(self) -> None:
        """Look for suggestions again (after a move to the Recycle Bin or a folder rescan)."""
        self.stop()
        if self._root is None:
            return
        worker = CleanupWorker(self._root, self)
        worker.done.connect(lambda groups: self._show(worker, groups))
        worker.finished.connect(lambda: self._running.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._current = worker
        self._running.add(worker)
        self._update_status()
        worker.start()

    def stop(self, *, wait: bool = False) -> None:
        """Stop the searches still running; with ``wait``, until their threads have ended."""
        self._current = None
        for worker in self._running.copy():
            worker.stop()
            if wait:
                wait_for(worker)

    def select_all_entries(self) -> None:
        """Select every suggested entry, ready for Delete."""
        grouped_list.select_entries(self.model, self.view, skip_first=False)

    def select_current_group(self) -> None:
        """Select the entries of the group the cursor is in."""
        index = self.view.currentIndex()
        if not index.isValid():
            return
        group = index.parent() if index.parent().isValid() else index
        grouped_list.select_group(self.model, self.view, group.row())

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit``."""
        self.unit = unit
        self._rebuild()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self.select_all.setText(tr("cleanup_select_all"))
        self.select_group.setText(tr("cleanup_select_group"))
        self._rebuild()

    def _show(self, worker: CleanupWorker, groups: list[CleanupGroup]) -> None:
        if worker is not self._current:
            return
        self._current = None
        self._groups = groups
        self._rebuild()

    def _rebuild(self) -> None:
        titles = [(tr("cleanup_group", title=tr(f"cleanup_{group.key}"), count=format_count(len(group.nodes)),
                      size=format_size(group.size, self.unit)), group.nodes) for group in self._groups]
        grouped_list.fill(self.model, self.view, titles, self.unit,
                          tips=[tr(f"cleanup_{group.key}_tip") for group in self._groups])
        self._update_status()

    def _update_status(self) -> None:
        has_entries = bool(self._groups) and self._current is None
        self.select_all.setEnabled(has_entries)
        self.select_group.setEnabled(has_entries)
        self.status.setText(self._status_text())

    def _status_text(self) -> str:
        if self._current is not None:
            return tr("cleanup_running")
        if self._root is None:
            return tr("cleanup_hint")
        if not self._groups:
            return tr("cleanup_none")
        size = format_size(sum(group.size for group in self._groups), self.unit)
        return tr("cleanup_summary", size=size, groups=format_count(len(self._groups)))
