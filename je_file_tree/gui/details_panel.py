"""A collapsible, lazy selection summary; large subtree distributions run off the UI thread."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import QLabel, QLayout, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from je_file_tree.core.details import Breakdown, breakdown
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_size, format_time
from je_file_tree.core.node import Node
from je_file_tree.gui.elided_label import ElidedLabel
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.system_files import SystemFileInfo


class DetailsWorker(QThread):
    """Compute one selected folder's bounded distribution, cancellable at every entry."""

    done = Signal(object)

    def __init__(self, node: Node, now: float, parent: QWidget) -> None:
        super().__init__(parent)
        self.node, self.now = node, now
        self.cancel = threading.Event()

    def run(self) -> None:
        """Emit only complete, uncancelled distribution data."""
        result = breakdown(self.node, self.now, self.cancel)
        if result is not None:
            self.done.emit(result)


class DetailsPanel(QWidget):
    """Show recorded selection facts; folded and live-scan panes never walk descendants."""

    def __init__(self, settings: QSettings | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.node: Node | None = None
        self.live = False
        self.now = time.time()
        self.unit = AUTO_UNIT
        self._result: Breakdown | None = None
        self._current: DetailsWorker | None = None
        self._running: set[DetailsWorker] = set()
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.path_label = ElidedLabel()
        self.facts = QLabel()
        self.facts.setTextFormat(Qt.TextFormat.PlainText)
        self.facts.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.distribution = QLabel()
        self.distribution.setTextFormat(Qt.TextFormat.PlainText)
        self.distribution.setWordWrap(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.system_info = SystemFileInfo(self)
        body_layout.addWidget(self.system_info)
        for widget in (self.path_label, self.facts, self.distribution):
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            body_layout.addWidget(widget)
        self.body = QScrollArea()
        self.body.setWidgetResizable(True)
        self.body.setWidget(body)
        self.body.setMaximumHeight(235)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._start)
        self.toggle.toggled.connect(self._fold)
        self.toggle.setChecked(settings is not None and settings.value('details_expanded', False, type=bool))
        self._fold(self.toggle.isChecked())

    def set_node(self, node: Node | None, *, live: bool = False, now: float | None = None) -> None:
        """Invalidate stale replies and refresh totals without accessing the filesystem."""
        self.stop()
        self.node, self.live, self.now = node, live, time.time() if now is None else now
        self._result = None
        self.retranslate()
        if self.toggle.isChecked() and node is not None and not live:
            self._timer.start()

    def stop(self, *, wait: bool = False) -> None:
        """Cancel all obsolete requests; the window joins their owned threads on close."""
        self._timer.stop()
        self._current = None
        for worker in list(self._running):
            worker.cancel.set()
            if wait:
                wait_for(worker)

    def retranslate(self) -> None:
        """Refresh labels, dates and units without repeating the traversal."""
        self.toggle.setText(tr('details_title'))
        node = self.node
        self.system_info.set_node(node)
        self.path_label.setText(node.path if node is not None else tr('details_empty'))
        fields = () if node is None else (
            ('column_size', format_size(node.size, self.unit)),
            ('column_allocated', format_size(node.allocated, self.unit)),
            ('column_files', format_count(node.file_count)), ('column_folders', format_count(node.dir_count)),
            ('column_modified', format_time(node.modified)),
        )
        self.facts.setText('\n'.join(f'{tr(key)}: {value}' for key, value in fields))
        self.distribution.setText(self._distribution_text())

    def _fold(self, expanded: bool) -> None:
        self.body.setVisible(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        if self._settings is not None:
            self._settings.setValue('details_expanded', expanded)
        if expanded:
            self.set_node(self.node, live=self.live, now=self.now)
        else:
            self.stop()
        self.retranslate()

    def _start(self) -> None:
        if self.node is None or self.live or not self.toggle.isChecked():
            return
        worker = DetailsWorker(self.node, self.now, self)
        worker.done.connect(lambda result: self._done(worker, result))
        worker.finished.connect(lambda: self._running.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._current = worker
        self._running.add(worker)
        worker.start()

    def _done(self, worker: DetailsWorker, result: Breakdown) -> None:
        if worker is not self._current:
            return
        self._current, self._result = None, result
        self.retranslate()

    def _distribution_text(self) -> str:
        if self.node is None:
            return ''
        if self.live:
            return tr('details_live')
        if self._result is None:
            return tr('details_loading')
        lines = [tr('details_recorded')]
        for title, values, prefix in (('tab_types', self._result.types, 'category'),
                                     ('tab_age', self._result.ages, 'age')):
            lines.append(tr(title))
            for key, (size, count) in values.items():
                if count:
                    label = tr('age_colour_unknown') if key == 'unknown' else tr(f'{prefix}_{key}')
                    lines.append(tr('details_bucket', label=label, size=format_size(size, self.unit),
                                    count=format_count(count)))
        return '\n'.join(lines)
