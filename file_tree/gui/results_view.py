"""The results page: the folder tree on the left, and treemap / largest files / file types / problems on the right.

Selecting an entry anywhere selects it everywhere: in the tree (expanding the
folders above it), and outlined in the treemap. While a scan runs, the page
already shows its tree (``show_live_root``) under a progress bar and is
refreshed about once a second (``refresh_live``); the lists that need the whole
tree (largest files, file types) fill in when the scan ends.
"""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPoint, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSplitter,
    QTableView,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from file_tree.core.analysis import CATEGORIES, CategoryStat, category_stats, extension_stats, subtract_stats
from file_tree.core.formatting import format_count, format_size
from file_tree.core.node import Node
from file_tree.core.scanner import ScanProgress
from file_tree.gui.delegates import ShareBarDelegate
from file_tree.gui.i18n import format_duration, tr
from file_tree.gui.scan_bar import ScanBar
from file_tree.gui.scan_worker import ScanOutcome
from file_tree.gui.tables import SORT_ROLE, FileTypesModel, LargestFilesModel, ProblemsModel
from file_tree.gui.tree_model import NODE_ROLE, SHARE, SIZE, FolderTreeModel
from file_tree.gui.treemap_widget import CATEGORY_COLOURS, TreemapWidget

_LARGEST_SIZE_COLUMN = 1
# Name takes the remaining width; these are the other columns, in order.
_TREE_COLUMN_WIDTHS = {1: 80, 2: 110, 3: 70, 4: 70, 5: 125}
_LARGEST_COLUMN_WIDTHS = {0: 200, 1: 80, 3: 125}
_LARGEST_FOLDER_COLUMN = 2
_TYPES_SHARE_COLUMN = 3


class _FileTypesProxy(QSortFilterProxyModel):
    """Filters the file-type rows to one group."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.category = ""

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Qt: keep a row when no group is chosen or it belongs to the chosen one."""
        if not self.category:
            return True
        model = self.sourceModel()
        stat = model.row_at(source_row) if isinstance(model, FileTypesModel) else None
        return stat is not None and stat.category == self.category


class ResultsView(QWidget):
    """Shows one scan; asks the window for a context menu with ``node_menu_requested``."""

    node_menu_requested = Signal(object, QPoint)
    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree_model = FolderTreeModel(self)
        self.largest_model = LargestFilesModel(self)
        self.types_model = FileTypesModel(self)
        self.problems_model = ProblemsModel(self)
        self._categories: list[CategoryStat] = []
        self._outcome: ScanOutcome | None = None

        self.scan_bar = ScanBar()
        self._live_ticks = 0
        self.summary = QLabel()
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.tree = self._build_tree()
        self.treemap = TreemapWidget()
        self._treemap_up = QToolButton()
        self._treemap_path = QLabel()
        self._legend = QLabel()
        self._largest_filter = QLineEdit()
        self.largest_table, self._largest_proxy = self._build_table(self.largest_model, _LARGEST_SIZE_COLUMN)
        largest_header = self.largest_table.horizontalHeader()
        largest_header.setStretchLastSection(False)
        for column, width in _LARGEST_COLUMN_WIDTHS.items():
            self.largest_table.setColumnWidth(column, width)
        largest_header.setSectionResizeMode(_LARGEST_FOLDER_COLUMN, QHeaderView.ResizeMode.Stretch)
        self.largest_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # the end of a path says the most
        self._types_combo = QComboBox()
        self._types_proxy = _FileTypesProxy(self)
        self.types_table = self._build_types_table()
        self.problems_table, _ = self._build_table(self.problems_model, 0)
        self.tabs = QTabWidget()
        self._assemble()
        self.retranslate()

    # --- public API -------------------------------------------------------

    @property
    def outcome(self) -> ScanOutcome | None:
        """The scan shown."""
        return self._outcome

    def begin_scan(self) -> None:
        """Clear the page for a new scan and show the progress bar."""
        self._outcome = None
        self._live_ticks = 0
        self.tree_model.set_root(None)
        for model in (self.largest_model, self.types_model, self.problems_model):
            model.set_rows([])
        self._categories = []
        self.treemap.set_view_root(None)
        self.scan_bar.start()
        self._update_texts()

    def show_live_root(self, root: Node) -> None:
        """Show the tree a running scan is filling in."""
        self.tree_model.set_root(root, live=True)
        self.tree.expand(self.tree_model.index(0, 0))
        self.treemap.set_view_root(root)
        self.select_node(root)
        self._update_texts()

    def refresh_live(self) -> None:
        """Show what the running scan added since the last call (the treemap every third call)."""
        if not self.tree_model.live:
            return
        self._live_ticks += 1
        self.tree_model.refresh()
        if self._live_ticks % 3 == 0:
            self.treemap.invalidate()
        self.selection_changed.emit(self.selected_node())  # its size has grown too

    def show_progress(self, progress: ScanProgress) -> None:
        """Show the running scan's latest counts in the bar and the summary line."""
        self.scan_bar.show_progress(progress)
        if self._outcome is None:
            self.summary.setText(self._summary_text())

    def end_scan(self) -> None:
        """Hide the progress bar (the scan ended without a result to show)."""
        self.scan_bar.hide()
        if self._outcome is None:
            self.tree_model.set_root(None)
            self.treemap.set_view_root(None)

    def show_outcome(self, outcome: ScanOutcome) -> None:
        """Show a finished (or stopped) scan; folders opened while it ran stay open."""
        self._outcome = outcome
        root = outcome.result.root
        self.scan_bar.hide()
        if self.tree_model.root is root:
            self.tree_model.finish_live()
        else:
            self.tree_model.set_root(root)
            self.tree.expand(self.tree_model.index(0, 0))
        self.largest_model.set_rows(outcome.largest)
        self.types_model.set_rows(outcome.extensions)
        self.problems_model.set_rows(outcome.result.errors)
        self._categories = outcome.categories
        view_root = self.treemap.view_root
        self.treemap.set_view_root(view_root if view_root is not None and _is_under(view_root, root) else root)
        if self.selected_node() is None:
            self.select_node(root)
        self._update_texts()

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit``."""
        self.tree_model.set_unit(unit)
        for model in (self.largest_model, self.types_model):
            model.unit = unit
            model.refresh()

    def selected_node(self) -> Node | None:
        """The entry selected in the tree."""
        index = self.tree.currentIndex()
        return self.tree_model.node(index) if index.isValid() else None

    def select_node(self, node: Node) -> None:
        """Select ``node`` in the tree (expanding its folders), and outline it in the treemap."""
        index = self.tree_model.index_for(node)
        if not index.isValid():
            return
        parent = index.parent()
        while parent.isValid():
            self.tree.expand(parent)
            parent = parent.parent()
        self.tree.selectionModel().setCurrentIndex(
            index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.tree.scrollTo(index)

    def forget(self, node: Node) -> None:
        """Update every view after ``node`` was deleted from disk."""
        outcome = self._outcome
        if outcome is None:
            return
        view_root = self.treemap.view_root
        extensions = subtract_stats(self.types_model.rows(), extension_stats(node))
        self.tree_model.remove(node)
        root = outcome.result.root
        self.largest_model.set_rows([file for file in self.largest_model.rows() if _is_under(file, root)])
        self.types_model.set_rows(extensions)
        self._categories = category_stats(extensions)
        if view_root is not None and not _is_under(view_root, root):
            view_root = root
        self.treemap.set_view_root(view_root)
        self._update_texts()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self.tree_model.retranslate()
        for model in (self.largest_model, self.types_model, self.problems_model):
            model.refresh()
        self.scan_bar.retranslate()
        self._treemap_up.setText(tr("treemap_up"))
        self._treemap_up.setToolTip(tr("treemap_up_tip"))
        self._largest_filter.setPlaceholderText(tr("largest_filter"))
        self._fill_types_combo()
        self._update_texts()

    # --- building ---------------------------------------------------------

    def _build_tree(self) -> QTreeView:
        tree = QTreeView()
        tree.setModel(self.tree_model)
        tree.setUniformRowHeights(True)
        tree.setSortingEnabled(True)
        tree.sortByColumn(SIZE, Qt.SortOrder.DescendingOrder)
        tree.setAlternatingRowColors(True)
        tree.setItemDelegateForColumn(SHARE, ShareBarDelegate(tree))
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(lambda point: self._menu_for(tree, point))
        header = tree.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        for column, width in _TREE_COLUMN_WIDTHS.items():
            tree.setColumnWidth(column, width)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.selectionModel().currentChanged.connect(self._tree_current_changed)
        return tree

    def _build_table(self, model: LargestFilesModel | ProblemsModel,
                     size_column: int) -> tuple[QTableView, QSortFilterProxyModel]:
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(model)
        proxy.setSortRole(SORT_ROLE)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxy.setFilterKeyColumn(-1)
        table = _table(proxy)
        table.sortByColumn(size_column, Qt.SortOrder.DescendingOrder if size_column else Qt.SortOrder.AscendingOrder)
        table.customContextMenuRequested.connect(lambda point: self._menu_for(table, point))
        table.doubleClicked.connect(lambda index: self._table_activated(table, index))
        return table, proxy

    def _build_types_table(self) -> QTableView:
        self._types_proxy.setSourceModel(self.types_model)
        self._types_proxy.setSortRole(SORT_ROLE)
        table = _table(self._types_proxy)
        table.setItemDelegateForColumn(_TYPES_SHARE_COLUMN, ShareBarDelegate(table))
        table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._types_combo.currentIndexChanged.connect(self._types_category_changed)
        return table

    def _assemble(self) -> None:
        self._largest_filter.setClearButtonEnabled(True)
        self._largest_filter.textChanged.connect(self._largest_proxy.setFilterFixedString)
        self._treemap_up.clicked.connect(self.treemap.zoom_out)
        self._treemap_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._legend.setWordWrap(True)
        self.treemap.node_clicked.connect(self._treemap_clicked)
        self.treemap.view_root_changed.connect(self._treemap_root_changed)
        self.treemap.context_menu_requested.connect(self._emit_menu)

        self.tabs.addTab(_column(_row(self._treemap_up, self._treemap_path), self.treemap, self._legend), "")
        self.tabs.addTab(_column(self._largest_filter, self.largest_table), "")
        self.tabs.addTab(_column(self._types_combo, self.types_table), "")
        self.tabs.addTab(self.problems_table, "")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 500])
        self.splitter = splitter
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.scan_bar)
        layout.addWidget(self.summary)
        layout.addWidget(splitter, 1)

    # --- reactions --------------------------------------------------------

    def _tree_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        node = self.tree_model.node(current)
        self.treemap.set_selected(node)
        self.selection_changed.emit(node)

    def _treemap_clicked(self, node: Node) -> None:
        self.select_node(node)

    def _treemap_root_changed(self, node: Node | None) -> None:
        self._treemap_path.setText(node.path if node is not None else "")
        self._treemap_up.setEnabled(node is not None and node.parent is not None)

    def _table_activated(self, table: QTableView, index: QModelIndex) -> None:
        node = index.data(NODE_ROLE)
        if isinstance(node, Node):
            self.select_node(node)

    def _menu_for(self, view: QAbstractItemView, point: QPoint) -> None:
        index = view.indexAt(point)
        node = index.data(NODE_ROLE) if index.isValid() else None
        if isinstance(node, Node):
            self._emit_menu(node, view.viewport().mapToGlobal(point))

    def _emit_menu(self, node: Node | None, point: QPoint) -> None:
        if node is not None:
            self.node_menu_requested.emit(node, point)

    def _types_category_changed(self, _position: int) -> None:
        self._types_proxy.category = self._types_combo.currentData() or ""
        self._types_proxy.invalidate()

    # --- texts ------------------------------------------------------------

    def _fill_types_combo(self) -> None:
        current = self._types_combo.currentData()
        self._types_combo.blockSignals(True)
        self._types_combo.clear()
        self._types_combo.addItem(tr("types_all"), "")
        for category in CATEGORIES:
            self._types_combo.addItem(tr(f"category_{category}"), category)
        position = self._types_combo.findData(current) if current else 0
        self._types_combo.setCurrentIndex(max(0, position))
        self._types_combo.blockSignals(False)

    def _update_texts(self) -> None:
        errors = len(self._outcome.result.errors) if self._outcome else 0
        titles = ("tab_treemap", "tab_largest", "tab_types")
        for position, key in enumerate(titles):
            self.tabs.setTabText(position, tr(key))
        self.tabs.setTabText(3, tr("tab_problems_count", count=errors) if errors else tr("tab_problems"))
        self._legend.setText(self._legend_html())
        self.summary.setText(self._summary_text())

    def _summary_text(self) -> str:
        outcome = self._outcome
        root = outcome.result.root if outcome is not None else self.tree_model.root
        if root is None:
            return ""
        values = {"path": root.path, "size": format_size(root.size), "files": format_count(root.file_count),
                  "folders": format_count(root.dir_count)}
        if outcome is None:
            return tr("summary_live", **values)
        key = "summary_partial" if outcome.partial else "summary"
        return tr(key, time=format_duration(outcome.result.elapsed), **values)

    def _legend_html(self) -> str:
        sizes = {stat.category: stat.size for stat in self._categories}
        parts = []
        for category in CATEGORIES:
            size = sizes.get(category)
            if size is None:
                continue
            colour = CATEGORY_COLOURS[category]
            label = _unbreakable(f"\u00a0{tr(f'category_{category}')} ({format_size(size)})")
            parts.append(f'<span style="color:{colour}">&#9632;</span>\u2060{label}')
        return " &nbsp; ".join(parts)



def _unbreakable(text: str) -> str:
    """``text`` that a line break can never split.

    Chinese may break between any two characters and Qt ignores ``<nobr>`` and
    ``white-space: nowrap`` for that, so spaces become no-break spaces and a
    word joiner (U+2060) goes between every two characters.
    """
    return "\u2060".join(text.replace(" ", "\u00a0"))


def _is_under(node: Node, root: Node) -> bool:
    top = node
    while top.parent is not None:
        top = top.parent
    return top is root


def _table(model: QSortFilterProxyModel) -> QTableView:
    table = QTableView()
    table.setModel(model)
    table.setSortingEnabled(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(table.fontMetrics().height() + 6)
    table.horizontalHeader().setStretchLastSection(True)
    table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    return table


def _row(*widgets: QWidget) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return box


def _column(*widgets: QWidget) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 4, 0, 0)
    for widget in widgets:
        layout.addWidget(widget, 1 if isinstance(widget, (QTableView, TreemapWidget)) else 0)
    return box

