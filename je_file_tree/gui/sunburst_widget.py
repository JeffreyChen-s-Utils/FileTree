"""The sunburst view: the folder shown in the centre, each deeper level a ring, angles by size.

Colours follow the top-level folder (the entries of the folder shown), lighter the deeper
they are, so a folder's whole branch reads as one colour. The rings are drawn once into a
cached pixmap; the mouse only adds the highlight.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import QToolTip, QWidget

from je_file_tree.core.formatting import AUTO_UNIT, format_share, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.sunburst import Segment, layout, segment_at
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.age_colours import age_colour
from je_file_tree.gui.colours import readable_ink
from je_file_tree.gui.treemap_widget import BY_AGE, BY_FOLDER, BY_TYPE, COLOUR_MODES, colour_for

RINGS = 4  # at most; fewer when the tree is shallower, so the rings always fill the space
_GOLDEN = 0.618033988749895
_MARGIN = 6
_CENTRE_SHARE = 0.22  # of the radius
_LABEL_MIN_ARC = 60  # pixels of arc before a segment gets its name
_OUTSIDE = -1


class SunburstWidget(QWidget):
    """Draws the rings of one folder; click selects, double-click opens a folder, the centre goes up."""

    node_clicked = Signal(object)
    view_root_changed = Signal(object)
    context_menu_requested = Signal(object, QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 150)
        self.unit = AUTO_UNIT
        self._view_root: Node | None = None
        self._segments: list[Segment] = []
        self._pixmap: QPixmap | None = None
        self._hover: Segment | None = None
        self._selected: Node | None = None
        self._hues: dict[int, float] = {}
        self._rings = 1
        self._colours = BY_FOLDER
        self.age_reference = time.time()

    # --- the same interface as the treemap --------------------------------

    @property
    def colour_mode(self) -> str:
        """File-type, top-folder or recorded modified-age colouring."""
        return self._colours

    def set_colour_mode(self, mode: str) -> None:
        """Use a shared chart colouring mode and discard the cached drawing."""
        if mode in COLOUR_MODES:
            self._colours = mode
            self.invalidate()

    @property
    def view_root(self) -> Node | None:
        """The folder in the centre."""
        return self._view_root

    def set_view_root(self, node: Node | None) -> None:
        """Put ``node`` (a folder; a file puts its folder) in the centre."""
        if node is not None and not node.is_dir:
            node = node.parent
        self._view_root = node
        self._hover = None
        self.invalidate()
        self.view_root_changed.emit(node)

    def zoom_out(self) -> None:
        """Put the parent of the current folder in the centre."""
        if self._view_root is not None and self._view_root.parent is not None:
            self.set_view_root(self._view_root.parent)

    def set_selected(self, node: Node | None) -> None:
        """Outline ``node`` when it has an arc."""
        self._selected = node
        self.update()

    def invalidate(self) -> None:
        """Lay out and draw again."""
        self._pixmap = None
        self._segments = []
        self.update()

    def hit(self, x: float, y: float) -> Segment | Node | None:
        """What is at a point: an arc, the folder in the centre, or None."""
        ring = self._ring_at(x, y)
        if ring == 0:
            return self._view_root
        if ring == _OUTSIDE:
            return None
        centre = self._centre()
        fraction = (math.atan2(x - centre.x(), centre.y() - y) / (2 * math.pi)) % 1.0
        return segment_at(self._current_segments(), ring, fraction)

    # --- Qt -----------------------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Qt: a new size needs a new drawing."""
        self._pixmap = None
        super().resizeEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Qt: the cached rings plus the hover and selection outlines."""
        painter = QPainter(self)
        if self._view_root is None or self._view_root.size <= 0:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("treemap_empty"))
            return
        if self._pixmap is None:
            self._render()
        if self._pixmap is not None:
            painter.drawPixmap(0, 0, self._pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        selected = next((segment for segment in self._segments if segment.node is self._selected), None)
        for segment, colour, width in ((selected, QColor("#ffffff"), 3.0), (selected, QColor("#000000"), 1.0),
                                       (self._hover, self.palette().highlight().color(), 2.0)):
            if segment is not None:
                pen = QPen(colour)
                pen.setWidthF(width)
                painter.setPen(pen)
                painter.drawPath(self._path(segment))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Qt: highlight the arc under the mouse and describe it in a tooltip."""
        found = self.hit(event.position().x(), event.position().y())
        segment = found if isinstance(found, Segment) else None
        if segment is not self._hover:
            self._hover = segment
            self.update()
            if segment is None:
                QToolTip.hideText()
            else:
                QToolTip.showText(event.globalPosition().toPoint(), self._describe(segment.node), self)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Qt: drop the highlight when the mouse leaves."""
        self._hover = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Qt: a left click selects the entry, or goes up from the centre."""
        if event.button() == Qt.MouseButton.LeftButton:
            found = self.hit(event.position().x(), event.position().y())
            if isinstance(found, Segment):
                self.node_clicked.emit(found.node)
            elif found is not None:
                self.zoom_out()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Qt: a double click on a folder's arc puts that folder in the centre."""
        found = self.hit(event.position().x(), event.position().y())
        if isinstance(found, Segment) and found.node.is_dir and not found.node.is_link:
            self.set_view_root(found.node)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Qt: ask the window for the menu of the entry under the mouse (or of the folder in the centre)."""
        found = self.hit(event.pos().x(), event.pos().y())
        node = found.node if isinstance(found, Segment) else self._view_root
        self.context_menu_requested.emit(node, event.globalPos())

    # --- geometry -----------------------------------------------------------

    def _centre(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _radii(self) -> tuple[float, float]:
        """The radius of the centre disc and the width of one ring."""
        self._current_segments()  # sets how many rings there are
        outer = max(min(self.width(), self.height()) / 2 - _MARGIN, 10.0)
        inner = outer * _CENTRE_SHARE
        return inner, (outer - inner) / self._rings

    def _ring_at(self, x: float, y: float) -> int:
        """0 in the centre disc, 1.. on the rings, ``_OUTSIDE`` beyond them."""
        centre = self._centre()
        distance = math.hypot(x - centre.x(), y - centre.y())
        inner, ring = self._radii()
        if distance < inner:
            return 0
        index = int((distance - inner) // ring) + 1
        return index if index <= self._rings else _OUTSIDE

    def _current_segments(self) -> list[Segment]:
        if not self._segments and self._view_root is not None:
            self._segments = layout(self._view_root, max_depth=RINGS)
            self._rings = max((segment.depth for segment in self._segments), default=1)
            self._hues = {id(child): (index * _GOLDEN) % 1.0
                          for index, child in enumerate(sorted(self._view_root.children,
                                                               key=lambda node: node.size, reverse=True))}
        return self._segments

    def _path(self, segment: Segment) -> QPainterPath:
        """The ring piece of ``segment``: outer arc clockwise, inner arc back."""
        inner, ring = self._radii()
        low = inner + (segment.depth - 1) * ring
        high = low + ring
        centre = self._centre()
        start = 90.0 - segment.start * 360.0  # Qt: degrees counter-clockwise from three o'clock
        sweep = -segment.span * 360.0
        path = QPainterPath()
        path.arcMoveTo(QRectF(centre.x() - high, centre.y() - high, 2 * high, 2 * high), start)
        path.arcTo(QRectF(centre.x() - high, centre.y() - high, 2 * high, 2 * high), start, sweep)
        path.arcTo(QRectF(centre.x() - low, centre.y() - low, 2 * low, 2 * low), start + sweep, -sweep)
        path.closeSubpath()
        return path

    # --- drawing -----------------------------------------------------------

    def _render(self) -> None:
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio)))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(self.palette().base().color())
        painter = QPainter(pixmap)
        self.draw_vector(painter)
        painter.end()
        self._pixmap = pixmap

    def draw_vector(self, painter: QPainter) -> None:
        """Draw the bounded current rings directly, for lossless SVG output without a cached bitmap."""
        root = self._view_root
        if root is None or root.size <= 0:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("treemap_empty"))
            return
        painter.fillRect(self.rect(), self.palette().base())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = QPen(self.palette().base().color())
        border.setWidthF(1.0)
        inner, ring = self._radii()
        for segment in self._current_segments():
            painter.setPen(border)
            painter.setBrush(self._colour(segment))
            painter.drawPath(self._path(segment))
            radius = inner + (segment.depth - 0.5) * ring
            if segment.span * 2 * math.pi * radius >= _LABEL_MIN_ARC:
                self._draw_label(painter, segment, radius, ring)
        centre = self._centre()
        painter.setPen(self.palette().mid().color())
        painter.setBrush(self.palette().window())
        painter.drawEllipse(centre, inner - 2, inner - 2)
        painter.setPen(self.palette().text().color())
        box = QRectF(centre.x() - inner, centre.y() - inner, 2 * inner, 2 * inner).adjusted(6, 6, -6, -6)
        name = painter.fontMetrics().elidedText(root.name, Qt.TextElideMode.ElideMiddle, int(box.width()))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, f"{name}\n{format_size(root.size, self.unit)}")

    def _draw_label(self, painter: QPainter, segment: Segment, radius: float, ring: float) -> None:
        angle = (segment.start + segment.span / 2) * 2 * math.pi
        centre = self._centre()
        point = QPointF(centre.x() + radius * math.sin(angle), centre.y() - radius * math.cos(angle))
        width = min(segment.span * 2 * math.pi * radius, ring * 1.6)
        box = QRectF(point.x() - width / 2, point.y() - ring / 2, width, ring)
        painter.setPen(readable_ink(self._colour(segment)))
        text = painter.fontMetrics().elidedText(segment.node.name, Qt.TextElideMode.ElideRight, int(width))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def _colour(self, segment: Segment) -> QColor:
        if self._colours == BY_AGE:
            return age_colour(segment.node, self.age_reference)
        if self._colours == BY_TYPE:
            return colour_for(segment.node)
        top = segment.node
        while top.parent is not None and top.parent is not self._view_root:
            top = top.parent
        hue = self._hues.get(id(top), 0.0)
        saturation = 0.55 if segment.node.is_dir else 0.35
        return QColor.fromHsvF(hue, saturation, min(0.72 + 0.07 * segment.depth, 0.98))

    def _describe(self, node: Node) -> str:
        root = self._view_root
        share = node.size / root.size if root is not None and root.size else 0.0
        return tr("treemap_tooltip", name=node.name, size=format_size(node.size, self.unit),
                  share=format_share(share), path=node.path)
