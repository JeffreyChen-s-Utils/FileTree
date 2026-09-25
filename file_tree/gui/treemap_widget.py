"""The treemap view: every file as a rectangle sized by how much space it takes.

The layout and the drawing are done once per size or folder change into a
cached pixmap; moving the mouse only draws the highlight on top, so hovering
stays smooth however many rectangles there are.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import QToolTip, QWidget

from file_tree.core.analysis import category_of, extension_of
from file_tree.core.formatting import format_share, format_size
from file_tree.core.node import Node
from file_tree.core.treemap import Rect, Tile, layout
from file_tree.gui.i18n import tr

# One colour per file-type group (every key of analysis.CATEGORIES), readable on
# light and dark themes alike.
CATEGORY_COLOURS: dict[str, str] = {
    "images": "#4e9a06",
    "video": "#c4a000",
    "audio": "#75507b",
    "documents": "#3465a4",
    "archives": "#ce5c00",
    "code": "#06989a",
    "programs": "#c0504d",
    "other": "#a08c6e",
}
_FOLDER_COLOURS = ("#d3d7cf", "#babdb6", "#a4a8a0")
_MAX_DEPTH = 8
_LABEL_MIN_WIDTH = 48
_LABEL_MIN_HEIGHT = 16
_SHADE_MIN_SIDE = 12


def colour_for(node: Node) -> QColor:
    """The fill colour of a file tile (by file type) or a folder tile (by depth)."""
    if node.is_dir:
        return QColor(_FOLDER_COLOURS[node.depth % len(_FOLDER_COLOURS)])
    return QColor(CATEGORY_COLOURS[category_of(extension_of(node.name))])


class TreemapWidget(QWidget):
    """Draws the treemap of one folder; click selects, double-click opens a folder, right-click asks for a menu."""

    node_clicked = Signal(object)
    view_root_changed = Signal(object)
    context_menu_requested = Signal(object, QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 150)
        self._view_root: Node | None = None
        self._tiles: list[Tile] = []
        self._pixmap: QPixmap | None = None
        self._hover: Tile | None = None
        self._selected: Node | None = None

    @property
    def view_root(self) -> Node | None:
        """The folder the treemap currently shows."""
        return self._view_root

    def set_view_root(self, node: Node | None) -> None:
        """Show ``node`` (a folder) filling the whole widget."""
        if node is not None and not node.is_dir:
            node = node.parent
        self._view_root = node
        self._hover = None
        self.invalidate()
        self.view_root_changed.emit(node)

    def zoom_out(self) -> None:
        """Show the parent of the current folder."""
        if self._view_root is not None and self._view_root.parent is not None:
            self.set_view_root(self._view_root.parent)

    def set_selected(self, node: Node | None) -> None:
        """Outline ``node`` (the entry selected elsewhere in the window)."""
        self._selected = node
        self.update()

    def invalidate(self) -> None:
        """Lay out and draw again (after a deletion or a theme change)."""
        self._pixmap = None
        self._tiles = []
        self.update()

    def tile_at(self, x: float, y: float) -> Tile | None:
        """The innermost tile under a point."""
        for tile in reversed(self._tiles):
            if tile.rect.contains(x, y):
                return tile
        return None

    # --- Qt events ---------------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Qt: a new size needs a new layout."""
        self.invalidate()
        super().resizeEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Qt: the cached picture plus the hover and selection outlines."""
        painter = QPainter(self)
        if self._view_root is None or self._view_root.size <= 0:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("treemap_empty"))
            return
        if self._pixmap is None:
            self._render()
        if self._pixmap is not None:
            painter.drawPixmap(0, 0, self._pixmap)
        self._outline(painter, self._selected, QColor("#ffffff"), 3)
        self._outline(painter, self._selected, QColor("#000000"), 1)
        if self._hover is not None:
            self._outline(painter, self._hover.node, QColor(self.palette().highlight().color()), 2)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Qt: highlight the tile under the mouse and describe it in a tooltip."""
        point = event.position()
        tile = self.tile_at(point.x(), point.y())
        if tile is not self._hover:
            self._hover = tile
            self.update()
            if tile is None:
                QToolTip.hideText()
            else:
                QToolTip.showText(event.globalPosition().toPoint(), self._describe(tile.node), self)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Qt: drop the highlight when the mouse leaves."""
        self._hover = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Qt: a left click selects the entry under the mouse."""
        if event.button() == Qt.MouseButton.LeftButton:
            tile = self.tile_at(event.position().x(), event.position().y())
            if tile is not None:
                self.node_clicked.emit(tile.node)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Qt: a double click shows the folder under the mouse on its own."""
        tile = self.tile_at(event.position().x(), event.position().y())
        if tile is not None:
            target = tile.node if tile.node.is_dir else tile.node.parent
            if target is not None and target is not self._view_root:
                self.set_view_root(target)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Qt: ask the window for the menu of the entry under the mouse."""
        tile = self.tile_at(event.pos().x(), event.pos().y())
        self.context_menu_requested.emit(tile.node if tile else self._view_root, event.globalPos())

    # --- drawing -----------------------------------------------------------

    def _render(self) -> None:
        if self._view_root is None:
            return
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio)))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(self.palette().base().color())
        self._tiles = layout(self._view_root, Rect(0, 0, self.width(), self.height()), max_depth=_MAX_DEPTH)
        painter = QPainter(pixmap)
        border = QPen(QColor(0, 0, 0, 90))
        border.setWidthF(0.5)
        for tile in self._tiles:
            self._draw_tile(painter, tile, border)
        painter.end()
        self._pixmap = pixmap

    def _draw_tile(self, painter: QPainter, tile: Tile, border: QPen) -> None:
        rect = QRectF(tile.rect.x, tile.rect.y, tile.rect.width, tile.rect.height)
        colour = colour_for(tile.node)
        if min(rect.width(), rect.height()) >= _SHADE_MIN_SIDE and not tile.node.is_dir:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, colour.lighter(135))
            gradient.setColorAt(1.0, colour.darker(115))
            painter.setBrush(gradient)
        else:
            painter.setBrush(colour)
        painter.setPen(border)
        painter.drawRect(rect)
        if rect.width() >= _LABEL_MIN_WIDTH and rect.height() >= _LABEL_MIN_HEIGHT:
            painter.setPen(QColor("#000000") if tile.node.is_dir else QColor("#ffffff"))
            label = rect.adjusted(3, 1, -3, -1)
            flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            text = painter.fontMetrics().elidedText(tile.node.name, Qt.TextElideMode.ElideRight,
                                                    int(label.width()))
            painter.drawText(label, flags, text)

    def _outline(self, painter: QPainter, node: Node | None, colour: QColor, width: float) -> None:
        if node is None:
            return
        tile = next((tile for tile in self._tiles if tile.node is node), None)
        if tile is None:
            return
        pen = QPen(colour)
        pen.setWidthF(width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(tile.rect.x, tile.rect.y, tile.rect.width, tile.rect.height))

    def _describe(self, node: Node) -> str:
        share = node.size / self._view_root.size if self._view_root and self._view_root.size else 0.0
        return tr("treemap_tooltip", name=node.name, size=format_size(node.size),
                  share=format_share(share), path=node.path)
