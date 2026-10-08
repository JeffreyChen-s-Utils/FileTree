"""Accessible names/current-selection descriptions and bounded keyboard chart navigation."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QScrollArea

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui.node_text import node_path
from je_file_tree.gui.bar_chart import BarChartWidget
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.sunburst_widget import SunburstWidget
from je_file_tree.gui.tree_diagram import TreeDiagramWidget
from je_file_tree.gui.treemap_widget import TreemapWidget

Chart = TreemapWidget | BarChartWidget | SunburstWidget | TreeDiagramWidget
_NEXT_KEYS = (Qt.Key.Key_Down, Qt.Key.Key_Right)
_PREVIOUS_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Left)
_SHORTCUT_MODIFIERS = (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
                       | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier)


def _within(node: Node, root: Node) -> bool:
    above: Node | None = node
    while above is not None:
        if above is root:
            return True
        above = above.parent
    return False


class ChartAccessibility(QObject):
    """Expose a chart's current folder/entry while navigating only its bounded rendered nodes."""

    def __init__(self, chart: Chart, mode: str) -> None:
        super().__init__(chart)
        self.chart, self.mode = chart, mode
        chart.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        chart.installEventFilter(self)
        chart.node_clicked.connect(self._picked)
        chart.view_root_changed.connect(lambda _node: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        """Translate the accessible chart name, controls and current recorded selection facts."""
        chart = self.chart
        chart.setAccessibleName(tr(f'chart_{self.mode}'))
        root, node = chart.view_root, chart._selected
        controls = tr('chart_access_tree_keys' if isinstance(chart, TreeDiagramWidget) else 'chart_access_keys')
        description = controls
        if root is not None:
            description += '\n' + tr('chart_access_folder', path=node_path(root))
        if node is not None and root is not None and _within(node, root):
            description += '\n' + tr('chart_access_selected', path=node_path(node),
                                      size=format_size(node.size, chart.unit),
                                      allocated=format_size(node.allocated, chart.unit),
                                      files=format_count(node.file_count), folders=format_count(node.dir_count))
            if node.accounting is not None:
                description += (f"\n{tr('column_accounted_size')}: {format_size(node.accounted_size, chart.unit)}; "
                                f"{tr('column_accounted_allocated')}: "
                                f"{format_size(node.accounted_allocated, chart.unit)}")
        chart.setAccessibleDescription(description)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handle chart-only keys; modified shortcuts and Tree diagram's existing navigation pass through."""
        if event.type() == QEvent.Type.FocusIn:
            self.refresh()
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self.chart.invalidate()
        if (not isinstance(event, QKeyEvent) or event.type() != QEvent.Type.KeyPress
                or event.modifiers() & _SHORTCUT_MODIFIERS):
            return False
        chart, key = self.chart, event.key()
        if key == Qt.Key.Key_Backspace:
            chart.zoom_out()
        elif isinstance(chart, TreeDiagramWidget) and key in (*_NEXT_KEYS, *_PREVIOUS_KEYS):
            return False
        elif key in (*_NEXT_KEYS, *_PREVIOUS_KEYS):
            self._step(1 if key in _NEXT_KEYS else -1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            node = chart._selected
            if (node is not None and node.is_dir and not node.is_link and chart.view_root is not None
                    and _within(node, chart.view_root)):
                chart.set_view_root(node)
        else:
            return False
        event.accept()
        return True

    def _nodes(self) -> list[Node]:
        chart = self.chart
        root = chart.view_root
        if root is None:
            return []
        if isinstance(chart, BarChartWidget):
            nodes = chart._current_rows()
        elif isinstance(chart, SunburstWidget):
            nodes = [segment.node for segment in chart._current_segments()]
        elif isinstance(chart, TreeDiagramWidget):
            nodes = [row.node for row in chart.rows() if row.node is not None]
        else:
            if chart._pixmap is None and root.accounted_size > 0:
                chart._render()
            nodes = [tile.node for tile in chart._tiles if not tile.grouped]
        return list(dict.fromkeys((root, *nodes)))

    def _step(self, offset: int) -> None:
        nodes = self._nodes()
        if not nodes:
            return
        current = next((index for index, node in enumerate(nodes) if node is self.chart._selected),
                       -1 if offset > 0 else len(nodes))
        position = max(0, min(len(nodes) - 1, current + offset))
        node = nodes[position]
        self.chart.set_selected(node)
        self.chart.node_clicked.emit(node)

    def _picked(self, node: Node) -> None:
        self.refresh()
        bounds = self._bounds(node)
        scroll = self.chart.parentWidget()
        while scroll is not None and not isinstance(scroll, QScrollArea):
            scroll = scroll.parentWidget()
        if isinstance(scroll, QScrollArea) and bounds is not None:
            scroll.ensureVisible(round(bounds.center().x()), round(bounds.center().y()), 20, 20)

    def _bounds(self, node: Node) -> QRectF | None:
        chart = self.chart
        if isinstance(chart, BarChartWidget):
            rows = chart._current_rows()
            if node in rows:
                return chart._line_rect(rows.index(node))
        if isinstance(chart, TreeDiagramWidget):
            row = next((row for row in chart.rows() if row.node is node), None)
            if row is not None:
                return chart.card_rect(row)
        return None
