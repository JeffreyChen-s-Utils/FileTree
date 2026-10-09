"""Compact scan totals and coverage state, rendered from already captured values."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QResizeEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr

_METRICS = ("size", "allocated", "files", "folders")
_COMPACT_WIDTH = 680


class ResultOverview(QWidget):
    """Display constant-time root counters; coverage never implies recoverable space."""

    problems_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root: Node | None = None
        self._state = "empty"
        self._errors = 0
        self.unit = "auto"
        self._columns = 0
        self.state = QLabel()
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        self.problems = QPushButton()
        self.problems.clicked.connect(self.problems_requested)
        self.cards: list[QFrame] = []
        self.captions: list[QLabel] = []
        self.values: list[QLabel] = []
        self._grid = QGridLayout()
        for _key in _METRICS:
            self._add_card()
        row = QHBoxLayout()
        row.addWidget(self.state, 1)
        row.addWidget(self.problems)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(row)
        layout.addLayout(self._grid)
        self.setStyleSheet("QFrame#scan_metric { background: palette(base); border: 1px solid palette(mid);"
                           " border-radius: 6px; }"
                           "QLabel#metric_caption { color: palette(placeholder-text); }")
        self._arrange()
        self.retranslate()

    def _add_card(self) -> None:
        card = QFrame()
        card.setObjectName("scan_metric")
        caption, value = QLabel(), QLabel()
        caption.setObjectName("metric_caption")
        for label in (caption, value):
            label.setTextFormat(Qt.TextFormat.PlainText)
        font = QFont(value.font())
        font.setPointSizeF(font.pointSizeF() * 1.45)
        font.setBold(True)
        value.setFont(font)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        column = QVBoxLayout(card)
        column.setContentsMargins(14, 8, 14, 10)
        column.setSpacing(2)
        column.addWidget(caption)
        column.addWidget(value)
        self.cards.append(card)
        self.captions.append(caption)
        self.values.append(value)

    def show_totals(self, root: Node | None, state: str, errors: int = 0) -> None:
        """Show a recorded root and explicit empty/live/complete/partial state without filesystem calls."""
        self._root, self._state, self._errors = root, state, errors
        self.retranslate()

    def retranslate(self) -> None:
        """Refresh values and their accessible labels using the current language."""
        self.state.setText(tr("overview_" + self._state))
        self.state.setToolTip(tr("overview_coverage_hint"))
        self.problems.setText(tr("overview_problems", count=format_count(self._errors)))
        self.problems.setVisible(self._errors > 0)
        root = self._root
        amounts = ((format_size(root.size, self.unit), format_size(root.allocated, self.unit),
                    format_count(root.file_count), format_count(root.dir_count)) if root is not None else ("—",) * 4)
        for key, caption, value, amount in zip(_METRICS, self.captions, self.values, amounts, strict=True):
            text = tr("overview_" + key)
            caption.setText(text)
            value.setText(amount)
            value.setAccessibleName(text)
            value.setAccessibleDescription(amount)
        self.cards[1].setToolTip(tr("overview_allocation_hint"))

    def _arrange(self) -> None:
        columns = 2 if self.width() < _COMPACT_WIDTH else 4
        if columns == self._columns:
            return
        self._columns = columns
        for index, card in enumerate(self.cards):
            self._grid.addWidget(card, index // columns, index % columns)
        for column in range(4):
            self._grid.setColumnStretch(column, int(column < columns))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Qt: keep counters readable in a narrow window."""
        super().resizeEvent(event)
        self._arrange()
