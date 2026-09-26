"""Cell painters."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from je_file_tree.gui.tree_model import SHARE_ROLE

_BAR_MARGIN = 3


class ShareBarDelegate(QStyledItemDelegate):
    """Draws a cell's share (0..1, from ``SHARE_ROLE``) as a bar behind its percentage text."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: QModelIndex | QPersistentModelIndex) -> None:
        """Qt: the usual cell with a bar underneath the text."""
        share = index.data(SHARE_ROLE)
        style = option.widget.style() if option.widget is not None else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)
        if isinstance(share, float) and share > 0:
            area = QRectF(option.rect).adjusted(_BAR_MARGIN, _BAR_MARGIN, -_BAR_MARGIN, -_BAR_MARGIN)
            area.setWidth(max(1.0, area.width() * min(share, 1.0)))
            colour = QColor(option.palette.highlight().color())
            colour.setAlpha(110)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawRoundedRect(area, 2, 2)
            painter.restore()
        text_option = QStyleOptionViewItem(option)
        self.initStyleOption(text_option, index)
        text_option.backgroundBrush = QBrush()
        # The panel (selection, hover) is already drawn under the bar; drawing it
        # again with the text would cover the bar.
        text_option.state &= ~(QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver)
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, text_option, painter, option.widget)
