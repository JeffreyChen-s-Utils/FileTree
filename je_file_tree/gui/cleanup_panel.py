"""The Clean up tab's suggestions: groups of places whose contents can usually go, found after every scan."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from je_file_tree.core.cleanup import CleanupGroup
from je_file_tree.core.cleanup_policy import CleanupPolicy
from je_file_tree.core.coverage import Coverage
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui import grouped_list
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.cleanup_text import explanation
from je_file_tree.gui.scan_worker import CleanupWorker, wait_for


class CleanupPanel(QWidget):
    """The suggestions of ``core.cleanup``, one group per kind, with buttons to select them for Delete.

    A ``CleanupWorker`` finds them when a scan is shown (``set_root``) and again after the tree
    changed (``refresh``); only the latest search is shown.
    """

    review_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.unit = AUTO_UNIT
        self.model = QStandardItemModel(self)
        self.view = grouped_list.build_view(self.model)
        self.status = QLabel()
        self.status.setWordWrap(True)
        # a long line would otherwise claim its whole width and squeeze the folder tree beside the tabs
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.coverage_banner = QLabel()
        self.coverage_banner.setWordWrap(True)
        self.coverage_banner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._coverage: Coverage | None = None
        self._partial = False
        self._policy = CleanupPolicy()
        self.select_all = QPushButton()
        self.select_group = QPushButton()
        self.select_all.clicked.connect(self.select_all_entries)
        self.select_group.clicked.connect(self.select_current_group)
        self.view.selectionModel().currentChanged.connect(lambda _current, _previous: self._group_button())
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
        layout.addWidget(self.coverage_banner)
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

    def set_root(self, root: Node | None, *, partial: bool = False) -> None:
        """Suggest from ``root`` (None while a scan runs: the list waits)."""
        self.stop()
        self._root = root
        self._coverage = None
        self._partial = partial
        self._groups = []
        self._rebuild()
        self.refresh()

    def refresh(self) -> None:
        """Look for suggestions again (after a move to the Recycle Bin or a folder rescan)."""
        self.stop()
        if self._root is None:
            return
        self._groups = []
        self._coverage = None
        self._rebuild()
        worker = CleanupWorker(self._root, self, policy=self._policy)
        worker.done.connect(lambda groups, coverage: self._show(worker, groups, coverage))
        worker.finished.connect(lambda: self._running.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._current = worker
        self._running.add(worker)
        self._update_status()
        worker.start()

    def set_policy(self, policy: CleanupPolicy) -> None:
        """Apply settings only to proposals; the scan and its accounting remain unchanged."""
        self._policy = policy
        self.refresh()

    def stop(self, *, wait: bool = False) -> None:
        """Stop the searches still running; with ``wait``, until their threads have ended."""
        self._current = None
        for worker in self._running.copy():
            worker.stop()
            if wait:
                wait_for(worker)

    def select_all_entries(self) -> None:
        """Select every suggested entry, ready for Delete."""
        if self.select_all.isEnabled():
            self.view.clearSelection()
            groups = [group for group in self._groups if group.details.risk == "low"]
            for row, group in enumerate(self._groups):
                if group.details.risk == "low":
                    grouped_list.select_group(self.model, self.view, row, append=True)
            self.review_requested.emit([node for group in groups for node in group.nodes])

    def select_current_group(self) -> None:
        """Select the entries of the group the cursor is in."""
        if not self.select_group.isEnabled():
            return
        index = self.view.currentIndex()
        if not index.isValid():
            return
        group = index.parent() if index.parent().isValid() else index
        grouped_list.select_group(self.model, self.view, group.row())
        self.review_requested.emit(self._groups[group.row()].nodes)

    def reasons_for(self, nodes: list[Node]) -> dict[Node, CleanupGroup]:
        """Rule keys of current suggestions in a proposed batch, including mixed manual selections."""
        wanted = set(nodes)
        return {node: group for group in self._groups for node in group.nodes if node in wanted}

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit``."""
        self.unit = unit
        self._rebuild()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self.select_all.setText(tr("cleanup_select_all"))
        self.select_group.setText(tr("cleanup_select_group"))
        self._rebuild()

    def _show(self, worker: CleanupWorker, groups: list[CleanupGroup], coverage: Coverage) -> None:
        if worker is not self._current:
            return
        self._current = None
        self._groups = groups
        self._coverage = coverage
        self._rebuild()

    def _rebuild(self) -> None:
        titles = [(tr("cleanup_group", title=tr(f"cleanup_{group.key}"), count=format_count(len(group.nodes)),
                      size=format_size(group.size, self.unit)), group.nodes) for group in self._groups]
        grouped_list.fill(self.model, self.view, titles, self.unit,
                          tips=[explanation(group.key, group.details) for group in self._groups])
        self._update_status()

    def _update_status(self) -> None:
        has_entries = bool(self._groups) and self._current is None
        self.select_all.setEnabled(has_entries and any(group.details.risk == "low" for group in self._groups)
                                   and not self._partial and self._coverage is not None
                                   and self._coverage.complete)
        self.select_group.setEnabled(has_entries)
        self._group_button()
        self.status.setText(self._status_text())
        coverage = self._coverage
        self.coverage_banner.setVisible(coverage is not None)
        if coverage is not None:
            key = "coverage_complete" if coverage.complete and not self._partial else "coverage_partial"
            self.coverage_banner.setText(tr(key, size=format_size(coverage.known_bytes, self.unit),
                                            known=format_count(coverage.known_folders),
                                            skipped=format_count(coverage.skipped_folders),
                                            denied=format_count(coverage.inaccessible_folders),
                                            pending=format_count(coverage.pending_folders)))

    def _group_button(self) -> None:
        index = self.view.currentIndex()
        row = index.parent().row() if index.parent().isValid() else index.row()
        manual = 0 <= row < len(self._groups) and self._groups[row].details.risk == "manual"
        self.select_group.setText(tr("cleanup_review_manual" if manual else "cleanup_select_group"))

    def _status_text(self) -> str:
        if self._current is not None:
            return tr("cleanup_running")
        if self._root is None:
            return tr("cleanup_hint")
        if not self._groups:
            return tr("cleanup_none")
        size = format_size(sum(group.size for group in self._groups), self.unit)
        return tr("cleanup_summary", size=size, groups=format_count(len(self._groups)))
