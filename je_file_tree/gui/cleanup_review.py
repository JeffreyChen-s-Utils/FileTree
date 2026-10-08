"""One explicit, editable review queue before clean-up confirmations."""

from __future__ import annotations

import threading

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSizePolicy, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.core.formatting import format_count, format_size, format_time
from je_file_tree.core.cleanup import DETAILS, CleanupGroup
from je_file_tree.core.node import Node, outermost
from je_file_tree.core.protected import Protection, protection_of
from je_file_tree.core.savings import Savings, estimate_savings
from je_file_tree.gui import file_actions
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.cleanup_text import explanation
from je_file_tree.gui.scan_worker import wait_for

_HEADERS = ("review_select", "column_path", "review_rule", "review_reason", "column_modified",
            "column_size", "column_allocated", "review_protection", "review_consequence")


class ReviewModel(QAbstractTableModel):
    """Lazy rows over the proposed outermost entries; only the checkbox column is editable."""

    selection_changed = Signal()

    def __init__(self, nodes: list[Node], reasons: dict[Node, str | CleanupGroup], places: list[Protection],
                 unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.nodes = outermost(nodes)
        self._reasons = reasons
        self.checked = {node for node in self.nodes if self._rule(node)[1] is None
                        or self._rule(node)[1].risk == "low"}
        self._places = places
        self._unit = unit

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        """Qt: number of proposed paths."""
        return 0 if parent is not None and parent.isValid() else len(self.nodes)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        """Qt: review fields."""
        return 0 if parent is not None and parent.isValid() else len(_HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        """Qt: translated review headers."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr(_HEADERS[section]) if 0 <= section < len(_HEADERS) else None
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Qt: only selection checkboxes can be edited."""
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return base | Qt.ItemFlag.ItemIsUserCheckable if index.isValid() and index.column() == 0 else base

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Qt: full paths and explanations are also available as tooltips."""
        if not index.isValid() or not 0 <= index.row() < len(self.nodes):
            return None
        node = self.nodes[index.row()]
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            return Qt.CheckState.Checked if node in self.checked else Qt.CheckState.Unchecked
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        key, details = self._rule(node)
        reason = explanation(key, details) if key is not None else tr("review_manual_reason")
        protection = protection_of(node.path, self._places)
        values = ("", node.path, tr(f"cleanup_{key}") if key else tr("review_manual"), reason,
                  format_time(node.modified), format_size(node.size, self._unit),
                  format_size(node.allocated, self._unit),
                  tr(f"protected_{protection.reason}") if protection else tr("review_not_protected"), reason)
        return values[index.column()]

    def _rule(self, node: Node):
        reason = self._reasons.get(node)
        if isinstance(reason, CleanupGroup):
            return reason.key, reason.details
        return reason, DETAILS.get(reason)

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        """Qt: unchecking a row removes it from the eventual batch."""
        if not index.isValid() or index.column() != 0 or role != Qt.ItemDataRole.CheckStateRole:
            return False
        node = self.nodes[index.row()]
        if value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value):
            self.checked.add(node)
        else:
            self.checked.discard(node)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        self.selection_changed.emit()
        return True

    def selected_nodes(self) -> list[Node]:
        """Checked entries in the displayed order."""
        return [node for node in self.nodes if node in self.checked]


class _EstimateWorker(QThread):
    ready = Signal(object)

    def __init__(self, nodes: list[Node], root: Node, parent: QWidget) -> None:
        super().__init__(parent)
        self._nodes, self._root = nodes, root
        self._cancel = threading.Event()

    def stop(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        result = estimate_savings(self._nodes, root=self._root, cancel=self._cancel)
        if result is not None:
            self.ready.emit(result)


class CleanupReview(QDialog):
    """Review every proposal and its consequences; accepting only returns a selection, never moves it."""

    def __init__(self, nodes: list[Node], reasons: dict[Node, str | CleanupGroup], places: list[Protection],
                 unit: str, root: Node, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("review_title"))
        self.resize(1100, 560)
        self.model = ReviewModel(nodes, reasons, places, unit, self)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.view.setColumnWidth(1, 250)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        self.details.setMaximumHeight(120)
        self.details.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.view.selectionModel().currentChanged.connect(lambda _current, _previous: self._show_details())
        self.open_folder = QPushButton(tr("review_open_folder"))
        self.open_folder.clicked.connect(self._open_folder)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("review_continue"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        bar = QHBoxLayout()
        bar.addWidget(self.open_folder)
        bar.addStretch(1)
        bar.addWidget(self.buttons)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("review_hint")))
        layout.addWidget(self.view, 1)
        layout.addWidget(self.details)
        layout.addWidget(self.summary)
        layout.addLayout(bar)
        self._root, self._unit = root, unit
        self._current: _EstimateWorker | None = None
        self._running: set[_EstimateWorker] = set()
        self.model.selection_changed.connect(self._estimate)
        if self.model.rowCount():
            self.view.setCurrentIndex(self.model.index(0, 1))
        self._estimate()

    def selected_nodes(self) -> list[Node]:
        """The final checked outermost entries."""
        return self.model.selected_nodes()

    def shutdown(self) -> None:
        """Stop estimate workers before closing or destroying the dialog."""
        self._current = None
        for worker in self._running.copy():
            worker.stop()
            wait_for(worker)

    def done(self, result: int) -> None:
        """Qt: cancellation and acceptance both end the estimate workers."""
        self.shutdown()
        super().done(result)

    def _open_folder(self) -> None:
        index = self.view.currentIndex()
        if index.isValid():
            file_actions.reveal_in_file_manager(self.model.nodes[index.row()].path)

    def _show_details(self) -> None:
        row = self.view.currentIndex().row()
        if row < 0:
            self.details.clear()
            return
        def value(column: int) -> str:
            return str(self.model.data(self.model.index(row, column)))

        text = tr("review_details", path=value(1), rule=value(2), protection=value(7), consequence=value(8))
        self.details.setText(text)
        self.details.setToolTip(text)

    def _estimate(self) -> None:
        if self._current is not None:
            self._current.stop()
        chosen = self.selected_nodes()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.summary.setText(tr("review_estimating", count=format_count(len(chosen))))
        worker = _EstimateWorker(chosen, self._root, self)
        self._current = worker
        self._running.add(worker)
        worker.ready.connect(lambda value: self._show_estimate(worker, value))
        worker.finished.connect(lambda: self._running.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _show_estimate(self, worker: _EstimateWorker, value: Savings) -> None:
        if worker is not self._current:
            return
        self._current = None
        recovery = (tr("size_unknown") if value.recoverable_max is None else
                    f"0–{format_size(value.recoverable_max, self._unit)}")
        free = tr("size_unknown") if value.free_now is None else format_size(value.free_now, self._unit)
        self.summary.setText(tr("review_summary", count=format_count(len(self.selected_nodes())),
                                logical=format_size(value.logical, self._unit),
                                allocated=format_size(value.allocated, self._unit), recoverable=recovery, free=free))
        self._fit_summary()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(self.selected_nodes()))

    def resizeEvent(self, event) -> None:
        """Qt: preserve every wrapped estimate line when the review width changes."""
        super().resizeEvent(event)
        self._fit_summary()

    def _fit_summary(self) -> None:
        self.summary.setMinimumHeight(max(self.summary.fontMetrics().height(),
                                          self.summary.heightForWidth(self.summary.width())))
        self.layout().activate()
