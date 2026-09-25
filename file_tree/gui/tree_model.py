"""The folder tree as a Qt item model.

The model wraps the scanned ``Node`` tree directly, without copying it, so a
tree of millions of entries costs nothing extra to show: rows are created only
when a folder is expanded. The scanner leaves every folder's children sorted
largest first; any other order is kept per folder in this model and computed
the first time that folder is shown, so changing the sort column costs nothing
up front either.

While a scan is still running (``live``), worker threads keep appending
children and growing sizes. The model then shows, for each folder, a sorted
copy of its children taken the first time the folder is asked for, and keeps
using that copy until ``refresh()``: the view never sees a list change under
it, and each refresh re-sorts by the sizes reached so far.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, QObject, QPersistentModelIndex, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle

from file_tree.core.formatting import AUTO_UNIT, format_count, format_share, format_size, format_time
from file_tree.core.node import Node
from file_tree.core.scanner import NOT_SCANNED
from file_tree.gui.i18n import tr
from file_tree.gui.reasons import problem_text

NAME, SIZE, SHARE, FILES, FOLDERS, MODIFIED = range(6)
COLUMN_KEYS = ("column_name", "column_size", "column_share", "column_files", "column_folders",
               "column_modified")
NODE_ROLE = Qt.ItemDataRole.UserRole + 1
SHARE_ROLE = Qt.ItemDataRole.UserRole + 2

_NUMERIC_COLUMNS = (SIZE, SHARE, FILES, FOLDERS)
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

ModelIndex = QModelIndex | QPersistentModelIndex


def sort_key(column: int) -> Callable[[Node], Any]:
    """The ascending sort key of a column (folders before files for the name column)."""
    keys: dict[int, Callable[[Node], Any]] = {
        NAME: lambda node: (not node.is_dir, node.name.lower()),
        SIZE: lambda node: node.size,
        SHARE: lambda node: node.size,
        FILES: lambda node: node.file_count,
        FOLDERS: lambda node: node.dir_count,
        MODIFIED: lambda node: node.modified,
    }
    return keys[column]


class FolderTreeModel(QAbstractItemModel):
    """Shows one scanned tree: the scanned folder is the single top-level row."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root: Node | None = None
        self._live = False
        self._unit = AUTO_UNIT
        self._sort_column = SIZE
        self._sort_order = Qt.SortOrder.DescendingOrder
        self._orders: dict[int, list[Node]] = {}
        self._rows: dict[int, int] = {}
        self._icons: dict[str, QIcon] = {}
        self._roles: dict[int, Callable[[Node, int], Any]] = {
            Qt.ItemDataRole.DisplayRole: self._display,
            Qt.ItemDataRole.TextAlignmentRole: lambda _node, column: _RIGHT if column in _NUMERIC_COLUMNS else None,
            Qt.ItemDataRole.DecorationRole: lambda node, column: self._icon(node) if column == NAME else None,
            Qt.ItemDataRole.ToolTipRole: lambda node, _column: self._tooltip(node),
            NODE_ROLE: lambda node, _column: node,
            SHARE_ROLE: lambda node, _column: node.share_of_parent(),
        }

    # --- public API -------------------------------------------------------

    @property
    def root(self) -> Node | None:
        """The scanned folder shown, or None before the first scan."""
        return self._root

    @property
    def live(self) -> bool:
        """Whether the tree shown is still being scanned."""
        return self._live

    def set_root(self, root: Node | None, *, live: bool = False) -> None:
        """Show a new tree (or nothing); ``live`` while the scan is still filling it in."""
        self.beginResetModel()
        self._root = root
        self._live = live and root is not None
        self._clear_caches()
        self.endResetModel()

    def refresh(self) -> None:
        """Show what a running scan has added since the last refresh, keeping expansion and selection."""
        self._relayout(lambda: None)

    def finish_live(self) -> None:
        """The scan is done: show its final, sorted tree without collapsing what the user opened."""
        def stop() -> None:
            self._live = False
        self._relayout(stop)

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit`` (``"auto"`` or one of ``SIZE_UNITS``)."""
        self._unit = unit
        self.layoutAboutToBeChanged.emit()
        self.layoutChanged.emit()

    def retranslate(self) -> None:
        """Re-read the translated header texts."""
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(COLUMN_KEYS) - 1)

    def node(self, index: ModelIndex) -> Node | None:
        """The node behind an index (None for the invisible root)."""
        if not index.isValid():
            return None
        return index.internalPointer()

    def index_for(self, node: Node) -> QModelIndex:
        """The index of ``node`` in column 0 (invalid when it is not in this tree)."""
        if self._root is None:
            return QModelIndex()
        if node is self._root:
            return self.createIndex(0, 0, node)
        parent = node.parent
        if parent is None:
            return QModelIndex()
        row = self._row_of(node)
        return self.createIndex(row, 0, node) if row >= 0 else QModelIndex()

    def remove(self, node: Node) -> None:
        """Take ``node`` out of the tree after it was deleted from disk, updating every total above it."""
        parent = node.parent
        if parent is None:
            return
        parent_index = self.index_for(parent)
        row = self._row_of(node)
        if row < 0:
            return
        self.beginRemoveRows(parent_index, row, row)
        node.detach()
        self._orders.pop(id(parent), None)
        self._rows.clear()
        self.endRemoveRows()
        ancestor: Node | None = parent
        while ancestor is not None:
            self._refresh_children(ancestor)
            ancestor = ancestor.parent
        if self._root is not None:
            self.dataChanged.emit(self.index(0, SIZE), self.index(0, MODIFIED))

    # --- QAbstractItemModel ------------------------------------------------

    def index(self, row: int, column: int, parent: ModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        """Qt: the index of a child of ``parent``."""
        if self._root is None or not 0 <= column < len(COLUMN_KEYS):
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(0, column, self._root) if row == 0 else QModelIndex()
        folder = self.node(parent)
        children = self._ordered(folder) if folder is not None else []
        if not 0 <= row < len(children):
            return QModelIndex()
        return self.createIndex(row, column, children[row])

    def parent(self, index: ModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        """Qt: the index of the folder that holds ``index``."""
        node = self.node(index)
        if node is None or node.parent is None:
            return QModelIndex()
        return self.index_for(node.parent)

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Qt: how many children ``parent`` has."""
        if self._root is None:
            return 0
        if not parent.isValid():
            return 1
        if parent.column() != 0:
            return 0
        node = self.node(parent)
        return len(self._ordered(node)) if node is not None else 0

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Qt: the number of columns."""
        return len(COLUMN_KEYS)

    def hasChildren(self, parent: ModelIndex = QModelIndex()) -> bool:  # noqa: B008
        """Qt: whether ``parent`` can be expanded (cheaper than counting rows)."""
        if not parent.isValid():
            return self._root is not None
        node = self.node(parent)
        return parent.column() == 0 and node is not None and bool(self._ordered(node))

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Qt: the translated column titles."""
        if orientation != Qt.Orientation.Horizontal or not 0 <= section < len(COLUMN_KEYS):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return tr(COLUMN_KEYS[section])
        if role == Qt.ItemDataRole.TextAlignmentRole and section in _NUMERIC_COLUMNS:
            return _RIGHT
        return None

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Qt: what a cell shows."""
        node = self.node(index)
        handler = self._roles.get(role)
        if node is None or handler is None:
            return None
        return handler(node, index.column())

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Qt: order every folder's children by ``column``; folders are re-sorted when next shown."""
        if not 0 <= column < len(COLUMN_KEYS):
            return

        def change() -> None:
            self._sort_column = column
            self._sort_order = order
        self._relayout(change)

    def _relayout(self, change: Callable[[], None]) -> None:
        """Apply ``change``, drop the cached orders and move every persistent index to its node's new row.

        The view keeps its expanded folders, selection and current item as
        persistent indexes, so they all follow their nodes.
        """
        self.layoutAboutToBeChanged.emit()
        persistent = self.persistentIndexList()
        nodes = [(self.node(index), index.column()) for index in persistent]
        change()
        self._clear_caches()
        replacements = [self._index_at(node, column_number) for node, column_number in nodes]
        self.changePersistentIndexList(persistent, replacements)
        self.layoutChanged.emit()

    # --- helpers -----------------------------------------------------------

    def replace(self, old: Node, new: Node) -> None:
        """Swap a rescanned folder into the tree (``Node.replace_with``), keeping what the view still can.

        Expanded folders and the selection that were inside the old branch are
        dropped; everywhere else they follow their nodes as after a sort.
        """
        self._relayout(lambda: old.replace_with(new))

    def _index_at(self, node: Node | None, column: int) -> QModelIndex:
        if node is None or not self._in_tree(node):
            return QModelIndex()
        index = self.index_for(node)
        return index.siblingAtColumn(column) if index.isValid() else index

    def _in_tree(self, node: Node) -> bool:
        """Whether ``node`` still hangs under the root (not in a branch that was replaced or removed)."""
        top = node
        while top.parent is not None:
            top = top.parent
        return top is self._root

    def _clear_caches(self) -> None:
        self._orders.clear()
        self._rows.clear()

    def _is_default_order(self) -> bool:
        return self._sort_column in (SIZE, SHARE) and self._sort_order == Qt.SortOrder.DescendingOrder

    def _ordered(self, folder: Node) -> list[Node] | tuple[()]:
        """``folder``'s children in the current sort order (a frozen copy while the scan is live)."""
        if not folder.children or (self._is_default_order() and not self._live):
            return folder.children
        cached = self._orders.get(id(folder))
        if cached is None:
            descending = self._sort_order == Qt.SortOrder.DescendingOrder
            cached = sorted(list(folder.children), key=sort_key(self._sort_column), reverse=descending)
            self._orders[id(folder)] = cached
        return cached

    def _row_of(self, node: Node) -> int:
        """``node``'s row under its parent (-1 when it is no longer there)."""
        row = self._rows.get(id(node))
        if row is not None:
            return row
        parent = node.parent
        if parent is None:
            return 0
        siblings = self._ordered(parent)
        if node.is_dir:
            for position, sibling in enumerate(siblings):
                if sibling.is_dir:
                    self._rows[id(sibling)] = position
            return self._rows.get(id(node), -1)
        try:
            return siblings.index(node)
        except ValueError:
            return -1

    def _refresh_children(self, folder: Node) -> None:
        """Repaint the numbers of every child of ``folder`` (their share of it changed)."""
        count = len(self._ordered(folder))
        parent_index = self.index_for(folder)
        if count and parent_index.isValid():
            self.dataChanged.emit(self.index(0, SIZE, parent_index),
                                  self.index(count - 1, MODIFIED, parent_index))

    def _display(self, node: Node, column: int) -> str:
        if column == NAME:
            return node.name
        if column == SIZE:
            return format_size(node.size, self._unit)
        if column == SHARE:
            return format_share(node.share_of_parent())
        if column == MODIFIED:
            return format_time(node.modified)
        if not node.is_dir or node.is_link:
            return ""
        return format_count(node.file_count if column == FILES else node.dir_count)

    def _tooltip(self, node: Node) -> str:
        if node.error == NOT_SCANNED:
            return tr("tooltip_not_scanned", path=node.path)
        if node.error:
            return tr("tooltip_unreadable", path=node.path, reason=problem_text(node.error))
        if node.is_link:
            return tr("tooltip_link", path=node.path)
        return node.path

    def _icon(self, node: Node) -> QIcon:
        if node.error:
            key = "error"
        elif node.is_link:
            key = "link_folder" if node.is_dir else "link_file"
        else:
            key = "folder" if node.is_dir else "file"
        icon = self._icons.get(key)
        if icon is None:
            pixmaps = {
                "error": QStyle.StandardPixmap.SP_MessageBoxWarning,
                "link_folder": QStyle.StandardPixmap.SP_DirLinkIcon,
                "link_file": QStyle.StandardPixmap.SP_FileLinkIcon,
                "folder": QStyle.StandardPixmap.SP_DirIcon,
                "file": QStyle.StandardPixmap.SP_FileIcon,
            }
            icon = QApplication.style().standardIcon(pixmaps[key])
            self._icons[key] = icon
        return icon
