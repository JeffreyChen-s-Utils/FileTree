"""A list of entries in named groups (Duplicates, Clean-up suggestions): one line per group, its entries below.

Each entry line shows name, size, folder and modified time and carries its node (``NODE_ROLE``), so
the results page's context menu, double-click and Delete work on it like on any other list.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from PySide6.QtCore import (
    QAbstractItemModel, QItemSelection, QItemSelectionModel, QModelIndex, QObject,
    QPersistentModelIndex, Qt,
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTreeView

from je_file_tree.core.formatting import format_size, format_time
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.tree_model import NODE_ROLE

COLUMNS = ("column_name", "column_size", "column_folder", "column_modified")
_COLUMN_WIDTHS = {0: 200, 1: 80, 3: 125}
_FOLDER_COLUMN = 2
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_GROUP_FLAGS = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
_ENTRY_FLAGS = _GROUP_FLAGS | Qt.ItemFlag.ItemNeverHasChildren
ModelIndex = QModelIndex | QPersistentModelIndex


@dataclass(frozen=True, slots=True)
class _Group:
    title: str
    nodes: tuple[Node, ...]
    tip: str | None
    kept: Node | None


class GroupedListModel(QAbstractItemModel):
    """Two-level captured groups; format visible cells without creating per-file Qt items.

    Native Windows: eager four-cell rows took 2.58 s for 100,000 entries. Capture
    membership once, retain every row and supply display roles only when requested.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._groups: tuple[_Group, ...] = ()
        self._icons: dict[Node, QIcon] = {}
        self._unit = "auto"
        self._kept_font = QFont()
        self._kept_font.setBold(True)

    def set_groups(self, groups: Sequence[tuple[str, Sequence[Node]]], unit: str,
                   *, tips: Sequence[str] | None = None, keepers: Sequence[Node | None] | None = None,
                   icons: Mapping[Node, QIcon] | None = None) -> None:
        """Replace all groups, freezing row membership and optional keeper/thumbnail roles."""
        captured = tuple(_Group(title, tuple(nodes), tips[row] if tips is not None else None,
                                keepers[row] if keepers is not None else None)
                         for row, (title, nodes) in enumerate(groups))
        self.beginResetModel()
        self._groups = captured
        self._unit = unit
        self._icons = dict(icons) if icons is not None else {}
        self.endResetModel()

    def set_group_labels(self, labels: Sequence[tuple[str, str | None]]) -> None:
        """Update group titles/tooltips without replacing captured rows or resetting view state."""
        if len(labels) != len(self._groups):
            raise ValueError("Group labels must match the captured group count")
        updated, changed = [], []
        for row, (group, (title, tip)) in enumerate(zip(self._groups, labels, strict=True)):
            updated_group = group
            if group.title != title or group.tip != tip:
                updated_group = replace(group, title=title, tip=tip)
                changed.append(row)
            updated.append(updated_group)
        if changed:
            self._groups = tuple(updated)
            # Native 100k-entry probe: broad root ranges revisit intervening files (U-20261017-21).
            for row in changed:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole])

    def index(self, row: int, column: int, parent: ModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        """Use zero for a group and its one-based group number for a child index ID."""
        if row < 0 or not 0 <= column < len(COLUMNS):
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(row, column, 0) if row < len(self._groups) else QModelIndex()
        if parent.column() != 0 or parent.internalId() != 0:
            return QModelIndex()
        return (self.createIndex(row, column, parent.row() + 1)
                if row < len(self._groups[parent.row()].nodes) else QModelIndex())

    def parent(self, index: ModelIndex) -> QModelIndex:
        """Entry cells share their group's first-column parent; groups have no parent."""
        group = index.internalId() if index.isValid() else 0
        return self.createIndex(group - 1, 0, 0) if group else QModelIndex()

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Expose every captured member immediately, including members outside the viewport."""
        if not parent.isValid():
            return len(self._groups)
        if parent.column() != 0 or parent.internalId() != 0:
            return 0
        return len(self._groups[parent.row()].nodes)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Name, size, folder and modified time."""
        return len(COLUMNS)

    def hasChildren(self, parent: ModelIndex = QModelIndex()) -> bool:  # noqa: B008
        """Only nonempty groups have children; entries never expand or inspect the Node tree."""
        return self.rowCount(parent) > 0

    def flags(self, index: ModelIndex) -> Qt.ItemFlag:
        """Read-only selectable groups and entry cells."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return _ENTRY_FLAGS if index.internalId() else _GROUP_FLAGS

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Translated column headings."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr(COLUMNS[section]) if 0 <= section < len(COLUMNS) else None
        return None

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Keep group headers separate from file-operation Node roles on every entry cell."""
        if not index.isValid():
            return None
        group_id = index.internalId()
        if not group_id:
            group = self._groups[index.row()]
            return self._group_data(group, index.column(), role)
        group = self._groups[group_id - 1]
        return self._entry_data(group.nodes[index.row()], index.column(), role, group.kept)

    def _entry_data(self, node: Node, column: int, role: int, kept: Node | None) -> Any:
        if role == NODE_ROLE:
            return node
        if role == Qt.ItemDataRole.ToolTipRole:
            return node.path
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(node, column, kept)
        if role == Qt.ItemDataRole.TextAlignmentRole and column == 1:
            return _RIGHT
        return self._decoration(node, column, role, kept)

    @staticmethod
    def _group_data(group: _Group, column: int, role: int) -> Any:
        if column == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return group.title
            if role == Qt.ItemDataRole.ToolTipRole:
                return group.tip
        return None

    def _decoration(self, node: Node, column: int, role: int, kept: Node | None) -> Any:
        if column == 0:
            if role == Qt.ItemDataRole.FontRole and node is kept:
                return self._kept_font
            if role == Qt.ItemDataRole.DecorationRole:
                return self._icons.get(node)
        return None

    def _text(self, node: Node, column: int, kept: Node | None) -> str:
        if column == 0:
            return tr("duplicates_kept_name", name=node.name) if node is kept else node.name
        if column == 1:
            return format_size(node.size, self._unit)
        if column == _FOLDER_COLUMN:
            return os.path.dirname(node.path)
        return format_time(node.modified)

    def extra_selection(self, keepers: Mapping[int, Node | None]) -> QItemSelection:
        """Full-row ranges excluding every keeper occurrence in eligible captured groups.

        Missing keepers are refused, including keepers outside the displayed snapshot.
        Read Node identities once, without querying Qt data roles for each entry.
        """
        selection = QItemSelection()
        for row, kept in keepers.items():
            if kept is None or not 0 <= row < len(self._groups):
                continue
            nodes = self._groups[row].nodes
            parent = self.index(row, 0)
            start = 0
            found = False
            for position, node in enumerate(nodes):
                if node is kept:
                    found = True
                    if start < position:
                        selection.select(self.index(start, 0, parent),
                                         self.index(position - 1, len(COLUMNS) - 1, parent))
                    start = position + 1
            if found and start < len(nodes):
                selection.select(self.index(start, 0, parent),
                                 self.index(len(nodes) - 1, len(COLUMNS) - 1, parent))
        return selection


def build_view(model: GroupedListModel) -> QTreeView:
    """A tree view over ``model`` in which several entry lines can be selected."""
    view = QTreeView()
    view.setModel(model)
    view.setUniformRowHeights(True)
    view.setAlternatingRowColors(True)
    view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    view.header().setStretchLastSection(False)
    return view


def fill(model: GroupedListModel, view: QTreeView, groups: Sequence[tuple[str, Sequence[Node]]], unit: str,
         *, tips: Sequence[str] | None = None, keepers: Sequence[Node | None] | None = None,
         icons: Mapping[Node, QIcon] | None = None) -> None:
    """Show ``groups`` (a title and its entries, in the order given), all opened; ``tips``: one tooltip per group."""
    model.set_groups(groups, unit, tips=tips, keepers=keepers, icons=icons)
    for row in range(model.rowCount()):
        view.setFirstColumnSpanned(row, QModelIndex(), True)  # a group's line runs across the columns
    for column, width in _COLUMN_WIDTHS.items():
        view.setColumnWidth(column, width)
    view.header().setSectionResizeMode(_FOLDER_COLUMN, QHeaderView.ResizeMode.Stretch)
    for row in range(model.rowCount()):
        view.expand(model.index(row, 0))


def select_entries(model: GroupedListModel, view: QTreeView, *, skip_first: bool) -> None:
    """Select the entry lines of every group (with ``skip_first``, all but each group's first), focusing the view."""
    selection = QItemSelection()
    start = 1 if skip_first else 0
    for row in range(model.rowCount()):
        group = model.index(row, 0)
        count = model.rowCount(group)
        if count > start:
            selection.select(model.index(start, 0, group), model.index(count - 1, len(COLUMNS) - 1, group))
    view.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    view.setFocus()


def select_group(model: GroupedListModel, view: QTreeView, row: int, *, append: bool = False) -> None:
    """Select the entry lines of the group on line ``row``, focusing the view."""
    group = model.index(row, 0)
    count = model.rowCount(group)
    selection = QItemSelection()
    if count:
        selection.select(model.index(0, 0, group), model.index(count - 1, len(COLUMNS) - 1, group))
    flag = QItemSelectionModel.SelectionFlag.Select if append else QItemSelectionModel.SelectionFlag.ClearAndSelect
    view.selectionModel().select(selection, flag)
    view.setFocus()
