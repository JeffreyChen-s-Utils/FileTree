"""The bar chart: one horizontal bar per entry of a folder, the largest first.

Easier to read exactly than the treemap: every entry has its name, its size and its share of the
folder in plain text, and the bars are scaled to the largest entry so small differences show. Only
the ``MAX_BARS`` largest entries get a bar; the rest share one line.
"""

from __future__ import annotations

import heapq

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QStyle, QToolTip, QWidget

from je_file_tree.core.analysis import category_of, extension_of
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_share, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.treemap_widget import CATEGORY_COLOURS

MAX_BARS = 100
_NAME_SHARE = 0.34  # of the width, at most _NAME_MAX pixels
_NAME_MAX = 280
_VALUE_WIDTH = 150
_GAP = 8
_FOLDER_COLOUR = "#5b8def"
_REST_COLOUR = "#9a9a9a"


def bar_colour(node: Node) -> QColor:
    """Folders in one colour, files in the colour of their type (the treemap's legend)."""
    if node.is_dir:
        return QColor(_FOLDER_COLOUR)
    return QColor(CATEGORY_COLOURS[category_of(extension_of(node.name))])


class BarChartWidget(QWidget):
    """Bars for the entries of one folder; click selects, double-click opens a folder, right-click asks for a menu."""

    node_clicked = Signal(object)
    view_root_changed = Signal(object)
    context_menu_requested = Signal(object, QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.unit = AUTO_UNIT
        self._view_root: Node | None = None
        self._rows: list[Node] | None = None  # None: to be read from the folder at the next paint
        self._rest: tuple[int, int] = (0, 0)  # entries without a bar: count, size
        self._hover: int | None = None
        self._selected: Node | None = None

    # --- the same interface as the treemap --------------------------------

    @property
    def view_root(self) -> Node | None:
        """The folder shown."""
        return self._view_root

    def set_view_root(self, node: Node | None) -> None:
        """Show the entries of ``node`` (a folder; a file shows its folder)."""
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
        """Outline ``node`` when it has a bar."""
        self._selected = node
        self.update()

    def invalidate(self) -> None:
        """Read the folder again (after a scan step, a deletion or a rescan)."""
        self._rows = None
        self.updateGeometry()
        self.update()

    def node_at(self, y: float) -> Node | None:
        """The entry whose bar is at height ``y`` (None on the summary line or below the bars)."""
        rows = self._current_rows()
        index = int(y // self._row_height())
        return rows[index] if 0 <= index < len(rows) else None

    # --- Qt -----------------------------------------------------------------

    def sizeHint(self) -> QSize:
        """Qt: one line per bar, plus one for the entries without a bar."""
        lines = len(self._current_rows()) + (1 if self._rest[0] else 0)
        return QSize(400, max(lines, 1) * self._row_height())

    def minimumSizeHint(self) -> QSize:
        """Qt: tall enough for every line, so a scroll area scrolls rather than squeezes."""
        return QSize(200, self.sizeHint().height())

    def paintEvent(self, event: QPaintEvent) -> None:
        """Qt: draw the bars."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        root = self._view_root
        if root is None:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("treemap_empty"))
            return
        rows = self._current_rows()
        if not rows:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("bars_empty_folder"))
            return
        largest = max(rows[0].accounted_size, 1)
        for index, node in enumerate(rows):
            self._draw_row(painter, index, node, node.accounted_size / largest, root.accounted_size)
        count, size = self._rest
        if count:
            label = tr("bars_more", count=format_count(count), size=format_size(size, self.unit))
            self._draw_line(painter, len(rows), label, None, min(size / largest, 1.0), size, root.accounted_size)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Qt: highlight the bar under the mouse and describe it in a tooltip."""
        node = self.node_at(event.position().y())
        index = None if node is None else int(event.position().y() // self._row_height())
        if index != self._hover:
            self._hover = index
            self.update()
            if node is None:
                QToolTip.hideText()
            else:
                QToolTip.showText(event.globalPosition().toPoint(), self._describe(node), self)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Qt: drop the highlight when the mouse leaves."""
        self._hover = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Qt: a left click selects the entry."""
        if event.button() == Qt.MouseButton.LeftButton:
            node = self.node_at(event.position().y())
            if node is not None:
                self.node_clicked.emit(node)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Qt: a double click on a folder shows its entries."""
        node = self.node_at(event.position().y())
        if node is not None and node.is_dir and not node.is_link:
            self.set_view_root(node)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Qt: ask the window for the menu of the entry under the mouse (or of the folder shown)."""
        node = self.node_at(event.pos().y())
        self.context_menu_requested.emit(node if node is not None else self._view_root, event.globalPos())

    # --- drawing -----------------------------------------------------------

    def _row_height(self) -> int:
        return self.fontMetrics().height() + 10

    def _current_rows(self) -> list[Node]:
        """The entries with a bar, the largest first (read from the folder when it changed)."""
        if self._rows is None:
            children = list(self._view_root.children) if self._view_root is not None else []
            self._rows = heapq.nlargest(MAX_BARS, children, key=lambda node: node.accounted_size)
            rest = len(children) - len(self._rows)
            total = sum(node.accounted_size for node in children)
            self._rest = (rest, total - sum(node.accounted_size for node in self._rows))
        return self._rows

    def _draw_row(self, painter: QPainter, index: int, node: Node, fraction: float, total: int) -> None:
        if index == self._hover:
            painter.fillRect(self._line_rect(index), self.palette().alternateBase())
        self._draw_line(painter, index, node.name, node, fraction, node.accounted_size, total)
        if node is self._selected:
            painter.setPen(self.palette().highlight().color())
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._line_rect(index).adjusted(1, 1, -1, -1))

    def _draw_line(self, painter: QPainter, index: int, label: str, node: Node | None,  # noqa: PLR0913
                   fraction: float, size: int, total: int) -> None:
        line = self._line_rect(index)
        height = line.height()
        name_width = min(self.width() * _NAME_SHARE, _NAME_MAX)
        icon_size = self.fontMetrics().height()
        text_colour = self.palette().text().color()
        if node is not None and node.is_dir:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            icon.paint(painter, int(line.x() + 4), int(line.y() + (height - icon_size) / 2), icon_size, icon_size)
        name_rect = QRectF(line.x() + icon_size + 8, line.y(), name_width - icon_size - 8, height)
        painter.setPen(text_colour)
        align = Qt.AlignmentFlag.AlignVCenter
        painter.drawText(name_rect, align | Qt.AlignmentFlag.AlignLeft,
                         self.fontMetrics().elidedText(label, Qt.TextElideMode.ElideMiddle, int(name_rect.width())))
        bar_left = name_width + _GAP
        bar_space = max(self.width() - bar_left - _VALUE_WIDTH - _GAP, 0)
        bar = QRectF(bar_left, line.y() + height * 0.2, max(bar_space * fraction, 1.0), height * 0.6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bar_colour(node) if node is not None else QColor(_REST_COLOUR))
        painter.drawRoundedRect(bar, 2, 2)
        share = format_share(size / total) if total else ""
        value = QRectF(self.width() - _VALUE_WIDTH, line.y(), _VALUE_WIDTH - 6, height)
        painter.setPen(text_colour)
        painter.drawText(value, align | Qt.AlignmentFlag.AlignRight, f"{format_size(size, self.unit)}   {share}")

    def _line_rect(self, index: int) -> QRectF:
        height = self._row_height()
        return QRectF(0, index * height, self.width(), height)

    def _describe(self, node: Node) -> str:
        root = self._view_root
        share = node.accounted_size / root.accounted_size if root is not None and root.accounted_size else 0.0
        return tr("treemap_tooltip", name=node.name, size=format_size(node.accounted_size, self.unit),
                  share=format_share(share), path=node.path)
