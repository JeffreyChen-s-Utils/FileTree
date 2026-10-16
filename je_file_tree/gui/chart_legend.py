"""Keep each chart legend entry intact while wrapping between entries."""

from __future__ import annotations

import html
from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLabel, QLayout, QLayoutItem, QSizePolicy, QWidget


class ChartLegend(QWidget):
    """A small flowing set of nonwrapping labels, with ordinary text and accessible names.

    Do not insert U+2060 to prevent CJK line breaks: native Windows measurements after
    warming the base font took 387.6–536.8 ms for a label containing that character,
    versus 0.07–0.43 ms for ordinary/nonbreaking-space/rich-text labels (2026-10-16).
    Keeping each entry in its own label preserves wrapping without that font fallback.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._flow = _LegendLayout(self)
        self._items: tuple[tuple[str, str], ...] = ()
        self._labels: list[QLabel] = []

    def set_items(self, items: Sequence[tuple[str, str]]) -> None:
        """Show color/text pairs in order; unchanged entries retain their existing widgets."""
        values = tuple(items)
        if values == self._items:
            return
        while (item := self._flow.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._items = values
        self._labels = []
        for colour, text in values:
            label = QLabel(self)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setText(f'<span style="color:{html.escape(colour, quote=True)}">&#9632;</span> {html.escape(text)}')
            label.setAccessibleName(text)
            label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self._flow.addWidget(label)
            label.show()
            self._labels.append(label)
        self.updateGeometry()

    def labels(self) -> tuple[QLabel, ...]:
        """The current ordered entry labels, excluding retired widgets awaiting deletion."""
        return tuple(self._labels)


class _LegendLayout(QLayout):
    """Lay out a bounded set of legend labels without splitting any entry."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self._entries: list[QLayoutItem] = []
        self._horizontal_gap = 12
        self._vertical_gap = 4

    def addItem(self, item: QLayoutItem) -> None:
        """Qt: append one item and invalidate cached geometry."""
        self._entries.append(item)
        self.invalidate()

    def count(self) -> int:
        """Qt: number of entry widgets."""
        return len(self._entries)

    def itemAt(self, index: int) -> QLayoutItem | None:
        """Qt: the entry at an index, or None when outside the layout."""
        return self._entries[index] if 0 <= index < len(self._entries) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        """Qt: remove an entry without destroying its widget."""
        if not 0 <= index < len(self._entries):
            return None
        item = self._entries.pop(index)
        self.invalidate()
        return item

    def expandingDirections(self) -> Qt.Orientation:
        """Qt: labels retain their natural size."""
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        """Qt: additional rows are needed when the pane narrows."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Qt: calculate the height without changing widget geometry."""
        return self._arrange(QRect(0, 0, width, 0), measure=True)

    def minimumSize(self) -> QSize:
        """Qt: reserve enough width for the longest complete entry."""
        size = QSize(0, 0)
        for item in self._entries:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def sizeHint(self) -> QSize:
        """Qt: let available width determine wrapping."""
        return self.minimumSize()

    def setGeometry(self, rect: QRect) -> None:
        """Qt: position entries using the same wrapping as heightForWidth."""
        super().setGeometry(rect)
        self._arrange(rect, measure=False)

    def _arrange(self, rect: QRect, *, measure: bool) -> int:
        margins = self.contentsMargins()
        content = rect.marginsRemoved(margins)
        x, y, row_height = content.x(), content.y(), 0
        for item in self._entries:
            size = item.sizeHint()
            if x > content.x() and x + size.width() > content.x() + content.width():
                x = content.x()
                y += row_height + self._vertical_gap
                row_height = 0
            if not measure:
                item.setGeometry(QRect(QPoint(x, y), size))
            x += size.width() + self._horizontal_gap
            row_height = max(row_height, size.height())
        return y + row_height + margins.bottom() - rect.y()
