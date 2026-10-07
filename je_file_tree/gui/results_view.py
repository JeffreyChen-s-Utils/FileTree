"""The results page: the folder tree on the left, and treemap / largest files / file types / problems on the right.

Selecting an entry anywhere selects it everywhere: in the tree (expanding the
folders above it), and outlined in the treemap. While a scan runs, the page
already shows its tree (``show_live_root``) under a progress bar and is
refreshed about once a second (``refresh_live``); the lists that need the whole
tree (largest files, file types) fill in when the scan ends.
"""

from __future__ import annotations

import contextlib
import dataclasses
import html
import os
import time
from collections.abc import Callable, Mapping, Sequence

from PySide6.QtCore import (
    QItemSelectionModel, QModelIndex, QPoint, QSettings, QSortFilterProxyModel, Qt, QTimer, Signal,
)
from PySide6.QtGui import QFont, QFontMetrics, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from je_file_tree.core.analysis import (
    AGES,
    CATEGORIES,
    AgeStat,
    CategoryStat,
    ExtensionStat,
    Summary,
    age_of,
    age_stats,
    category_stats,
    extension_of,
    extension_stats,
    files_beneath,
    subtract_ages,
    subtract_stats,
)
from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.capacity import CapacityLedger
from je_file_tree.core.node import Node
from je_file_tree.core.compare import SavedScan
from je_file_tree.core.scanner import ScanProgress, ScanResult
from je_file_tree.core.type_locations import TypeMatches
from je_file_tree.gui import elevation
from je_file_tree.gui.changes_panel import ChangesPanel
from je_file_tree.gui.capacity_panel import CapacityPanel
from je_file_tree.gui.age_colours import AGE_COLOURS, UNKNOWN_AGE_COLOUR
from je_file_tree.gui.charts import MODES as CHART_MODES
from je_file_tree.gui.charts import SUNBURST, TREE, TREEMAP, ChartStack
from je_file_tree.gui.delegates import ShareBarDelegate
from je_file_tree.gui.breadcrumbs import Breadcrumbs
from je_file_tree.gui.cleanup_panel import CleanupPanel
from je_file_tree.gui.duplicates_panel import DuplicatesPanel
from je_file_tree.gui.details_panel import DetailsPanel
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.i18n import format_duration, tr
from je_file_tree.gui.scan_bar import ScanBar
from je_file_tree.gui.scan_worker import AnalyseWorker, ScanOutcome, wait_for
from je_file_tree.gui.search_panel import SearchPanel
from je_file_tree.gui.tables import (
    SORT_ROLE,
    AgeModel,
    ChangesModel,
    FileTypesModel,
    LargestFilesModel,
    ProblemsModel,
)
from je_file_tree.gui.tree_model import (
    ALLOCATED,
    DRIVE_SHARE,
    FILES,
    FOLDERS,
    MODIFIED,
    NODE_ROLE,
    SHARE,
    SIZE,
    FolderTreeModel,
)
from je_file_tree.gui.tree_filter import TreeFilter
from je_file_tree.gui.treemap_widget import BY_AGE, BY_FOLDER, CATEGORY_COLOURS, COLOUR_MODES, LEVELS
from je_file_tree.gui.tree_diagram import ORIENTATIONS
from je_file_tree.gui.tree_columns import TreeColumns
from je_file_tree.gui.type_locations import TypeLocationsModel, TypeLocationsWorker
from je_file_tree.gui.users_panel import UsersPanel

_LARGEST_SIZE_COLUMN = 1
# Name starts at 250 px; extra columns use horizontal scrolling.
_TREE_COLUMN_WIDTHS = {SIZE: 75, ALLOCATED: 75, SHARE: 95, DRIVE_SHARE: 95, FILES: 55, FOLDERS: 65, MODIFIED: 120}
_LARGEST_COLUMN_WIDTHS = {0: 200, 1: 80, 3: 125}
_LARGEST_FOLDER_COLUMN = 2
_CHANGE_COLUMN = 3
_PROBLEM_COLUMN_WIDTH = 220
_TYPES_SHARE_COLUMN = 3
_AGE_SHARE_COLUMN = 2
CHART_TAB, LARGEST_TAB, SEARCH_TAB, CLEANUP_TAB, TYPES_TAB, AGE_TAB, CHANGES_TAB, PROBLEMS_TAB = range(8)
USERS_TAB = 8
SUGGESTIONS_PAGE, DUPLICATES_PAGE = range(2)  # the pages of the Clean up tab


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
    chart_menu_requested = Signal(object, object, QPoint)
    selection_changed = Signal(object)
    elevate_requested = Signal()
    compare_failed = Signal(str)
    chart_setting_changed = Signal(str, object)  # a setting key and its new value

    def __init__(self, parent: QWidget | None = None, *, settings: QSettings | None = None) -> None:
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
        self.summary = _summary_label()
        self.capacity = CapacityPanel()
        self.tree = self._build_tree(settings)
        self._build_chart_controls()
        self._treemap_up = QToolButton()
        self.breadcrumbs = Breadcrumbs()
        self._legend = QLabel()
        self._largest_filter = QLineEdit()
        self._focus_label = QLabel()
        self._show_all = QPushButton()
        self._focus_bar = _row(self._focus_label, self._show_all)
        self.largest_table, self._largest_proxy = self._build_entries_table(self.largest_model)
        self.search_model = LargestFilesModel(self)
        self.search_table, _ = self._build_entries_table(self.search_model)
        self.search = SearchPanel(self.search_table, self.search_model)
        self._build_cleanup_panels()
        self.changes_model = ChangesModel(self)
        self.changes_table, _ = self._build_table(self.changes_model, _CHANGE_COLUMN)
        self.changes = ChangesPanel(self.changes_table, self.changes_model)
        self._reveal_changes = False
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
        self._build_scope_switch()
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
        self.breadcrumbs.set_root(None)
        self.details.set_node(None)
        self._stop_focused()
        self.charts.set_age_reference(time.time())
        self.capacity.set_ledger(None)
        self.search.set_root(None)
        self.duplicates.set_root(None)
        self.cleanup.set_root(None)
        self.users.set_root(None)
        self.changes.set_root(None)
        self._live_ticks = 0
        self.tree_model.set_root(None)
        for model in (self.largest_model, self.types_model, self.problems_model, self.age_model):
            model.set_rows([])
        self._largest_all = []
        self._focus = None
        self._categories = []
        self.charts.set_view_root(None)
        self.scan_bar.start()
        self._update_texts()

    def show_live_root(self, root: Node) -> None:
        """Show the tree a running scan is filling in."""
        self.tree_model.set_root(root, live=True)
        self.breadcrumbs.set_root(root)
        self.tree.expand(self.tree_filter.index_for(root))
        self.charts.set_view_root(root)
        self.select_node(root)
        self._update_texts()

    def refresh_live(self) -> None:
        """Show what the running scan added since the last call (the treemap every third call)."""
        if not self.tree_model.live:
            return
        self._live_ticks += 1
        self.tree_model.refresh()
        if self._live_ticks % 3 == 0:
            self.charts.invalidate()
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
            self.charts.set_view_root(None)

    def show_outcome(self, outcome: ScanOutcome) -> None:
        """Show a finished (or stopped) scan; folders opened while it ran stay open."""
        self._outcome = outcome
        self.charts.set_age_reference(outcome.now)
        root = outcome.result.root
        self.scan_bar.hide()
        if self.tree_model.root is root:
            self.tree_model.finish_live()
        else:
            self.tree_model.set_root(root)
            self.tree.expand(self.tree_filter.index_for(root))
        self.capacity.set_ledger(outcome.capacity)
        self.breadcrumbs.set_root(root)
        self.tree_model.set_drive_total(outcome.capacity.total if outcome.capacity is not None else None)
        self._scope = None
        self._scope_button.setChecked(False)
        self._show_lists(outcome.largest, outcome.extensions, outcome.ages)
        self.problems_model.set_rows(outcome.result.errors)
        self._categories = outcome.chart_categories if outcome.chart_categories is not None else outcome.categories
        view_root = self.charts.view_root
        self.charts.set_view_root(view_root if view_root is not None and view_root.is_in(root) else root)
        if self.selected_node() is None:
            self.select_node(root)
        self.search.set_root(root)
        self.duplicates.set_root(root)
        self.cleanup.set_root(root, partial=outcome.partial)
        self.users.set_root(root, partial=outcome.partial)
        self.changes.set_root(root)
        self._update_texts()
        self.selection_changed.emit(self.selected_node())  # its size is final now

    def replace_branch(self, old: Node, fresh: ScanResult) -> Node:
        """Put a rescan of the folder ``old`` in its place; returns the new node.

        The tree, the treemap, the problems and the summary change at once; the
        lists that need the whole tree follow with ``apply_summary``.
        """
        self._stop_focused()
        self.capacity.set_ledger(None)
        self.tree_model.set_drive_total(None)
        new = fresh.root
        view_root = self.charts.view_root
        inside_old = view_root is not None and _is_within(view_root, old)
        prefix = old.path.rstrip("\\/") + os.sep
        self.tree_model.replace(old, new)
        if self._outcome is not None:
            errors = self._outcome.result.errors
            errors[:] = [error for error in errors if error[0] != old.path and not error[0].startswith(prefix)]
            errors.extend(fresh.errors)
            self._outcome = dataclasses.replace(self._outcome, capacity=None)
            self.problems_model.set_rows(errors)
        self.charts.set_view_root(new if inside_old else view_root)
        self.search.rerun()
        self.duplicates.prune()
        self.cleanup.refresh()
        self.users.refresh()
        self.changes.refresh()
        self._update_texts()
        self.selection_changed.emit(self.selected_node())
        return new

    def set_capacity(self, capacity: CapacityLedger) -> None:
        """Show a refreshed whole-tree ledger computed after a branch rescan."""
        if self._outcome is not None:
            self._outcome = dataclasses.replace(self._outcome, capacity=capacity)
            self.capacity.set_ledger(capacity)
            self.tree_model.set_drive_total(capacity.total)

    def apply_summary(self, summary: Summary) -> None:
        """Show recomputed largest files and per-type and per-age totals for the tree on screen."""
        outcome = self._outcome
        if outcome is None:
            return
        root = outcome.result.root
        largest = [node for node in summary.largest if node.is_in(root)]
        self._outcome = dataclasses.replace(outcome, largest=largest, extensions=summary.extensions,
                                            categories=category_stats(summary.extensions), ages=summary.ages,
                                            now=summary.now, chart_categories=summary.counted_categories)
        self._categories = (summary.counted_categories if summary.counted_categories is not None
                            else self._outcome.categories)
        self.charts.set_age_reference(summary.now)
        if self._scope is None:
            self._show_lists(largest, summary.extensions, summary.ages)
        else:
            self._rescope(force=True)

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit``."""
        self.tree_model.set_unit(unit)
        self.capacity.unit = unit
        self.capacity.retranslate()
        for model in (self.largest_model, self.types_model, self.age_model, self.search_model, self.changes_model):
            model.unit = unit
            model.refresh()
        self.search.retranslate()
        self.duplicates.set_unit(unit)
        self.cleanup.set_unit(unit)
        self.users.set_unit(unit)
        self.charts.set_unit(unit)
        self.details.unit = unit
        self.details.retranslate()
        self.type_locations_model.unit = unit
        self.type_locations_model.refresh()
        self.changes.retranslate()
        self.breadcrumbs.retranslate()

    def selected_node(self) -> Node | None:
        """The entry the tree's cursor is on."""
        index = self.tree.currentIndex()
        return index.data(NODE_ROLE) if index.isValid() else None

    def selected_nodes(self) -> list[Node]:
        """Every entry selected in the tree (Ctrl+click and Shift+click pick several)."""
        return _selected_in(self.tree)

    def focused_selection(self) -> list[Node]:
        """The entries selected where the keyboard is: the largest-files, search or duplicates list, else the tree."""
        for view in (self.largest_table, self.search_table, self.duplicates.view, self.cleanup.view):
            if view.hasFocus():
                return _selected_in(view)
        return _selected_in(self.tree)

    def set_chart_mode(self, mode: str) -> None:
        """Show a chart mode; ignore unknown values."""
        if mode in self._chart_buttons:
            self.charts.set_mode(mode)
            self._chart_buttons[mode].setChecked(True)
            self._update_chart_controls()

    def apply_chart_settings(self, values: Mapping[str, object]) -> None:
        """Restore chart settings; ignore invalid saved values."""
        self.set_chart_mode(str(values.get("chart_mode", "")))
        treemap = self.charts.treemap
        with contextlib.suppress(ValueError):  # a hand-edited setting that is not a number: keep the default
            treemap.set_levels(int(str(values.get("treemap_levels", treemap.levels))))
        self.charts.set_colour_mode(str(values.get("treemap_colours", treemap.colour_mode)))
        self.charts.tree.set_orientation(str(values.get("tree_orientation", self.charts.tree.orientation)))
        _select_data(self._levels_combo, treemap.levels)
        _select_data(self._colours_combo, treemap.colour_mode)
        _select_data(self._tree_orientation_combo, self.charts.tree.orientation)
        self._update_chart_controls()

    def compare_with(self, file: str) -> None:
        """Compare the scan on screen with the saved scan ``file``; the Changes tab comes forward with the result."""
        self._reveal_changes = True
        self.changes.open(file)

    def compare_saved(self, saved: SavedScan) -> None:
        """Reuse the Changes tab for a local-history snapshot already loaded on its owned worker."""
        self._reveal_changes = True
        self.changes.compare_saved(saved)

    def show_search(self) -> None:
        """Bring the Search tab forward with the cursor in its box."""
        self.tabs.setCurrentIndex(SEARCH_TAB)
        self.search.focus()

    def current_list(self) -> QAbstractItemView | None:
        """The active result list, including filtered/sorted and grouped model order."""
        lists = {LARGEST_TAB: self.type_locations_table if self.type_locations_table.hasFocus() else self.largest_table,
                 SEARCH_TAB: self.search_table, TYPES_TAB: self.types_table,
                 AGE_TAB: self.age_table, CHANGES_TAB: self.changes_table, PROBLEMS_TAB: self.problems_table,
                 USERS_TAB: self.users.view,
                 CLEANUP_TAB: self.cleanup.view if self.cleanup_pages.currentIndex() == SUGGESTIONS_PAGE
                 else self.duplicates.view}
        return lists.get(self.tabs.currentIndex())

    def select_node(self, node: Node) -> None:
        """Select ``node`` in the tree (expanding its folders), and outline it in the treemap."""
        index = self.tree_filter.reveal(node)
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
        self._stop_focused()
        self.capacity.set_ledger(None)
        self.tree_model.set_drive_total(None)
        view_root = self.charts.view_root
        extensions = outcome.extensions
        ages = outcome.ages
        for node in nodes:
            extensions = subtract_stats(extensions, extension_stats(node))
            ages = subtract_ages(ages, age_stats(files_beneath(node), outcome.now))
            self.tree_model.remove(node)
        root = outcome.result.root
        self._outcome = dataclasses.replace(outcome, extensions=extensions, ages=ages,
                                            categories=category_stats(extensions),
                                            largest=[file for file in outcome.largest if file.is_in(root)],
                                            capacity=None)
        self._categories = self._outcome.categories
        if self._scope is None:
            self._largest_all = [file for file in self._largest_all if file.is_in(root)]
            self.largest_model.set_rows([file for file in self.largest_model.rows() if file.is_in(root)])
            self.types_model.set_rows(extensions)
            self.age_model.set_rows(ages)
        else:
            self._rescope(force=True)
        if view_root is not None and not view_root.is_in(root):
            view_root = root
        self.charts.set_view_root(view_root)
        self.search.rerun()
        self.duplicates.prune()
        self.cleanup.refresh()
        self.users.refresh()
        self.changes.refresh()
        self._update_texts()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self.tree_model.retranslate()
        self.tree_filter.retranslate()
        self.charts.retranslate()
        self.capacity.retranslate()
        for model in (self.largest_model, self.types_model, self.problems_model, self.age_model):
            model.refresh()
        self._show_all.setText(tr("largest_show_all"))
        self.types_table.setToolTip(tr("list_files_tip"))
        self.age_table.setToolTip(tr("list_files_tip"))
        self.scan_bar.retranslate()
        self._treemap_up.setText(tr("treemap_up"))
        self.details.retranslate()
        self._treemap_up.setToolTip(tr("treemap_up_tip"))
        for mode, button in self._chart_buttons.items():
            button.setText(tr(f"chart_{mode}"))
            button.setToolTip(tr(f"chart_{mode}_tip"))
        self._levels_label.setText(tr("treemap_levels"))
        self._colours_label.setText(tr("treemap_colours"))
        _fill_combo(self._levels_combo, [(tr("treemap_levels_all") if levels == LEVELS[-1] else str(levels), levels)
                                         for levels in LEVELS], self.charts.treemap.levels)
        _fill_combo(self._colours_combo, [(tr(f"treemap_colours_{mode}"), mode) for mode in COLOUR_MODES],
                    self.charts.treemap.colour_mode)
        self._tree_orientation_label.setText(tr("tree_orientation"))
        _fill_combo(self._tree_orientation_combo,
                    [(tr(f"tree_orientation_{mode}"), mode) for mode in ORIENTATIONS],
                    self.charts.tree.orientation)
        self._largest_filter.setPlaceholderText(tr("largest_filter"))
        self._type_locations_label.setText(tr('type_locations_title'))
        self._type_locations_label.setToolTip(tr('type_locations_tip'))
        self.type_locations_model.refresh()
        self.search.retranslate()
        self.duplicates.retranslate()
        self.cleanup.retranslate()
        self.users.retranslate()
        self.changes.retranslate()
        self.breadcrumbs.retranslate()
        self._problems_hint.setText(tr("problems_hint"))
        self._elevate_button.setText(tr("action_elevate"))
        self._elevate_button.setToolTip(tr("action_elevate_tip"))
        self._fill_types_combo()
        self._update_texts()

    # --- building ---------------------------------------------------------

    def _build_cleanup_panels(self) -> None:
        self.duplicates = DuplicatesPanel()
        self.cleanup = CleanupPanel()
        self.users = UsersPanel()
        self.cleanup_pages = QTabWidget()

    def _build_scope_switch(self) -> None:
        self._scope: Node | None = None  # the folder the three lists cover; None: the whole scan
        self._scope_button = QToolButton()
        self._scope_timer = QTimer(self)
        self._scope_worker: AnalyseWorker | None = None
        self._list_workers: set[AnalyseWorker | TypeLocationsWorker] = set()
        self._focus_worker: TypeLocationsWorker | None = None

    def _build_chart_controls(self) -> None:
        self.charts = ChartStack()
        self._chart_buttons = {mode: QToolButton() for mode in CHART_MODES}
        self._chart_group = QButtonGroup(self)
        self._levels_label = QLabel()
        self._levels_combo = QComboBox()
        self._colours_label = QLabel()
        self._colours_combo = QComboBox()
        self._tree_orientation_label = QLabel()
        self._tree_orientation_combo = QComboBox()

    def _build_tree(self, settings: QSettings | None) -> QTreeView:
        self.details = DetailsPanel(settings, self)
        self.selection_changed.connect(lambda node: self.details.set_node(
            node, live=self.tree_model.live, now=self._outcome.now if self._outcome is not None else None))
        tree = QTreeView()
        tree.setModel(self.tree_model)
        tree.setUniformRowHeights(True)
        tree.setSortingEnabled(True)
        tree.sortByColumn(SIZE, Qt.SortOrder.DescendingOrder)
        tree.setAlternatingRowColors(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        tree.setItemDelegateForColumn(SHARE, ShareBarDelegate(tree))
        tree.setItemDelegateForColumn(DRIVE_SHARE, ShareBarDelegate(tree))
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(lambda point: self._menu_for(tree, point))
        header = tree.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        for column, width in _TREE_COLUMN_WIDTHS.items():
            tree.setColumnWidth(column, width)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        tree.setColumnWidth(0, 250)
        self.tree_columns = TreeColumns(tree, settings)
        tree.selectionModel().currentChanged.connect(self._tree_current_changed)
        tree.selectionModel().selectionChanged.connect(lambda *_: self.selection_changed.emit(self.selected_node()))
        self.tree_filter = TreeFilter(tree, self.tree_model, self)
        self.tree_filter.selection_model_changed.connect(self._connect_tree_selection)
        return tree

    def _connect_tree_selection(self) -> None:
        self.tree.selectionModel().currentChanged.connect(self._tree_current_changed)
        self.tree.selectionModel().selectionChanged.connect(
            lambda *_: self.selection_changed.emit(self.selected_node()))

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

    def _build_table(self, model: LargestFilesModel | ProblemsModel | ChangesModel,
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

    def _assemble_scope_switch(self) -> None:
        """*Selected folder only*, in the tab bar's corner: the three lists follow the tree's selection."""
        self._scope_button.setCheckable(True)
        self._scope_button.toggled.connect(self._scope_toggled)
        self._scope_button.toggled.connect(lambda _on: self._update_scope_button())
        self.tabs.setCornerWidget(self._scope_button, Qt.Corner.TopRightCorner)
        self.tabs.currentChanged.connect(lambda _index: self._update_scope_button())
        self._scope_timer.setSingleShot(True)
        self._scope_timer.setInterval(250)
        self._scope_timer.timeout.connect(self._rescope)

    def _assemble_chart_tab(self) -> None:
        """The Chart tab: the path and view buttons, the treemap options, the charts and the legend."""
        self._treemap_up.clicked.connect(self.charts.zoom_out)
        self.breadcrumbs.navigate.connect(self.charts.set_view_root)
        self._legend.setWordWrap(True)
        self.charts.node_clicked.connect(self._treemap_clicked)
        self.charts.view_root_changed.connect(self._treemap_root_changed)
        self.charts.context_menu_requested.connect(self._emit_menu)

        for mode, button in self._chart_buttons.items():
            button.setCheckable(True)
            button.setAutoRaise(True)
            self._chart_group.addButton(button)
            button.clicked.connect(lambda _checked=False, chosen=mode: self._choose_chart(chosen))
        self._chart_buttons[self.charts.mode].setChecked(True)
        chart_bar = _row(self._treemap_up, self.breadcrumbs)
        chart_bar.layout().setStretch(1, 1)
        for button in self._chart_buttons.values():
            chart_bar.layout().addWidget(button)
        self._treemap_options = _row(self._levels_label, self._levels_combo, self._colours_label, self._colours_combo)
        self._tree_options = _row(self._tree_orientation_label, self._tree_orientation_combo)
        self._levels_combo.currentIndexChanged.connect(lambda _index: self._choose_levels())
        self._colours_combo.currentIndexChanged.connect(lambda _index: self._choose_colours())
        self._tree_orientation_combo.currentIndexChanged.connect(lambda _index: self._choose_tree_orientation())
        self.tabs.addTab(_column(chart_bar, self._treemap_options, self._tree_options, self.charts, self._legend), "")
        self._update_chart_controls()

    def _assemble(self) -> None:
        self._largest_filter.setClearButtonEnabled(True)
        self._largest_filter.textChanged.connect(self._largest_proxy.setFilterFixedString)
        self._assemble_chart_tab()
        self._show_all.clicked.connect(self.show_all_largest)
        self._focus_bar.hide()
        self.tabs.addTab(_column(self._focus_bar, self._largest_filter, self._build_type_locations()), "")
        self.tabs.addTab(self.search, "")
        self.cleanup_pages.addTab(self.cleanup, "")
        self.cleanup_pages.addTab(self.duplicates, "")
        self.tabs.addTab(self.cleanup_pages, "")
        for view in (self.cleanup.view, self.duplicates.view):
            view.customContextMenuRequested.connect(lambda point, view=view: self._menu_for(view, point))
            view.doubleClicked.connect(lambda index, view=view: self._table_activated(view, index))
        self.tabs.addTab(_column(self._types_combo, self.types_table), "")
        self.tabs.addTab(self.age_table, "")
        self._problems_hint.setWordWrap(True)
        self._elevate_button.clicked.connect(self.elevate_requested)
        self.tabs.addTab(self.changes, "")
        self._assemble_scope_switch()
        self.tabs.setTabVisible(CHANGES_TAB, False)  # until a saved scan is opened
        self.changes.shown.connect(self._changes_shown)
        self.changes.failed.connect(self.compare_failed)
        self._problems_bar = _row(self._problems_hint, self._elevate_button)
        self.tabs.addTab(_column(self._problems_bar, self.problems_table), "")
        self.tabs.addTab(self.users, "")
        self.tabs.currentChanged.connect(lambda index: self.users.set_active(index == USERS_TAB))
        for view in (self.tree, self.largest_table, self.search_table, self.types_table, self.age_table,
                     self.changes_table, self.problems_table, self.cleanup.view, self.duplicates.view,
                     self.type_locations_table):
            install_copy(view)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree_with_details())
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([650, 450])
        self.splitter = splitter
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.scan_bar)
        layout.addWidget(self.summary)
        layout.addWidget(self.capacity)
        layout.addWidget(splitter, 1)

    def _tree_with_details(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree_filter.line)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.details)
        return column

    # --- reactions --------------------------------------------------------

    def _build_type_locations(self) -> QWidget:
        self.type_locations_model = TypeLocationsModel(self)
        self.type_locations_table, _ = self._build_table(self.type_locations_model, 1)
        header = self.type_locations_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 95), (2, 60), (3, 80)):
            self.type_locations_table.setColumnWidth(column, width)
        self.type_locations_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._type_locations_label = QLabel()
        self._type_locations_pane = _column(self._type_locations_label, self.type_locations_table)
        self._type_locations_pane.hide()
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.largest_table)
        splitter.addWidget(self._type_locations_pane)
        splitter.setSizes([300, 150])
        return splitter

    def _tree_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        node = current.data(NODE_ROLE) if current.isValid() else None
        self.charts.set_selected(node)
        self.selection_changed.emit(node)
        if self._scope_button.isChecked():
            self._scope_timer.start()  # moving through the tree with the arrow keys recomputes once, at the end

    def _choose_chart(self, mode: str) -> None:
        self.set_chart_mode(mode)
        self.chart_setting_changed.emit("chart_mode", mode)

    def _choose_levels(self) -> None:
        levels = self._levels_combo.currentData()
        if levels is not None and levels != self.charts.treemap.levels:
            self.charts.treemap.set_levels(int(levels))
            self.chart_setting_changed.emit("treemap_levels", int(levels))

    def _choose_colours(self) -> None:
        mode = self._colours_combo.currentData()
        if mode is not None and mode != self.charts.treemap.colour_mode:
            self.charts.set_colour_mode(str(mode))
            self.chart_setting_changed.emit("treemap_colours", str(mode))
            self._update_chart_controls()
            self._update_texts()

    def _choose_tree_orientation(self) -> None:
        orientation = self._tree_orientation_combo.currentData()
        if orientation is not None and orientation != self.charts.tree.orientation:
            self.charts.tree.set_orientation(str(orientation))
            self.chart_setting_changed.emit("tree_orientation", str(orientation))

    def _update_chart_controls(self) -> None:
        """Show shared colour choices for treemap/sunburst, and the matching legend."""
        treemap_on_screen = self.charts.mode == TREEMAP
        self._treemap_options.setVisible(self.charts.mode in (TREEMAP, SUNBURST))
        self._levels_label.setVisible(treemap_on_screen)
        self._levels_combo.setVisible(treemap_on_screen)
        self._tree_options.setVisible(self.charts.mode == TREE)
        by_folder = self.charts.mode == TREE or (self.charts.mode in (TREEMAP, SUNBURST)
                                                  and self.charts.treemap.colour_mode == BY_FOLDER)
        self._legend.setVisible(not by_folder)
        self._legend.setText(self._legend_html())

    def _changes_shown(self, shown: bool) -> None:
        self.tabs.setTabVisible(CHANGES_TAB, shown)
        if shown and self._reveal_changes:
            self.tabs.setCurrentIndex(CHANGES_TAB)
        self._reveal_changes = False

    def _treemap_clicked(self, node: Node) -> None:
        self.select_node(node)

    def _treemap_root_changed(self, node: Node | None) -> None:
        self.breadcrumbs.visit(node)
        self._treemap_up.setEnabled(node is not None and node.parent is not None)

    def _table_activated(self, table: QAbstractItemView, index: QModelIndex) -> None:
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
            self.chart_menu_requested.emit(node, [node], point)

    def wait_for_lists(self) -> None:
        """Wait for list computations still running (before the window closes)."""
        self._stop_focused()
        self.tree_filter.shutdown()
        for worker in self._list_workers.copy():
            wait_for(worker)

    def _show_lists(self, largest: Sequence[Node], extensions: Sequence[ExtensionStat],
                    ages: Sequence[AgeStat]) -> None:
        """Fill the three lists (largest files, types, ages), dropping a type or age focus."""
        self._stop_focused()
        self._largest_all = list(largest)
        self._focus = None
        self._focus_bar.hide()
        self.largest_model.set_rows(self._largest_all)
        self.types_model.set_rows(extensions)
        self.age_model.set_rows(ages)
        self._update_texts()

    def _lists_root(self) -> Node | None:
        """The folder the three lists cover (None before the first scan)."""
        if self._scope is not None:
            return self._scope
        return self._outcome.result.root if self._outcome is not None else None

    def _selected_folder(self) -> Node | None:
        node = self.selected_node()
        if node is not None and (not node.is_dir or node.is_link):
            node = node.parent
        return node

    def _scope_toggled(self, on: bool) -> None:
        if on:
            self._rescope(force=True)
            return
        self._scope = None
        self._scope_worker = None
        self._scope_timer.stop()
        if self._outcome is not None:
            self._show_lists(self._outcome.largest, self._outcome.extensions, self._outcome.ages)

    def _rescope(self, *, force: bool = False) -> None:
        """Compute the three lists for the selected folder on a worker (with *Selected folder only* on)."""
        self._scope_timer.stop()
        outcome = self._outcome
        if outcome is None or not self._scope_button.isChecked():
            return
        folder = self._selected_folder() or outcome.result.root
        if folder is self._scope and not force:
            return
        self._scope = folder
        worker = AnalyseWorker(folder, self)
        worker.done.connect(lambda summary: worker is self._scope_worker and self._scope_ready(folder, summary))
        worker.finished.connect(lambda: self._list_workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._scope_worker = worker
        self._list_workers.add(worker)
        self._update_scope_button()
        worker.start()

    def _scope_ready(self, folder: Node, summary: Summary) -> None:
        self._scope_worker = None
        if folder is self._scope:
            self._show_lists(summary.largest, summary.extensions, summary.ages)

    def _update_scope_button(self) -> None:
        """Shown on the three list tabs once there is a scan; names the folder while it is on."""
        tab = self.tabs.currentIndex()
        self._scope_button.setVisible(self._outcome is not None and tab in (LARGEST_TAB, TYPES_TAB, AGE_TAB))
        scope = self._scope
        on = self._scope_button.isChecked() and scope is not None
        self._scope_button.setText(tr("scope_folder_named", name=scope.name) if on else tr("scope_folder"))
        self._scope_button.setToolTip(scope.path if on else tr("scope_folder_tip"))

    def show_largest_of_type(self, extension: str) -> None:
        """List the largest files with this extension (an empty one: files without) on Largest files."""
        self._show_focused(("type", extension), lambda node: extension_of(node.name) == extension)

    def show_largest_of_age(self, age: str) -> None:
        """List the largest files last changed within this age group on the Largest files tab."""
        now = self._outcome.now if self._outcome else 0.0
        self._show_focused(("age", age), lambda node: age_of(node.modified, now) == age)

    def show_all_largest(self) -> None:
        """Go back to the largest files of all types and ages (in the scope the lists cover)."""
        self._stop_focused()
        self._focus = None
        self._focus_bar.hide()
        self.largest_model.set_rows(self._largest_all)

    def _show_focused(self, focus: tuple[str, str], keep: Callable[[Node], bool]) -> None:
        root = self._lists_root()
        if root is None:
            return
        self._stop_focused()
        self._focus = focus
        self.largest_model.set_rows([])
        self._type_locations_pane.setVisible(focus[0] == 'type')
        worker = TypeLocationsWorker(root, keep, self)
        worker.done.connect(lambda matches: self._focused_ready(worker, matches))
        worker.finished.connect(lambda: self._list_workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._focus_worker = worker
        self._list_workers.add(worker)
        worker.start()
        self._largest_filter.clear()
        self._focus_bar.show()
        self._update_texts()
        self.tabs.setCurrentIndex(LARGEST_TAB)

    def _stop_focused(self) -> None:
        if self._focus_worker is not None:
            self._focus_worker.stop()
        self._focus_worker = None
        self.type_locations_model.set_rows([])
        self._type_locations_pane.hide()

    def _focused_ready(self, worker: TypeLocationsWorker, matches: TypeMatches) -> None:
        if worker is not self._focus_worker or self._outcome is None:
            return
        self._focus_worker = None
        root = self._outcome.result.root
        if not worker.root.is_in(root):
            return
        self.largest_model.set_rows([node for node in matches.files if node.is_in(root)])
        self.type_locations_model.total = matches.total
        self.type_locations_model.set_rows([row for row in matches.folders if row.folder.is_in(root)])

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
        self._update_scope_button()
        errors = len(self._outcome.result.errors) if self._outcome else 0
        titles = ("tab_chart", "tab_largest", "tab_search", "tab_cleanup", "tab_types", "tab_age", "tab_changes")
        for position, key in enumerate(titles):
            self.tabs.setTabText(position, tr(key))
        self.cleanup_pages.setTabText(SUGGESTIONS_PAGE, tr("cleanup_suggestions"))
        self.cleanup_pages.setTabText(DUPLICATES_PAGE, tr("tab_duplicates"))
        self.tabs.setTabText(PROBLEMS_TAB, tr("tab_problems_count", count=errors) if errors else tr("tab_problems"))
        self.tabs.setTabText(USERS_TAB, tr("tab_users"))
        self._focus_label.setText(tr("largest_focus", what=self._focus_text()) if self._focus else "")
        self._problems_bar.setVisible(bool(errors) and elevation.can_elevate())
        self._legend.setText(self._legend_html())
        self.summary.setText(self._summary_text())

    def _summary_text(self) -> str:
        outcome = self._outcome
        root = outcome.result.root if outcome is not None else self.tree_model.root
        if root is None:
            return ""
        self.summary.setToolTip(root.path)
        values = {"path": html.escape(self._fitting_path(root.path)), "size": format_size(root.size),
                  "allocated": format_size(root.allocated), "files": format_count(root.file_count),
                  "folders": format_count(root.dir_count)}
        if outcome is None:
            return tr("summary_live", **values)
        key = "summary_partial" if outcome.partial else "summary"
        text = tr(key, time=format_duration(outcome.result.elapsed), **values)
        if outcome.result.hard_links is not None:
            info = outcome.result.hard_links
            text += "<br>" + tr("hard_links_summary", size=format_size(root.accounted_size),
                                allocated=format_size(root.accounted_allocated), aliases=format_count(info.aliases),
                                unknown=format_count(info.unknown))
        return text

    def _fitting_path(self, path: str) -> str:
        """``path`` shortened in the middle to half the summary line's width (it is shown in bold)."""
        font = QFont(self.summary.font())
        font.setBold(True)
        room = max(self.summary.width() // 2, 160)
        return QFontMetrics(font).elidedText(path, Qt.TextElideMode.ElideMiddle, room)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Qt: fit the scanned path in the summary line again."""
        super().resizeEvent(event)
        self.summary.setText(self._summary_text())

    def _legend_html(self) -> str:
        if self.charts.mode in (TREEMAP, SUNBURST) and self.charts.treemap.colour_mode == BY_AGE:
            self._legend.setToolTip(tr("age_colour_tip"))
            return " &nbsp; ".join(f'<span style="color:{colour}">&#9632;</span> '
                                   + _unbreakable(label) for colour, label in
                                   [(AGE_COLOURS[age], tr(f"age_{age}")) for age in AGES]
                                   + [(UNKNOWN_AGE_COLOUR, tr("age_colour_unknown"))])
        self._legend.setToolTip("")
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


def _summary_label() -> QLabel:
    """The line over the tree; the scanned path in it is shortened to fit (``_summary_text``), so a long
    one never widens the window."""
    label = QLabel()
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return label


def _fill_combo(combo: QComboBox, items: list[tuple[str, object]], current: object) -> None:
    """Replace a combo box's items (text, data) without signalling, keeping ``current`` selected."""
    combo.blockSignals(True)
    combo.clear()
    for text, data in items:
        combo.addItem(text, data)
    combo.blockSignals(False)
    _select_data(combo, current)


def _select_data(combo: QComboBox, data: object) -> None:
    combo.blockSignals(True)
    combo.setCurrentIndex(max(0, combo.findData(data)))
    combo.blockSignals(False)


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
        layout.addWidget(widget, 1 if isinstance(widget, (QTableView, ChartStack)) else 0)
    return box
