"""A bounded, zoomable folder hierarchy chart for the Chart tab."""

from __future__ import annotations

import html

from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QWheelEvent
from PySide6.QtWidgets import QToolTip, QWidget

from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_share, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.tree_layout import MAX_VISIBLE, PAGE_SIZE, DiagramItem, layout
from je_file_tree.gui.i18n import tr


HORIZONTAL, VERTICAL = "horizontal", "vertical"
ORIENTATIONS = (HORIZONTAL, VERTICAL)
_NODE_WIDTH = 190
_NODE_HEIGHT = 48
_LEVEL_GAP = 235
_ROW_GAP = 66
_MARGIN = 24


class TreeDiagramWidget(QWidget):
    """Draw only visible folder nodes; click selects, expand and double-click focuses."""

    node_clicked = Signal(object)
    view_root_changed = Signal(object)
    context_menu_requested = Signal(object, QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.unit = AUTO_UNIT
        self.orientation = HORIZONTAL
        self._view_root: Node | None = None
        self._selected: Node | None = None
        self._expanded: set[int] = set()
        self._counts: dict[int, int] = {}
        self._offsets: dict[int, int] = {}
        self._rows: list[DiagramItem] | None = None
        self._zoom = 1.0
        self.resize(self.sizeHint())

    @property
    def view_root(self) -> Node | None:
        """The folder shown at the start of the diagram."""
        return self._view_root

    def set_view_root(self, node: Node | None) -> None:
        """Focus a folder, or its parent when ``node`` is a file."""
        if node is not None and not node.is_dir:
            node = node.parent
        if node is not self._view_root:
            self._expanded.clear()
            self._counts.clear()
            self._offsets.clear()
        self._view_root = node
        self.invalidate()
        self.view_root_changed.emit(node)

    def zoom_out(self) -> None:
        """Focus the parent folder (ChartStack's shared navigation interface)."""
        if self._view_root is not None and self._view_root.parent is not None:
            self.set_view_root(self._view_root.parent)

    def set_selected(self, node: Node | None) -> None:
        """Highlight a folder selected in any other view."""
        self._selected = node
        self.update()

    def set_orientation(self, orientation: str) -> None:
        """Lay branches left-to-right or top-to-bottom."""
        if orientation in ORIENTATIONS and orientation != self.orientation:
            self.orientation = orientation
            self.invalidate()

    def set_zoom(self, zoom: float) -> None:
        """Scale cards and spacing while keeping the number of nodes bounded."""
        bounded = min(2.0, max(0.5, zoom))
        if bounded != self._zoom:
            self._zoom = bounded
            self.invalidate()

    def invalidate(self) -> None:
        """Discard cached geometry after a scan step, rescan or size change."""
        self._rows = None
        self.resize(self.sizeHint())
        self.updateGeometry()
        self.update()

    def rows(self) -> list[DiagramItem]:
        """The bounded, cached layout, useful for hit testing and keyboard use."""
        if self._rows is None:
            self._rows = layout(self._view_root, expanded=frozenset(self._expanded),
                                visible_counts=self._counts, page_offsets=self._offsets)
        return self._rows

    def card_rect(self, item: DiagramItem) -> QRectF:
        """Card position in widget coordinates."""
        x = item.depth * _LEVEL_GAP if self.orientation == HORIZONTAL else item.row * _LEVEL_GAP
        y = item.row * _ROW_GAP if self.orientation == HORIZONTAL else item.depth * _ROW_GAP
        return QRectF((_MARGIN + x) * self._zoom, (_MARGIN + y) * self._zoom,
                      _NODE_WIDTH * self._zoom, _NODE_HEIGHT * self._zoom)

    def item_at(self, x: float, y: float) -> DiagramItem | None:
        """Return the card under a point, if any."""
        return next((item for item in self.rows() if self.card_rect(item).contains(QPointF(x, y))), None)

    def sizeHint(self) -> QSize:
        """Enough room for the bounded diagram; the parent scroll area handles panning."""
        rows = self.rows()
        depth = max((item.depth for item in rows), default=0)
        last = max(len(rows) - 1, 0)
        width = depth * _LEVEL_GAP if self.orientation == HORIZONTAL else last * _LEVEL_GAP
        height = last * _ROW_GAP if self.orientation == HORIZONTAL else depth * _ROW_GAP
        return QSize(max(400, round((_MARGIN * 2 + width + _NODE_WIDTH) * self._zoom)),
                     max(260, round((_MARGIN * 2 + height + _NODE_HEIGHT) * self._zoom)))

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint only the cached, bounded layout; Qt clips to the scrolled viewport."""
        painter = QPainter(self)
        painter.fillRect(event.rect(), self.palette().base())
        if not self.rows():
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, tr("treemap_empty"))
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.palette().mid().color(), max(1, round(self._zoom))))
        for item in self.rows()[1:]:
            if item.parent is not None:
                self._draw_branch(painter, self.rows()[item.parent], item)
        for item in self.rows():
            rect = self.card_rect(item)
            if rect.intersects(event.rect()):
                self._draw_card(painter, item, rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Select a card; its leading symbol expands or collapses a folder."""
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.item_at(event.position().x(), event.position().y())
            if item is not None:
                if item.node is None:
                    self._reveal_more(item)
                elif (item.node is not self._view_root and item.node.is_dir and item.node.error is None
                      and event.position().x() < self.card_rect(item).left() + 26 * self._zoom):
                    self._toggle(item.node)
                else:
                    self.node_clicked.emit(item.node)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-click a folder card to use it as the new chart root."""
        item = self.item_at(event.position().x(), event.position().y())
        if item is not None and item.node is not None and item.node.is_dir:
            self.set_view_root(item.node)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Describe the card under the mouse without reading file contents."""
        item = self.item_at(event.position().x(), event.position().y())
        if item is None:
            QToolTip.hideText()
        elif item.node is not None:
            QToolTip.showText(event.globalPosition().toPoint(), html.escape(item.node.path), self)
        super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Ctrl+wheel zooms; plain wheel remains scroll-area panning."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self._zoom + (0.1 if event.angleDelta().y() > 0 else -0.1))
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Move selection by row; Right/Left expands or collapses the selected folder."""
        rows = self.rows()
        current = next((i for i, row in enumerate(rows) if row.node is self._selected), 0)
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and rows:
            step = -1 if key == Qt.Key.Key_Up else 1
            for index in range(current + step, len(rows) if step > 0 else -1, step):
                if rows[index].node is not None:
                    self.node_clicked.emit(rows[index].node)
                    return
        elif (key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and self._selected is not None
              and self._selected is not self._view_root and self._selected.error is None):
            want_open = key == Qt.Key.Key_Right
            if (id(self._selected) in self._expanded) != want_open:
                self._toggle(self._selected)
                return
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._selected is not None:
            self.set_view_root(self._selected)
            return
        elif key == Qt.Key.Key_Backspace:
            self.zoom_out()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Pass the clicked folder to the existing context menu."""
        item = self.item_at(event.pos().x(), event.pos().y())
        node = item.node if item is not None and item.node is not None else self._view_root
        self.context_menu_requested.emit(node, event.globalPos())

    def _toggle(self, node: Node) -> None:
        if id(node) in self._expanded:
            self._expanded.remove(id(node))
        else:
            self._expanded.add(id(node))
        self.invalidate()

    def _reveal_more(self, item: DiagramItem) -> None:
        if item.parent is not None:
            owner = self.rows()[item.parent].node
            if owner is not None:
                count = self._counts.get(id(owner), PAGE_SIZE)
                if len(self.rows()) >= MAX_VISIBLE:
                    self._offsets[id(owner)] = self._offsets.get(id(owner), 0) + count
                    self._counts[id(owner)] = PAGE_SIZE
                else:
                    self._counts[id(owner)] = count + PAGE_SIZE
                self.invalidate()

    def _draw_branch(self, painter: QPainter, parent: DiagramItem, child: DiagramItem) -> None:
        start, end = self.card_rect(parent), self.card_rect(child)
        if self.orientation == HORIZONTAL:
            painter.drawLine(QLineF(start.right(), start.center().y(), end.left(), end.center().y()))
        else:
            painter.drawLine(QLineF(start.center().x(), start.bottom(), end.center().x(), end.top()))

    def _draw_card(self, painter: QPainter, item: DiagramItem, rect: QRectF) -> None:
        node = item.node
        selected = node is not None and node is self._selected
        painter.save()
        font = painter.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() * self._zoom))
        painter.setFont(font)
        painter.setPen(QPen(self.palette().highlight().color() if selected else self.palette().mid().color(),
                            2 if selected else 1))
        painter.setBrush(self.palette().highlight() if selected else self.palette().window())
        painter.drawRoundedRect(rect, 5 * self._zoom, 5 * self._zoom)
        painter.setPen(self.palette().highlightedText().color() if selected else self.palette().text().color())
        if node is None:
            label = tr("tree_more", count=format_count(item.hidden_count),
                       size=format_size(item.hidden_size, self.unit))
            symbol = "+"
        else:
            label = node.name
            symbol = "!" if node.error is not None else (
                "−" if node is self._view_root or id(node) in self._expanded else "+")
        line = rect.adjusted(8 * self._zoom, 2 * self._zoom, -8 * self._zoom, -2 * self._zoom)
        painter.drawText(line, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, symbol)
        left = line.adjusted(17 * self._zoom, 0, 0, 0)
        name = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideMiddle, round(left.width()))
        painter.drawText(left, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, name)
        if node is not None:
            parent_size = node.parent.accounted_allocated if node.parent is not None else node.accounted_allocated
            share = format_share(node.accounted_allocated / parent_size) if parent_size else ""
            value = (tr("tree_unavailable") if node.error is not None
                     else f"{format_size(node.accounted_allocated, self.unit)}  {share}")
            painter.drawText(left, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, value)
        painter.restore()
