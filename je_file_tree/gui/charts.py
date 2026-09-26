"""The Chart tab's views of one folder: the treemap and the bar chart, switched with a button.

Every view shows the same folder: opening a folder in one (double-click) or going up moves them
all. ``ChartStack`` offers the views' own interface (``set_view_root``, ``view_root``, ``zoom_out``,
``set_selected``, ``invalidate`` and the three signals) so the results page drives it as one chart.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QScrollArea, QStackedWidget, QWidget

from je_file_tree.core.node import Node
from je_file_tree.gui.bar_chart import BarChartWidget
from je_file_tree.gui.treemap_widget import TreemapWidget

TREEMAP, BARS = "treemap", "bars"
MODES = (TREEMAP, BARS)


class ChartStack(QStackedWidget):
    """The chart views, one on screen at a time, all showing the same folder."""

    node_clicked = Signal(object)
    view_root_changed = Signal(object)
    context_menu_requested = Signal(object, QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.treemap = TreemapWidget()
        self.bars = BarChartWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.bars)
        self._charts: dict[str, TreemapWidget | BarChartWidget] = {TREEMAP: self.treemap, BARS: self.bars}
        self._pages = {TREEMAP: self.treemap, BARS: scroll}
        for mode in MODES:
            chart = self._charts[mode]
            self.addWidget(self._pages[mode])
            chart.node_clicked.connect(self.node_clicked)
            chart.context_menu_requested.connect(self.context_menu_requested)
            chart.view_root_changed.connect(self._follow)
        self._root: Node | None = None
        self._moving = False

    @property
    def mode(self) -> str:
        """The view on screen: one of ``MODES``."""
        page = self.currentWidget()
        return next(mode for mode, widget in self._pages.items() if widget is page)

    def set_mode(self, mode: str) -> None:
        """Show the view ``mode`` (an unknown mode is ignored)."""
        if mode in self._pages:
            self.setCurrentWidget(self._pages[mode])

    @property
    def view_root(self) -> Node | None:
        """The folder every view shows."""
        return self._root

    def set_view_root(self, node: Node | None) -> None:
        """Show ``node`` (a folder; a file shows its folder) in every view."""
        self._charts[TREEMAP].set_view_root(node)  # the others follow through _follow

    def zoom_out(self) -> None:
        """Show the parent of the current folder."""
        if self._root is not None and self._root.parent is not None:
            self.set_view_root(self._root.parent)

    def set_selected(self, node: Node | None) -> None:
        """Outline ``node`` in every view."""
        for chart in self._charts.values():
            chart.set_selected(node)

    def invalidate(self) -> None:
        """Lay out and draw every view again."""
        for chart in self._charts.values():
            chart.invalidate()

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit`` where a view prints them."""
        for chart in self._charts.values():
            chart.unit = unit
            chart.invalidate()

    def _follow(self, node: Node | None) -> None:
        """One view moved to ``node``: move the others along, then tell the page once."""
        if self._moving:
            return
        self._moving = True
        try:
            for chart in self._charts.values():
                if chart.view_root is not node:
                    chart.set_view_root(node)
        finally:
            self._moving = False
        self._root = node
        self.view_root_changed.emit(node)
