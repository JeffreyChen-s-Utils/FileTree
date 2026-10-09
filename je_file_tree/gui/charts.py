"""The Chart tab's four coordinated views of one folder, switched with buttons.

Every view shows the same folder: opening a folder in one (double-click) or going up moves them
all. ``ChartStack`` offers the views' own interface (``set_view_root``, ``view_root``, ``zoom_out``,
``set_selected``, ``invalidate`` and the three signals) so the results page drives it as one chart.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QScrollArea, QStackedWidget, QWidget

from je_file_tree.core.node import Node
from je_file_tree.gui.bar_chart import BarChartWidget
from je_file_tree.gui.sunburst_widget import SunburstWidget
from je_file_tree.gui.treemap_widget import TreemapWidget
from je_file_tree.gui.tree_diagram import TreeDiagramWidget
from je_file_tree.gui.chart_accessibility import ChartAccessibility

TREEMAP, BARS, SUNBURST, TREE = "treemap", "bars", "sunburst", "tree"
MODES = (TREEMAP, BARS, SUNBURST, TREE)
DEFAULT_MODE = TREEMAP  # the owner chose it as the first view


class ChartStack(QStackedWidget):
    """The chart views, one on screen at a time, all showing the same folder."""

    node_clicked = Signal(object)
    view_root_changed = Signal(object)
    context_menu_requested = Signal(object, QPoint)
    mode_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.treemap = TreemapWidget()
        self.bars = BarChartWidget()
        self.sunburst = SunburstWidget()
        self.tree = TreeDiagramWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.bars)
        tree_scroll = QScrollArea()
        tree_scroll.setWidgetResizable(False)
        tree_scroll.setWidget(self.tree)
        self._charts: dict[str, TreemapWidget | BarChartWidget | SunburstWidget | TreeDiagramWidget] = {
            TREEMAP: self.treemap, BARS: self.bars, SUNBURST: self.sunburst, TREE: self.tree}
        self._pages: dict[str, QWidget] = {TREEMAP: self.treemap, BARS: scroll,
                                           SUNBURST: self.sunburst, TREE: tree_scroll}
        self._access = {mode: ChartAccessibility(chart, mode) for mode, chart in self._charts.items()}
        for mode in MODES:
            chart = self._charts[mode]
            self.addWidget(self._pages[mode])
            chart.node_clicked.connect(self.node_clicked)
            chart.context_menu_requested.connect(self.context_menu_requested)
            chart.view_root_changed.connect(self._follow)
        self._root: Node | None = None
        self._moving = False
        self.set_mode(DEFAULT_MODE)

    @property
    def mode(self) -> str:
        """The view on screen: one of ``MODES``."""
        page = self.currentWidget()
        return next(mode for mode, widget in self._pages.items() if widget is page)

    def set_mode(self, mode: str) -> None:
        """Show the view ``mode`` (an unknown mode is ignored)."""
        if mode in self._pages:
            self.setCurrentWidget(self._pages[mode])
            self.mode_changed.emit(mode)

    def current_chart(self) -> QWidget:
        """The underlying drawing widget (including full bar rows beyond the scroll viewport)."""
        return self._charts[self.mode]

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
        for access in self._access.values():
            access.refresh()

    def invalidate(self) -> None:
        """Lay out and draw every view again."""
        for chart in self._charts.values():
            chart.invalidate()

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit`` where a view prints them."""
        for chart in self._charts.values():
            chart.unit = unit
            chart.invalidate()
        for access in self._access.values():
            access.refresh()

    def retranslate(self) -> None:
        """Refresh accessible names/descriptions and cached translated chart text."""
        for access in self._access.values():
            access.refresh()
        self.invalidate()

    def set_colour_mode(self, mode: str) -> None:
        """Apply the shared colour choice to both treemap tiles and sunburst arcs."""
        self.treemap.set_colour_mode(mode)
        self.sunburst.set_colour_mode(mode)

    def set_age_reference(self, now: float) -> None:
        """Freeze both age palettes at the current scan/analysis time."""
        for chart in (self.treemap, self.sunburst):
            chart.age_reference = now
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
                else:
                    chart.invalidate()
        finally:
            self._moving = False
        self._root = node
        self.view_root_changed.emit(node)
