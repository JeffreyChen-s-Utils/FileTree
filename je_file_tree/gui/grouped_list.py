"""A list of entries in named groups (Duplicates, Clean-up suggestions): one line per group, its entries below.

Each entry line shows name, size, folder and modified time and carries its node (``NODE_ROLE``), so
the results page's context menu, double-click and Delete work on it like on any other list.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTreeView

from je_file_tree.core.formatting import format_size, format_time
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.tree_model import NODE_ROLE

COLUMNS = ("column_name", "column_size", "column_folder", "column_modified")
_COLUMN_WIDTHS = {0: 200, 1: 80, 3: 125}
_FOLDER_COLUMN = 2
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def build_view(model: QStandardItemModel) -> QTreeView:
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


def fill(model: QStandardItemModel, view: QTreeView, groups: Sequence[tuple[str, Sequence[Node]]], unit: str) -> None:
    """Show ``groups`` (a title and its entries, in the order given), all opened."""
    model.clear()
    model.setHorizontalHeaderLabels([tr(key) for key in COLUMNS])
    for title, nodes in groups:
        head = QStandardItem(title)
        head.setEditable(False)
        for node in nodes:
            head.appendRow(_row(node.name, format_size(node.size, unit), os.path.dirname(node.path),
                                format_time(node.modified), node=node))
        model.appendRow(head)
    for row in range(model.rowCount()):
        view.setFirstColumnSpanned(row, QModelIndex(), True)  # a group's line runs across the columns
    for column, width in _COLUMN_WIDTHS.items():
        view.setColumnWidth(column, width)
    view.header().setSectionResizeMode(_FOLDER_COLUMN, QHeaderView.ResizeMode.Stretch)
    view.expandAll()


def select_entries(model: QStandardItemModel, view: QTreeView, *, skip_first: bool) -> None:
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


def _row(*texts: str, node: Node | None = None) -> list[QStandardItem]:
    """One line of items; an entry's line carries its node (``NODE_ROLE``) and its path as the tooltip."""
    items = []
    for column, text in enumerate(texts):
        item = QStandardItem(text)
        item.setEditable(False)
        if column == 1:
            item.setTextAlignment(_RIGHT)
        if node is not None:
            item.setData(node, NODE_ROLE)
            item.setToolTip(node.path)
        items.append(item)
    return items
