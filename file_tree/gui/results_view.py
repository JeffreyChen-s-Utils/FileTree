"""The results page: the folder tree on the left, and treemap / largest files / file types / problems on the right.

Selecting an entry anywhere selects it everywhere: in the tree (expanding the
folders above it), and outlined in the treemap. While a scan runs, the page
already shows its tree (``show_live_root``) under a progress bar and is
refreshed about once a second (``refresh_live``); the lists that need the whole
tree (largest files, file types) fill in when the scan ends.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Callable, Sequence

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPoint, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QPushButton,
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

from file_tree.core.analysis import (
    CATEGORIES,
    CategoryStat,
    Summary,
    age_of,
    age_stats,
    category_stats,
    extension_of,
    extension_stats,
    files_beneath,
    largest_matching,
    subtract_ages,
    subtract_stats,
)
from file_tree.core.formatting import format_count, format_size
from file_tree.core.node import Node
from file_tree.core.scanner import ScanProgress, ScanResult
from file_tree.gui import elevation
from file_tree.gui.delegates import ShareBarDelegate
from file_tree.gui.i18n import format_duration, tr
from file_tree.gui.scan_bar import ScanBar
from file_tree.gui.scan_worker import LARGEST_FILES_LIMIT, ScanOutcome
from file_tree.gui.search_panel import SearchPanel
from file_tree.gui.tables import SORT_ROLE, AgeModel, FileTypesModel, LargestFilesModel, ProblemsModel
from file_tree.gui.tree_model import (
    ALLOCATED,
    FILES,
    FOLDERS,
    MODIFIED,
    NODE_ROLE,
    SHARE,
    SIZE,
    FolderTreeModel,
)
from file_tree.gui.treemap_widget import CATEGORY_COLOURS, TreemapWidget

_LARGEST_SIZE_COLUMN = 1
# Name takes the remaining width; these are the other columns, in order.
_TREE_COLUMN_WIDTHS = {SIZE: 75, ALLOCATED: 75, SHARE: 95, FILES: 55, FOLDERS: 65, MODIFIED: 120}
_LARGEST_COLUMN_WIDTHS = {0: 200, 1: 80, 3: 125}
_LARGEST_FOLDER_COLUMN = 2
_PROBLEM_COLUMN_WIDTH = 220
_TYPES_SHARE_COLUMN = 3
_AGE_SHARE_COLUMN = 2
TREEMAP_TAB, LARGEST_TAB, SEARCH_TAB, TYPES_TAB, AGE_TAB, PROBLEMS_TAB = range(6)


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
    """Shows one scan; asks the window for a context menu with ``node_menu_requested``.

    ``node_menu_requested(node, picked, point)``: ``node`` is the entry under the mouse, ``picked`` the
    entries a *Move to Recycle Bin* in that menu acts on (the selection when ``node`` is part of it).
    """

    node_menu_requested = Signal(object, object, QPoint)
    selection_changed = Signal(object)
    elevate_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree_model = FolderTreeModel(self)
        self.largest_model = LargestFilesModel(self)
        self.types_model = FileTypesModel(self)
        self.problems_model = ProblemsModel(self)
        self.age_model = AgeModel(self)
        self._largest_all: list[Node] = []
        self._focus: tuple[str, str] | None = None  # ("type" | "age", value) the largest list shows
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
        self._focus_label = QLabel()
        self._show_all = QPushButton()
        self._focus_bar = _row(self._focus_label, self._show_all)
        self.largest_table, self._largest_proxy = self._build_entries_table(self.largest_model)
        self.search_model = LargestFilesModel(self)
        self.search_table, _ = self._build_entries_table(self.search_model)
        self.search = SearchPanel(self.search_table, self.search_model)
        self._types_combo = QComboBox()
        self._types_proxy = _FileTypesProxy(self)
        self.types_table = self._build_types_table()
        self.age_table = self._build_age_table()
        self.problems_table, _ = self._build_table(self.problems_model, 0)
        problems_header = self.problems_table.horizontalHeader()
        problems_header.setStretchLastSection(False)
        problems_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.problems_table.setColumnWidth(1, _PROBLEM_COLUMN_WIDTH)
        self.problems_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._problems_hint = QLabel()
        self._elevate_button = QPushButton()
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
        self.search.set_root(None)
        self._live_ticks = 0
        self.tree_model.set_root(None)
        for model in (self.largest_model, self.types_model, self.problems_model, self.age_model):
            model.set_rows([])
        self._largest_all = []
        self._focus = None
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
        self._largest_all = list(outcome.largest)
        self._focus = None
        self.largest_model.set_rows(self._largest_all)
        self.types_model.set_rows(outcome.extensions)
        self.age_model.set_rows(outcome.ages)
        self.problems_model.set_rows(outcome.result.errors)
        self._categories = outcome.categories
        view_root = self.treemap.view_root
        self.treemap.set_view_root(view_root if view_root is not None and _is_under(view_root, root) else root)
        if self.selected_node() is None:
            self.select_node(root)
        self.search.set_root(root)
        self._update_texts()
        self.selection_changed.emit(self.selected_node())  # its size is final now

    def replace_branch(self, old: Node, fresh: ScanResult) -> Node:
        """Put a rescan of the folder ``old`` in its place; returns the new node.

        The tree, the treemap, the problems and the summary change at once; the
        lists that need the whole tree follow with ``apply_summary``.
        """
        new = fresh.root
        view_root = self.treemap.view_root
        inside_old = view_root is not None and _is_within(view_root, old)
        prefix = old.path.rstrip("\\/") + os.sep
        self.tree_model.replace(old, new)
        if self._outcome is not None:
            errors = self._outcome.result.errors
            errors[:] = [error for error in errors if error[0] != old.path and not error[0].startswith(prefix)]
            errors.extend(fresh.errors)
            self.problems_model.set_rows(errors)
        self.treemap.set_view_root(new if inside_old else view_root)
        self.search.rerun()
        self._update_texts()
        self.selection_changed.emit(self.selected_node())
        return new

    def apply_summary(self, summary: Summary) -> None:
        """Show recomputed largest files and per-type and per-age totals for the tree on screen."""
        outcome = self._outcome
        if outcome is None:
            return
        root = outcome.result.root
        largest = [node for node in summary.largest if _is_under(node, root)]
        self._outcome = dataclasses.replace(outcome, largest=largest, extensions=summary.extensions,
                                            categories=category_stats(summary.extensions), ages=summary.ages,
                                            now=summary.now)
        self._largest_all = list(largest)
        self._focus = None
        self._focus_bar.hide()
        self.largest_model.set_rows(self._largest_all)
        self.types_model.set_rows(summary.extensions)
        self.age_model.set_rows(summary.ages)
        self._categories = self._outcome.categories
        self._update_texts()

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit``."""
        self.tree_model.set_unit(unit)
        for model in (self.largest_model, self.types_model, self.age_model, self.search_model):
            model.unit = unit
            model.refresh()
        self.search.retranslate()

    def selected_node(self) -> Node | None:
        """The entry the tree's cursor is on."""
        index = self.tree.currentIndex()
        return self.tree_model.node(index) if index.isValid() else None

    def selected_nodes(self) -> list[Node]:
        """Every entry selected in the tree (Ctrl+click and Shift+click pick several)."""
        return _selected_in(self.tree)

    def focused_selection(self) -> list[Node]:
        """The entries selected where the keyboard is: the largest-files or search list if focused, else the tree."""
        for table in (self.largest_table, self.search_table):
            if table.hasFocus():
                return _selected_in(table)
        return _selected_in(self.tree)

    def show_search(self) -> None:
        """Bring the Search tab forward with the cursor in its box."""
        self.tabs.setCurrentIndex(SEARCH_TAB)
        self.search.focus()

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

    def forget(self, nodes: Sequence[Node]) -> None:
        """Update every view after ``nodes`` were deleted from disk (none of them inside another)."""
        outcome = self._outcome
        if outcome is None:
            return
        view_root = self.treemap.view_root
        extensions = self.types_model.rows()
        ages = self.age_model.rows()
        for node in nodes:
            extensions = subtract_stats(extensions, extension_stats(node))
            ages = subtract_ages(ages, age_stats(files_beneath(node), outcome.now))
            self.tree_model.remove(node)
        root = outcome.result.root
        self._largest_all = [file for file in self._largest_all if _is_under(file, root)]
        self.largest_model.set_rows([file for file in self.largest_model.rows() if _is_under(file, root)])
        self.types_model.set_rows(extensions)
        self.age_model.set_rows(ages)
        self._categories = category_stats(extensions)
        if view_root is not None and not _is_under(view_root, root):
            view_root = root
        self.treemap.set_view_root(view_root)
        self.search.rerun()
        self._update_texts()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self.tree_model.retranslate()
        for model in (self.largest_model, self.types_model, self.problems_model, self.age_model):
            model.refresh()
        self._show_all.setText(tr("largest_show_all"))
        self.types_table.setToolTip(tr("list_files_tip"))
        self.age_table.setToolTip(tr("list_files_tip"))
        self.scan_bar.retranslate()
        self._treemap_up.setText(tr("treemap_up"))
        self._treemap_up.setToolTip(tr("treemap_up_tip"))
        self._largest_filter.setPlaceholderText(tr("largest_filter"))
        self.search.retranslate()
        self._problems_hint.setText(tr("problems_hint"))
        self._elevate_button.setText(tr("action_elevate"))
        self._elevate_button.setToolTip(tr("action_elevate_tip"))
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
        tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
        tree.selectionModel().selectionChanged.connect(lambda *_: self.selection_changed.emit(self.selected_node()))
        return tree

    def _build_entries_table(self, model: LargestFilesModel) -> tuple[QTableView, QSortFilterProxyModel]:
        """A list of entries (name, size, folder, modified) in which several rows can be selected."""
        table, proxy = self._build_table(model, _LARGEST_SIZE_COLUMN)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        for column, width in _LARGEST_COLUMN_WIDTHS.items():
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(_LARGEST_FOLDER_COLUMN, QHeaderView.ResizeMode.Stretch)
        table.setTextElideMode(Qt.TextElideMode.ElideMiddle)  # the end of a path says the most
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        return table, proxy

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

    def _build_age_table(self) -> QTableView:
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(self.age_model)
        proxy.setSortRole(SORT_ROLE)
        table = _table(proxy)
        table.setItemDelegateForColumn(_AGE_SHARE_COLUMN, ShareBarDelegate(table))
        table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        table.doubleClicked.connect(lambda index: self._age_activated(proxy, index))
        return table

    def _build_types_table(self) -> QTableView:
        self._types_proxy.setSourceModel(self.types_model)
        self._types_proxy.setSortRole(SORT_ROLE)
        table = _table(self._types_proxy)
        table.setItemDelegateForColumn(_TYPES_SHARE_COLUMN, ShareBarDelegate(table))
        table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        table.doubleClicked.connect(self._type_activated)
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
        self._show_all.clicked.connect(self.show_all_largest)
        self._focus_bar.hide()
        self.tabs.addTab(_column(self._focus_bar, self._largest_filter, self.largest_table), "")
        self.tabs.addTab(self.search, "")
        self.tabs.addTab(_column(self._types_combo, self.types_table), "")
        self.tabs.addTab(self.age_table, "")
        self._problems_hint.setWordWrap(True)
        self._elevate_button.clicked.connect(self.elevate_requested)
        self._problems_bar = _row(self._problems_hint, self._elevate_button)
        self.tabs.addTab(_column(self._problems_bar, self.problems_table), "")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([650, 450])
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
        if not isinstance(node, Node):
            return
        picked = _selected_in(view)
        if not any(entry is node for entry in picked):
            picked = [node]
        self.node_menu_requested.emit(node, picked, view.viewport().mapToGlobal(point))

    def _emit_menu(self, node: Node | None, point: QPoint) -> None:
        if node is not None:
            self.node_menu_requested.emit(node, [node], point)

    def show_largest_of_type(self, extension: str) -> None:
        """List the largest files with this extension (an empty one: files without) on Largest files."""
        self._show_focused(("type", extension), lambda node: extension_of(node.name) == extension)

    def show_largest_of_age(self, age: str) -> None:
        """List the largest files last changed within this age group on the Largest files tab."""
        now = self._outcome.now if self._outcome else 0.0
        self._show_focused(("age", age), lambda node: age_of(node.modified, now) == age)

    def show_all_largest(self) -> None:
        """Go back to the largest files of the whole scan."""
        self._focus = None
        self._focus_bar.hide()
        self.largest_model.set_rows(self._largest_all)

    def _show_focused(self, focus: tuple[str, str], keep: Callable[[Node], bool]) -> None:
        if self._outcome is None:
            return
        self._focus = focus
        self.largest_model.set_rows(largest_matching(self._outcome.result.root, keep, LARGEST_FILES_LIMIT))
        self._largest_filter.clear()
        self._focus_bar.show()
        self._update_texts()
        self.tabs.setCurrentIndex(LARGEST_TAB)

    def _focus_text(self) -> str:
        kind, value = self._focus or ("", "")
        if kind == "age":
            return tr(f"age_{value}")
        return value or tr("no_extension")

    def _type_activated(self, index: QModelIndex) -> None:
        stat = self.types_model.row_at(self._types_proxy.mapToSource(index).row())
        if stat is not None:
            self.show_largest_of_type(stat.extension)

    def _age_activated(self, proxy: QSortFilterProxyModel, index: QModelIndex) -> None:
        stat = self.age_model.row_at(proxy.mapToSource(index).row())
        if stat is not None:
            self.show_largest_of_age(stat.age)

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
        titles = ("tab_treemap", "tab_largest", "tab_search", "tab_types", "tab_age")
        for position, key in enumerate(titles):
            self.tabs.setTabText(position, tr(key))
        self.tabs.setTabText(PROBLEMS_TAB, tr("tab_problems_count", count=errors) if errors else tr("tab_problems"))
        self._focus_label.setText(tr("largest_focus", what=self._focus_text()) if self._focus else "")
        self._problems_bar.setVisible(bool(errors) and elevation.can_elevate())
        self._legend.setText(self._legend_html())
        self.summary.setText(self._summary_text())

    def _summary_text(self) -> str:
        outcome = self._outcome
        root = outcome.result.root if outcome is not None else self.tree_model.root
        if root is None:
            return ""
        values = {"path": root.path, "size": format_size(root.size), "allocated": format_size(root.allocated),
                  "files": format_count(root.file_count), "folders": format_count(root.dir_count)}
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


def _selected_in(view: QAbstractItemView) -> list[Node]:
    """The entries of the rows selected in ``view``."""
    nodes = (index.data(NODE_ROLE) for index in view.selectionModel().selectedRows(0))
    return [node for node in nodes if isinstance(node, Node)]


def _is_within(node: Node, branch: Node) -> bool:
    """Whether ``node`` is ``branch`` or lies beneath it."""
    current: Node | None = node
    while current is not None:
        if current is branch:
            return True
        current = current.parent
    return False


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

