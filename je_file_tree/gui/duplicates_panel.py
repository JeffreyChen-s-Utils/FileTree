"""The Duplicates tab: files with the same content, grouped, with the space the extra copies take."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QItemSelectionModel

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from je_file_tree.core.duplicates import (
    DEFAULT_MIN_SIZE, DuplicateGroup, DuplicateProgress, DuplicateResult, DuplicateSavings,
)
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.savings import Savings
from je_file_tree.gui.i18n import tr
from je_file_tree.gui import grouped_list
from je_file_tree.gui.scan_worker import DuplicatesWorker, wait_for
from je_file_tree.gui.duplicate_savings_worker import DuplicateSavingsWorker
from je_file_tree.gui.tree_model import NODE_ROLE

MIN_SIZES = (1, 100 * 1024, DEFAULT_MIN_SIZE, 10 * 1024 * 1024, 100 * 1024 * 1024)
LISTED_GROUPS = 1000


class DuplicatesPanel(QWidget):
    """Looks for duplicates on request (a ``DuplicatesWorker``) and lists the groups, oldest copy first.

    ``set_root(None)`` stops a search and disables the panel (while a scan runs); ``prune`` drops
    files that left the tree (moved to the Recycle Bin, or in a rescanned folder).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.unit = AUTO_UNIT
        self.model = QStandardItemModel(self)
        self.view = grouped_list.build_view(self.model)
        self.min_size = QComboBox()
        self.start_button = QPushButton()
        self.stop_button = QPushButton()
        self.select_extra = QPushButton()
        self.keep_selected = QPushButton()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.estimate = QLabel()
        self.estimate.setWordWrap(True)
        self.estimate.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.estimate.setToolTip(tr("duplicates_estimate_assumption"))
        self._size_label = QLabel()
        self._busy = QProgressBar()
        self._busy.setRange(0, 0)
        self._busy.setMaximumWidth(120)
        self._root: Node | None = None
        self._worker: DuplicatesWorker | None = None
        self._search_workers: set[DuplicatesWorker] = set()
        self._estimator: DuplicateSavingsWorker | None = None
        self._estimate_workers: set[DuplicateSavingsWorker] = set()
        self._savings: DuplicateSavings | None = None
        self._groups: list[DuplicateGroup] = []
        self._found: DuplicateResult | None = None
        self._progress: DuplicateProgress | None = None
        self._stopped = False
        self._assemble()
        self.view.selectionModel().currentChanged.connect(lambda _current, _previous: self._keeper_button())
        self.retranslate()
        self.set_root(None)

    # --- public API -------------------------------------------------------

    @property
    def groups(self) -> list[DuplicateGroup]:
        """The groups found, as they stand after files left the tree."""
        return self._groups

    @property
    def running(self) -> bool:
        """Whether a search is running."""
        return self._worker is not None or self._estimator is not None

    def set_root(self, root: Node | None) -> None:
        """Look for duplicates beneath ``root`` from now on (None: nothing to search, the panel is idle)."""
        self.stop()
        self._root = root
        self._groups = []
        self._found = None
        self._savings = None
        self._stopped = False
        self._rebuild()
        self._update()

    def start(self) -> None:
        """Start looking for duplicates of the size chosen or larger."""
        if self._root is None or self.running:
            return
        worker = DuplicatesWorker(self._root, int(self.min_size.currentData()), self)
        worker.progressed.connect(lambda progress: worker is self._worker and self._show_progress(progress))
        worker.succeeded.connect(lambda result: worker is self._worker and self._show_result(result))
        worker.cancelled.connect(lambda: worker is self._worker and self._finish(stopped=True))
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: self._search_workers.discard(worker))
        self._worker = worker
        self._search_workers.add(worker)
        self._progress = None
        self._stopped = False
        self._update()
        worker.start()

    def stop(self, *, wait: bool = False) -> None:
        """Stop a running search (``wait``: until its thread has ended); what was found so far is dropped."""
        worker = self._worker
        self._cancel_estimate()
        if worker is not None:
            worker.stop()
        if wait:
            for pending in self._search_workers.copy() | self._estimate_workers.copy():
                wait_for(pending)
        self._worker = None
        self._stopped = True
        self._update()

    def prune(self) -> None:
        """Drop files that are no longer in the tree, and groups left with a single file."""
        root = self._root
        if root is None or not self._groups:
            return
        kept = []
        for group in self._groups:
            files = [node for node in group.files if node.is_in(root)]
            if len(files) > 1:
                kept.append(replace(group, files=files, kept=group.kept if group.kept in files else None,
                                    proofs={node: group.proofs[node] for node in files if node in group.proofs}))
        self._groups = kept
        self._savings = None
        self._rebuild()
        self._start_estimate()
        self._update()

    def select_extra_copies(self) -> None:
        """Select extras only in explicitly chosen groups that passed every metadata/protection check."""
        if self.running or self._savings is None:
            return
        self.view.clearSelection()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for row, group in enumerate(self._groups[:LISTED_GROUPS]):
            if row >= len(self._savings.issues) or self._savings.issues[row] is not None:
                continue
            parent = self.model.index(row, 0)
            for index in range(self.model.rowCount(parent)):
                item = self.model.index(index, 0, parent)
                if item.data(NODE_ROLE) is not group.kept:
                    self.view.selectionModel().select(item, flags)
        self.view.setFocus()

    def choose_kept_copy(self) -> None:
        """Make the current file the explicit keeper and recompute estimates/checks on a worker."""
        index = self.view.currentIndex()
        node = index.data(NODE_ROLE)
        row = index.parent().row()
        if self.running or node is None or not 0 <= row < len(self._groups):
            return
        self._groups[row] = replace(self._groups[row], kept=node)
        self._savings = None
        self._rebuild()
        self._start_estimate()

    def decisions_for(self, nodes: list[Node]) -> list[DuplicateGroup]:
        """All current duplicate groups touched by an approved file selection, including keeper mistakes."""
        chosen = set(nodes)
        return [group for group in self._groups if any(node in chosen for node in group.files)]

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit``."""
        self.unit = unit
        self._rebuild()
        self._update()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self._size_label.setText(tr("duplicates_min_size"))
        self.estimate.setToolTip(tr("duplicates_estimate_assumption"))
        current = self.min_size.currentData()
        self.min_size.blockSignals(True)
        self.min_size.clear()
        for size in MIN_SIZES:
            self.min_size.addItem(tr("duplicates_any_size") if size <= 1 else format_size(size), size)
        position = self.min_size.findData(current if current is not None else DEFAULT_MIN_SIZE)
        self.min_size.setCurrentIndex(max(0, position))
        self.min_size.blockSignals(False)
        self.start_button.setText(tr("duplicates_find"))
        self.stop_button.setText(tr("duplicates_stop"))
        self.select_extra.setText(tr("duplicates_select_extra"))
        self.select_extra.setToolTip(tr("duplicates_select_extra_tip"))
        self.keep_selected.setText(tr("duplicates_keep_selected"))
        self._rebuild()
        self._update()

    # --- building ---------------------------------------------------------

    def _assemble(self) -> None:
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(lambda: self.stop())  # noqa: PLW0108 - clicked(bool) must not reach stop()
        self.select_extra.clicked.connect(self.select_extra_copies)
        self.keep_selected.clicked.connect(self.choose_kept_copy)
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        for widget in (self._size_label, self.min_size, self.start_button, self.stop_button, self._busy):
            bar.addWidget(widget)
        bar.addStretch(1)
        decisions = QHBoxLayout()
        decisions.addStretch(1)
        decisions.addWidget(self.keep_selected)
        decisions.addWidget(self.select_extra)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addLayout(bar)
        layout.addLayout(decisions)
        layout.addWidget(self.status)
        layout.addWidget(self.estimate)
        layout.addWidget(self.view, 1)

    def _rebuild(self) -> None:
        """Fill the list from ``_groups`` (the most extra space first, up to ``LISTED_GROUPS``), oldest copy first."""
        groups = [(self._group_title(position, group),
                   sorted(group.files, key=lambda file: (file.modified, file.path)))
                  for position, group in enumerate(self._groups[:LISTED_GROUPS])]
        grouped_list.fill(self.model, self.view, groups, self.unit, tips=[title for title, _files in groups])
        for row, (_title, files) in enumerate(groups):
            kept = self._groups[row].kept
            for index, node in enumerate(files):
                if node is kept:
                    item = self.model.item(row).child(index, 0)
                    item.setText(tr("duplicates_kept_name", name=node.name))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

    # --- a search ---------------------------------------------------------

    def _show_progress(self, progress: DuplicateProgress) -> None:
        self._progress = progress
        self._update()

    def _show_result(self, result: DuplicateResult) -> None:
        self._found = result
        self._groups = list(result.groups)
        self._savings = None
        self._rebuild()
        self._finish(stopped=False)
        self._start_estimate()

    def _finish(self, *, stopped: bool) -> None:
        self._worker = None
        self._stopped = stopped
        self._update()

    def _update(self) -> None:
        running = self._worker is not None
        self.min_size.setEnabled(self._root is not None and not self.running)
        self.start_button.setEnabled(self._root is not None and not self.running)
        self.stop_button.setEnabled(self.running)
        self._busy.setVisible(self.running)
        eligible = self._savings is not None and any(issue is None for issue in self._savings.issues)
        self.select_extra.setEnabled(bool(self._groups) and eligible and not self.running)
        self._keeper_button()
        self.status.setText(self._status_text())
        self.estimate.setVisible(bool(self._groups) and not running)
        self.estimate.setText(self._estimate_text())

    def _keeper_button(self) -> None:
        self.keep_selected.setEnabled(not self.running and self.view.currentIndex().data(NODE_ROLE) is not None)

    def _cancel_estimate(self) -> None:
        if self._estimator is not None:
            self._estimator.stop()
            self._estimator = None

    def _start_estimate(self) -> None:
        self._cancel_estimate()
        if self._root is None or not self._groups:
            self._update()
            return
        worker = DuplicateSavingsWorker(self._groups, self._root, LISTED_GROUPS, self)
        worker.done.connect(lambda savings: worker is self._estimator and self._show_savings(savings))
        worker.finished.connect(lambda: self._estimate_workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._estimator = worker
        self._estimate_workers.add(worker)
        self._update()
        worker.start()

    def _show_savings(self, savings: DuplicateSavings) -> None:
        self._estimator = None
        self._savings = savings
        self._rebuild()
        self._update()

    def _savings_text(self, value: Savings) -> str:
        maximum = value.recoverable_max
        recovery = tr("size_unknown") if maximum is None else (
            f"{format_size(value.recoverable_min, self.unit)} – {format_size(maximum, self.unit)}")
        allocated = tr("size_unknown") if maximum is None else format_size(value.allocated, self.unit)
        return tr("duplicates_savings", allocated=allocated, recoverable=recovery)

    def _estimate_text(self) -> str:
        if self._savings is not None:
            return self._savings_text(self._savings.total) + " " + tr("duplicates_estimate_assumption")
        return tr("duplicates_estimating") if self._estimator is not None else tr("duplicates_estimate_unavailable")

    def _group_title(self, position: int, group: DuplicateGroup) -> str:
        title = tr("duplicates_group", count=format_count(len(group.files)), size=format_size(group.size, self.unit),
                   extra=format_size(group.extra, self.unit))
        if self._savings is not None and position < len(self._savings.groups):
            title += " " + self._savings_text(self._savings.groups[position])
        title += " " + (tr("duplicates_kept_path", path=group.kept.path) if group.kept is not None
                         else tr("duplicates_choose_keeper"))
        if self._savings is not None and position < len(self._savings.issues):
            issue = self._savings.issues[position]
            if issue is not None and issue != "duplicate_choose":
                title += " " + tr("duplicates_group_blocked", reason=tr(f"trash_skip_{issue}"))
        return title

    def _status_text(self) -> str:
        if self._worker is not None:
            progress = self._progress
            if progress is None:
                return tr("duplicates_starting")
            return tr("duplicates_running", files=format_count(progress.files_read),
                      total=format_count(progress.files_total), read=format_size(progress.bytes_read, self.unit),
                      bytes=format_size(progress.bytes_total, self.unit))
        if self._stopped:
            return tr("duplicates_stopped")
        if self._found is None:
            return tr("duplicates_hint")
        if not self._groups:
            return tr("duplicates_none")
        extra = sum(group.extra for group in self._groups)
        text = tr("duplicates_summary", groups=format_count(len(self._groups)), extra=format_size(extra, self.unit))
        if len(self._groups) > LISTED_GROUPS:
            text += " " + tr("duplicates_limited", shown=format_count(LISTED_GROUPS))
        if self._found.skipped:
            text += " " + tr("duplicates_skipped", count=format_count(self._found.skipped))
        return text
