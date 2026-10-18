"""Accessible analysis navigation that follows the existing result-page indexes."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, QSize, QSignalBlocker, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QListWidget, QStyle, QTabWidget, QVBoxLayout, QWidget

from je_file_tree.gui.fluent_icons import palette_icon
from je_file_tree.gui.i18n import tr

_ICON_SIZE = 18
_ITEM_PADDING = 34  # the style sheet's 10 px item padding on both sides, 3 px accent bar and slack


class AnalysisTabs(QTabWidget):
    """Size the analysis pane for its active page; hidden search controls must not squeeze the tree."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.currentChanged.connect(lambda _index: self.updateGeometry())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt's name
        """Qt: retain the active page's controls without reserving every inactive page's width."""
        page = self.currentWidget()
        if page is None:
            return super().minimumSizeHint()
        frame = 2 * self.style().pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth)
        return page.minimumSizeHint() + QSize(frame, frame)


class ResultNavigation(QWidget):
    """Use a sidebar on wide windows and a compact chooser on narrow windows."""

    def __init__(self, tabs: QTabWidget, parent: QWidget | None = None, icons: Sequence[str] = ()) -> None:
        super().__init__(parent)
        self.tabs = tabs
        self._icon_names = tuple(icons)  # one fluent_icons name per page index, in page order
        self.list = QListWidget()
        self.list.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setObjectName("result_navigation")
        self.combo = QComboBox()
        self.list.currentRowChanged.connect(tabs.setCurrentIndex)
        self.combo.currentIndexChanged.connect(self._choose)
        tabs.currentChanged.connect(self._select)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.combo)
        self.compact = False
        self.set_compact(False)

    def refresh(self) -> None:
        """Copy labels/visibility from the fixed page registry, preserving the active view."""
        with QSignalBlocker(self.list), QSignalBlocker(self.combo):
            self.list.clear()
            self.combo.clear()
            for index in range(self.tabs.count()):
                text = self.tabs.tabText(index)
                self.list.addItem(text)
                item = self.list.item(index)
                item.setIcon(self._icon(index))
                item.setHidden(not self.tabs.isTabVisible(index))
                item.setToolTip(text)
                if self.tabs.isTabVisible(index):
                    self.combo.addItem(self._icon(index), text, index)
            self._select(self.tabs.currentIndex())
        self.list.setAccessibleName(tr("overview_navigation"))
        self.combo.setAccessibleName(tr("overview_navigation"))
        self.set_compact(self.compact)

    def set_compact(self, compact: bool) -> None:
        """Switch presentation without changing page selection or triggering analysis work."""
        self.compact = compact
        self.list.setVisible(not compact)
        self.combo.setVisible(compact)
        width = max(170, max((self.list.fontMetrics().horizontalAdvance(self.list.item(index).text())
                             for index in range(self.list.count())), default=110) + _ITEM_PADDING
                + (_ICON_SIZE + 8 if self._icon_names else 0))
        self.setMinimumWidth(0 if compact else min(width, 240))
        self.setMaximumWidth(16_777_215 if compact else min(width, 240))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt's name
        """Qt: repaint the page icons in the new palette's text colour (themes, high contrast)."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and self._icon_names:
            for index in range(self.list.count()):
                self.list.item(index).setIcon(self._icon(index))
            for row in range(self.combo.count()):
                self.combo.setItemIcon(row, self._icon(self.combo.itemData(row)))

    def _icon(self, index: int) -> QIcon:
        if not 0 <= index < len(self._icon_names):
            return QIcon()
        return palette_icon(self._icon_names[index], self.palette())

    def _choose(self, index: int) -> None:
        page = self.combo.itemData(index)
        if isinstance(page, int):
            self.tabs.setCurrentIndex(page)

    def _select(self, index: int) -> None:
        with QSignalBlocker(self.list), QSignalBlocker(self.combo):
            self.list.setCurrentRow(index)
            self.combo.setCurrentIndex(self.combo.findData(index))
