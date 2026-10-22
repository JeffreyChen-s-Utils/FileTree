"""The treemap view: every file as a rectangle sized by how much space it takes.

The layout and the drawing are done once per size or folder change into a
cached pixmap; moving the mouse only draws the highlight on top, so hovering
stays smooth however many rectangles there are.

To stay readable it draws ``levels`` levels below the folder shown (2 unless
chosen otherwise; a folder at the last level is one tile), gives each opened
folder a header strip with its name and size, prints sizes in the tiles that
have room, and can colour by file type or by top-level folder. No tile is
smaller than ``MIN_SIDE``: the entries of a folder too small for that share one
grey, hatched tile ("12 more"), instead of a mass of specks.
"""

from __future__ import annotations

import html
import time

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import QApplication, QToolTip, QWidget

from je_file_tree.core.analysis import category_of, extension_of
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_share, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui.node_text import node_name, node_path
from je_file_tree.core.treemap import Rect, Tile, layout
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.age_colours import age_colour
from je_file_tree.gui.colours import blend, readable_ink

# One flat colour per file-type group (every key of analysis.CATEGORIES): evenly bright hues
# that read on light and dark surfaces alike; labels pick black or white by contrast.
CATEGORY_COLOURS: dict[str, str] = {
    "images": "#3fa34d",
    "video": "#e0a526",
    "audio": "#8e6cc8",
    "documents": "#3b82c4",
    "archives": "#e07a3a",
    "code": "#1fa2a8",
    "programs": "#d9534f",
    "other": "#9a8f80",
}
_FOLDER_SHADES = (.10, .16, .22)  # text colour laid over the surface, by folder depth
LEVELS = (1, 2, 3, 4, 8)  # 8: every level worth drawing
DEFAULT_LEVELS = 2
BY_TYPE, BY_FOLDER, BY_AGE = "type", "folder", "age"
COLOUR_MODES = (BY_TYPE, BY_FOLDER, BY_AGE)
_GOLDEN = 0.618033988749895  # hue step that keeps neighbouring folders apart
MIN_SIDE = 14  # px: a tile smaller than this is hard to see or point at, so it joins its folder's group
_GROUP_HATCH_ALPHA = 40
_GAP = 1.0  # surface showing between neighbouring tiles
_ROUND_MIN_SIDE = 8  # tiles at least this wide and tall get rounded corners
_RADIUS = 2.0
_LABEL_MIN_WIDTH = 48
_LABEL_MIN_HEIGHT = 16


def colour_for(node: Node, palette: QPalette | None = None) -> QColor:
    """The fill colour of a file tile (by file type) or a folder tile (a shade of the surface, by depth)."""
    if node.is_dir:
        return folder_colour(node.depth, palette or QApplication.palette())
    return QColor(CATEGORY_COLOURS[category_of(extension_of(node.name))])


def _fill(painter: QPainter, rect: QRectF, brush: QColor | QBrush) -> None:
    """Fill a tile inset by half the gap on each side, rounded when it is large enough to show it."""
    inner = rect.adjusted(_GAP / 2, _GAP / 2, -_GAP / 2, -_GAP / 2)
    if inner.width() <= 0 or inner.height() <= 0:
        return
    painter.setPen(Qt.PenStyle.NoPen)  # labels leave their ink as the pen
    painter.setBrush(brush)
    rounded = min(inner.width(), inner.height()) >= _ROUND_MIN_SIDE
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, rounded)  # only corners need smoothing
    if rounded:
        painter.drawRoundedRect(inner, _RADIUS, _RADIUS)
    else:
        painter.drawRect(inner)


def folder_colour(depth: int, palette: QPalette) -> QColor:
    """A neutral folder fill that follows the theme: the text colour faintly over the base surface."""
    shade = _FOLDER_SHADES[depth % len(_FOLDER_SHADES)]
    return blend(palette.color(QPalette.ColorRole.Text), palette.color(QPalette.ColorRole.Base), shade)


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
        self._shades: list[QColor] = []
        self._inks: dict[int, QColor] = {}
        self._pixmap: QPixmap | None = None
        self._hover: Tile | None = None
        self._selected: Node | None = None
        self.unit = AUTO_UNIT
        self._levels = DEFAULT_LEVELS
        self._colours = BY_TYPE
        self.age_reference = time.time()
        self._hues: dict[int, float] = {}

    @property
    def levels(self) -> int:
        """How many levels below the folder shown are drawn."""
        return self._levels

    def set_levels(self, levels: int) -> None:
        """Draw ``levels`` levels below the folder shown (one of ``LEVELS``; others are ignored)."""
        if levels in LEVELS:
            self._levels = levels
            self.invalidate()

    @property
    def colour_mode(self) -> str:
        """File-type, top-folder or recorded modified-age colouring."""
        return self._colours

    def set_colour_mode(self, mode: str) -> None:
        """Use one of ``COLOUR_MODES``; ignore unknown saved preferences."""
        if mode in COLOUR_MODES:
            self._colours = mode
            self.invalidate()

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
        if self._view_root is None or self._view_root.accounted_size <= 0:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("treemap_empty"))
            return
        if self._pixmap is None:
            self._render()
        if self._pixmap is not None:
            painter.drawPixmap(0, 0, self._pixmap)
        selected = self._tile_of(self._selected)
        self._outline(painter, selected, QColor("#ffffff"), 3)
        self._outline(painter, selected, QColor("#000000"), 1)
        self._outline(painter, self._hover, QColor(self.palette().highlight().color()), 2)

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
                QToolTip.showText(event.globalPosition().toPoint(), self._describe(tile), self)
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
        self._tiles = layout(self._view_root, Rect(0, 0, self.width(), self.height()), max_depth=self._levels,
                             min_side=MIN_SIDE, header=self._line_height() + 2)
        self._hues = {id(child): (index * _GOLDEN) % 1.0 for index, child in enumerate(self._view_root.children)}
        # Per render: shades and label inks repeat across tiles, so each is computed once. Native, 1,259
        # tiles: 55–66 ms recomputing them per tile, 30–37 ms cached (old gradient drawing 36–41 ms).
        self._shades = [folder_colour(depth, self.palette()) for depth in range(len(_FOLDER_SHADES))]
        self._inks = {}
        painter = QPainter(pixmap)
        for tile in self._tiles:
            self._draw_tile(painter, tile)
        painter.end()
        self._pixmap = pixmap

    def _draw_tile(self, painter: QPainter, tile: Tile) -> None:
        rect = QRectF(tile.rect.x, tile.rect.y, tile.rect.width, tile.rect.height)
        if tile.grouped:
            self._draw_group(painter, tile, rect)
            return
        node = tile.node
        colour = self._colour(node, tile.depth)
        ink = self._ink(colour)
        _fill(painter, rect, colour)
        if rect.width() < _LABEL_MIN_WIDTH or rect.height() < _LABEL_MIN_HEIGHT:
            return
        size = format_size(node.accounted_size, self.unit)
        painter.setPen(ink)
        if tile.header:
            strip = QRectF(rect.x() + 3, rect.y() + 2, rect.width() - 6, tile.header)
            self._draw_label(painter, strip, f"{node.name}  {size}", Qt.AlignmentFlag.AlignVCenter)
            return
        if node.is_dir and node.children and tile.depth < self._levels:
            return  # opened without room for a strip: its children cover it
        label = rect.adjusted(3, 1, -3, -1)
        self._draw_label(painter, label, node.name, Qt.AlignmentFlag.AlignTop)
        if label.height() >= 2 * self._line_height():
            self._draw_label(painter, label.adjusted(0, self._line_height(), 0, 0), size, Qt.AlignmentFlag.AlignTop)

    def _draw_group(self, painter: QPainter, tile: Tile, rect: QRectF) -> None:
        """A folder's entries too small for tiles of their own: one neutral, hatched tile saying how many."""
        fill = self._shades[(tile.depth + 1) % len(self._shades)]
        ink = self._ink(fill)
        _fill(painter, rect, fill)
        hatch = QColor(ink)
        hatch.setAlpha(_GROUP_HATCH_ALPHA)
        _fill(painter, rect, QBrush(hatch, Qt.BrushStyle.BDiagPattern))
        if rect.width() < _LABEL_MIN_WIDTH or rect.height() < _LABEL_MIN_HEIGHT:
            return
        painter.setPen(ink)
        label = rect.adjusted(3, 1, -3, -1)
        count = format_count(tile.grouped)
        text = tr("treemap_more", count=count)
        if painter.fontMetrics().horizontalAdvance(text) > label.width():
            text = f"+{count}"  # "+39" reads better than "39 m…"
        self._draw_label(painter, label, text, Qt.AlignmentFlag.AlignTop)
        if label.height() >= 2 * self._line_height():
            self._draw_label(painter, label.adjusted(0, self._line_height(), 0, 0),
                             format_size(tile.grouped_size, self.unit), Qt.AlignmentFlag.AlignTop)

    def _draw_label(self, painter: QPainter, area: QRectF, text: str, vertical: Qt.AlignmentFlag) -> None:
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(area.width()))
        painter.drawText(area, Qt.AlignmentFlag.AlignLeft | vertical, elided)

    def _line_height(self) -> int:
        return self.fontMetrics().height()

    def _ink(self, fill: QColor) -> QColor:
        """Black or white label ink for ``fill``, remembered for the rest of this render."""
        key = fill.rgb()
        ink = self._inks.get(key)
        if ink is None:
            ink = self._inks[key] = readable_ink(fill)
        return ink

    def _colour(self, node: Node, depth: int) -> QColor:
        """The fill of a tile: by file type (folders grey by depth), or by the hue of its top-level folder."""
        if self._colours == BY_TYPE:
            return self._shades[node.depth % len(self._shades)] if node.is_dir else colour_for(node)
        if self._colours == BY_AGE:
            return age_colour(node, self.age_reference)
        top = node
        while top.parent is not None and top.parent is not self._view_root:
            top = top.parent
        hue = self._hues.get(id(top), 0.0)
        if node.is_dir:
            return QColor.fromHsvF(hue, 0.28, max(0.95 - 0.07 * depth, 0.6))
        return QColor.fromHsvF(hue, 0.62, 0.82)

    def _tile_of(self, node: Node | None) -> Tile | None:
        """The tile of ``node`` itself (never a group tile of its entries), if it has one."""
        if node is None:
            return None
        return next((tile for tile in self._tiles if tile.node is node and not tile.grouped), None)

    def _outline(self, painter: QPainter, tile: Tile | None, colour: QColor, width: float) -> None:
        if tile is None:
            return
        pen = QPen(colour)
        pen.setWidthF(width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(tile.rect.x, tile.rect.y, tile.rect.width, tile.rect.height))

    def _describe(self, tile: Tile) -> str:
        node = tile.node
        size = tile.grouped_size if tile.grouped else node.accounted_size
        total = self._view_root.accounted_size if self._view_root else 0
        share = format_share(size / total if total else 0.0)
        if not tile.grouped:
            return tr("treemap_tooltip", name=html.escape(node_name(node)), size=format_size(size, self.unit),
                      share=share, path=html.escape(node_path(node)))
        text = tr("treemap_more_tooltip", count=format_count(tile.grouped), name=html.escape(node_name(node)),
                  size=format_size(size, self.unit), share=share)
        return text if node is self._view_root else f"{text}<br>{tr('treemap_more_open')}"
