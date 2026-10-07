"""Bounded chart navigation history and clickable, horizontally scrollable ancestors."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMenu, QScrollArea, QSizePolicy, QToolButton, QWidget

from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr

_HISTORY_LIMIT = 100
_VISIBLE_NODES = 6
_LABEL_WIDTH = 120


class FolderHistory:
    """Keep at most 100 visits in one scan, skipping detached/replaced entries."""

    def __init__(self) -> None:
        self.root: Node | None = None
        self.entries: list[Node] = []
        self.position = -1

    def set_root(self, root: Node | None) -> None:
        """A new scan invalidates the previous scan's navigation references."""
        if root is not self.root:
            self.root, self.entries, self.position = root, [], -1

    def visit(self, node: Node | None) -> None:
        """Append a folder visit, discarding forward visits after a new navigation."""
        self.prune()
        if not self._valid(node) or self.current is node:
            return
        self.entries = self.entries[:self.position + 1] + [node]
        self.entries = self.entries[-_HISTORY_LIMIT:]
        self.position = len(self.entries) - 1

    @property
    def current(self) -> Node | None:
        """The currently indexed visit, if any."""
        return self.entries[self.position] if 0 <= self.position < len(self.entries) else None

    def prune(self) -> None:
        """Remove stale visits without traversing the scanned descendants."""
        entries, position = [], -1
        for number, node in enumerate(self.entries):
            if self._valid(node):
                entries.append(node)
                if number <= self.position:
                    position += 1
        self.entries, self.position = entries, position

    def step(self, offset: int) -> Node | None:
        """Move back/forward by one retained visit; return no node at the boundary."""
        self.prune()
        position = self.position + offset
        if offset not in (-1, 1) or not 0 <= position < len(self.entries):
            return None
        self.position = position
        return self.current

    def _valid(self, node: Node | None) -> bool:
        return bool(node is not None and node.is_dir and not node.is_link
                    and self.root is not None and node.is_in(self.root))


class Breadcrumbs(QWidget):
    """Clickable ancestors plus Back/Forward, without deep paths widening the chart."""

    navigate = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history = FolderHistory()
        self._node: Node | None = None
        self.back = QToolButton()
        self.forward = QToolButton()
        self.back.setArrowType(Qt.ArrowType.LeftArrow)
        self.forward.setArrowType(Qt.ArrowType.RightArrow)
        self.back.clicked.connect(lambda: self.step(-1))
        self.forward.clicked.connect(lambda: self.step(1))
        self._container = QWidget()
        self._crumbs = QHBoxLayout(self._container)
        self._crumbs.setContentsMargins(0, 0, 0, 0)
        self._crumbs.setSpacing(2)
        self._scroll = QScrollArea()
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._container)
        self._scroll.setMinimumWidth(60)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._scroll_to_current)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMaximumHeight(46)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.back)
        layout.addWidget(self.forward)
        layout.addWidget(self._scroll, 1)
        for sequence, offset in (("Alt+Left", -1), ("Alt+Right", 1)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(lambda direction=offset: self.isVisible() and self.step(direction))
        self.retranslate()

    def set_root(self, root: Node | None) -> None:
        """Bind navigation to the current scan; resuming the same live root preserves visits."""
        self.history.set_root(root)
        if not self.history._valid(self._node):
            self._node = None
            self._rebuild()
        self._update_buttons()

    def visit(self, node: Node | None) -> None:
        """Follow a chart navigation, recording folders once and updating clickable ancestors."""
        self.history.visit(node)
        self._node = node
        self._rebuild()
        self._update_buttons()

    def step(self, offset: int) -> None:
        """Navigate one valid history visit; the chart's reply does not append it twice."""
        node = self.history.step(offset)
        if node is not None:
            self.navigate.emit(node)
        self._update_buttons()

    def retranslate(self) -> None:
        """Refresh accessible labels, shortcut hints and the hidden-ancestor menu text."""
        self.back.setToolTip(tr("breadcrumbs_back"))
        self.forward.setToolTip(tr("breadcrumbs_forward"))
        self.back.setAccessibleName(tr("breadcrumbs_back"))
        self.forward.setAccessibleName(tr("breadcrumbs_forward"))
        self._rebuild()
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.history.prune()
        self.back.setEnabled(self.history.position > 0)
        self.forward.setEnabled(0 <= self.history.position < len(self.history.entries) - 1)

    def _rebuild(self) -> None:
        while self._crumbs.count():
            widget = self._crumbs.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        chain = []
        node = self._node
        while node is not None:
            chain.append(node)
            node = node.parent
        chain.reverse()
        shown = chain if len(chain) <= _VISIBLE_NODES else chain[:1] + chain[-(_VISIBLE_NODES - 1):]
        for number, node in enumerate(shown):
            if number == 1 and len(chain) > _VISIBLE_NODES:
                button = QToolButton()
                button.setText(tr("breadcrumbs_more"))
                button.setToolTip(tr("breadcrumbs_more_tip"))
                hidden = chain[1:-(_VISIBLE_NODES - 1)]
                button.clicked.connect(lambda _checked=False, entries=hidden, anchor=button:
                                        self._ancestors_menu(entries, anchor))
                self._crumbs.addWidget(button)
            button = QToolButton()
            label = node.name if node.parent is not None else os.path.basename(node.name.rstrip("\\/")) or node.name
            button.setText(self.fontMetrics().elidedText(label, Qt.TextElideMode.ElideMiddle, _LABEL_WIDTH))
            button.setToolTip(node.path)
            button.setAccessibleName(label)
            button.setAutoRaise(True)
            button.setEnabled(node is not self._node)
            button.clicked.connect(lambda _checked=False, entry=node: self.navigate.emit(entry))
            self._crumbs.addWidget(button)
        self._crumbs.addStretch(1)
        self._scroll_timer.start(0)

    def _scroll_to_current(self) -> None:
        bar = self._scroll.horizontalScrollBar()
        bar.setValue(bar.maximum())

    def _ancestors_menu(self, entries: list[Node], anchor: QWidget) -> None:
        menu = QMenu(self)
        for node in entries:
            action = menu.addAction(node.name)
            action.triggered.connect(lambda _checked=False, entry=node: self.navigate.emit(entry))
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(anchor.mapToGlobal(anchor.rect().bottomLeft()))
