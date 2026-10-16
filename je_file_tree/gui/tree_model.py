"""The folder tree as a Qt item model.

The model wraps the scanned ``Node`` tree directly, without copying it, so a
tree of millions of entries costs nothing extra to show: rows are created only
when a folder is expanded. The scanner leaves every folder's children sorted
largest first; any other order is kept per folder in this model and computed
the first time that folder is shown, so changing the sort column costs nothing
up front either.

Large persistent selections share one sibling lookup pass and cache only their
requested rows, rather than repeatedly searching the same wide folder.

While a scan is still running (``live``), worker threads keep appending
children and growing sizes. The model then shows, for each folder, a sorted
copy of its children taken the first time its rows are asked for, and keeps
using that copy until ``refresh()``: the view never sees a list change under
it, including initially empty groups. Expander checks only inspect child presence;
they do not sort, copy or freeze unopened groups.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, QObject, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QStyle

from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_share, format_size, format_time
from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node, detach_many
from je_file_tree.gui.node_text import node_name, node_path
from je_file_tree.core.scanner import EXCLUDED, NOT_SCANNED
from je_file_tree.core.snapshot import unpack_snapshot
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.reasons import problem_text

NAME, SIZE, ALLOCATED, SHARE, DRIVE_SHARE, FILES, FOLDERS, MODIFIED, ACCESSED, CREATED = range(10)
ACCOUNTED_SIZE, ACCOUNTED_ALLOCATED = 10, 11
COLUMN_KEYS = ("column_name", "column_size", "column_allocated", "column_share", "column_drive_share",
               "column_files", "column_folders",
               "column_modified", "column_accessed", "column_created", "column_accounted_size",
               "column_accounted_allocated")
NODE_ROLE = Qt.ItemDataRole.UserRole + 1
SHARE_ROLE = Qt.ItemDataRole.UserRole + 2

_NUMERIC_COLUMNS = (SIZE, ALLOCATED, SHARE, DRIVE_SHARE, FILES, FOLDERS, ACCOUNTED_SIZE, ACCOUNTED_ALLOCATED)
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
# 100k siblings: 8 individual lookups 3.64 ms vs batch 5.50 ms; 16 take 7.03 vs 5.69 ms.
# At 1,000 requested files: 408.98 vs 6.28 ms (2026-10-16). Keep small selections on the C list search.
_BATCHED_ROW_MINIMUM = 16
_LAYOUT_CHANGE_SIGNATURE = ("QList<QPersistentModelIndex>", "QAbstractItemModel::LayoutChangeHint")

ModelIndex = QModelIndex | QPersistentModelIndex


def sort_key(column: int) -> Callable[[Node], Any]:
    """The ascending sort key of a column (folders before files for the name column)."""
    keys: dict[int, Callable[[Node], Any]] = {
        NAME: lambda node: (not node.is_dir, node.name.lower()),
        SIZE: lambda node: node.size,
        ALLOCATED: lambda node: node.allocated,
        SHARE: lambda node: node.size,
        DRIVE_SHARE: lambda node: node.size,
        FILES: lambda node: node.file_count,
        FOLDERS: lambda node: node.dir_count,
        MODIFIED: lambda node: node.modified,
        ACCESSED: lambda node: node.accessed or -1,
        CREATED: lambda node: node.created or -1,
        ACCOUNTED_SIZE: lambda node: node.accounted_size,
        ACCOUNTED_ALLOCATED: lambda node: node.accounted_allocated,
    }
    return keys[column]


class FolderTreeModel(QAbstractItemModel):
    """Shows one scanned tree: the scanned folder is the single top-level row."""

    archive_requested = Signal(object)
    archives_invalidated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root: Node | None = None
        self._live = False
        self._unit = AUTO_UNIT
        self._drive_total: int | None = None
        self._sort_column = SIZE
        self._sort_order = Qt.SortOrder.DescendingOrder
        self._preserving_sort = False
        self._orders: dict[int, list[Node]] = {}
        self._rows: dict[int, int] = {}
        self._queried_parents: set[Node] = set()
        self._size_order_changed: set[Node] = set()
        self._icons: dict[str, QIcon] = {}
        self._archives: dict[Node, list[VirtualEntry]] = {}
        self._archive_done: set[Node] = set()
        self._archive_errors: dict[Node, str] = {}
        self._texts: dict[int, Callable[[Node], str]] = {
            NAME: node_name,
            SIZE: lambda node: format_size(node.size, self._unit),
            ALLOCATED: lambda node: "" if node.is_link else format_size(node.allocated, self._unit),
            ACCOUNTED_SIZE: lambda node: format_size(node.accounted_size, self._unit),
            ACCOUNTED_ALLOCATED: lambda node: format_size(node.accounted_allocated, self._unit),
            SHARE: lambda node: format_share(node.share_of_parent()),
            DRIVE_SHARE: lambda node: (format_share(share) if (share := self._drive_share(node)) is not None
                                       else tr("size_unknown")),
            MODIFIED: lambda node: format_time(node.modified),
            ACCESSED: lambda node: format_time(node.accessed) if node.accessed is not None else tr("size_unknown"),
            CREATED: lambda node: format_time(node.created) if node.created is not None else tr("size_unknown"),
        }
        self._node_role = lambda node, _column: node
        self._roles: dict[int, Callable[[Node, int], Any]] = {
            Qt.ItemDataRole.DisplayRole: self._display,
            Qt.ItemDataRole.TextAlignmentRole: lambda _node, column: _RIGHT if column in _NUMERIC_COLUMNS else None,
            Qt.ItemDataRole.DecorationRole: lambda node, column: self._icon(node) if column == NAME else None,
            Qt.ItemDataRole.ToolTipRole: self._column_tooltip,
            NODE_ROLE: self._node_role,
            SHARE_ROLE: lambda node, column: (self._drive_share(node) if column == DRIVE_SHARE
                                              else node.share_of_parent()),
            Qt.ItemDataRole.ForegroundRole: lambda node, _column: _muted() if node.error == EXCLUDED else None,
        }

    # --- public API -------------------------------------------------------

    def _column_tooltip(self, node: Node, column: int) -> str:
        if column in (ACCOUNTED_SIZE, ACCOUNTED_ALLOCATED):
            return tr("hard_links_hint")
        if column in (ACCESSED, CREATED):
            return tr("file_times_hint")
        return tr("drive_share_tip") if column == DRIVE_SHARE else self._tooltip(node)

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
        self.invalidate_archives()
        self._root = root
        self._drive_total = None
        self._live = live and root is not None
        self._queried_parents.clear()
        self._size_order_changed.clear()
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
        if unit == self._unit:
            return
        self._unit = unit
        self._repaint(((SIZE, ALLOCATED), (ACCOUNTED_SIZE, ACCOUNTED_ALLOCATED)), [Qt.ItemDataRole.DisplayRole])

    def set_drive_total(self, total: int | None) -> None:
        """Set worker-measured volume capacity; unknown/stale capacity never displays as zero."""
        normalized = total if total is not None and total > 0 else None
        if normalized == self._drive_total:
            return
        self._drive_total = normalized
        self._repaint(((DRIVE_SHARE, DRIVE_SHARE),), [Qt.ItemDataRole.DisplayRole, SHARE_ROLE])

    def _drive_share(self, node: Node) -> float | None:
        root = self._root
        if self._drive_total is None or root is None or root.snapshot is None or node.snapshot is None:
            return None
        if unpack_snapshot(root.snapshot).device != unpack_snapshot(node.snapshot).device:
            return None
        return node.size / self._drive_total

    def retranslate(self) -> None:
        """Re-read the translated header texts."""
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(COLUMN_KEYS) - 1)

    def node(self, index: ModelIndex) -> Node | None:
        """The real filesystem node; virtual archive entries never authorize file actions."""
        entry = self._entry(index)
        return None if isinstance(entry, VirtualEntry) else entry

    def node_at(self, row: int, parent: ModelIndex) -> Node | None:
        """Read a real source row in view order without a Qt index; virtual preview rows return None."""
        if self._root is None:
            return None
        if not parent.isValid():
            entry = self._root if row == 0 else None
        else:
            folder = self._entry(parent)
            children = self._ordered(folder) if folder is not None else []
            entry = children[row] if 0 <= row < len(children) else None
        return None if isinstance(entry, VirtualEntry) else entry

    def plain_row_selection(self) -> bool:
        """Whether complete selected ranges can use recorded identities without custom cell semantics."""
        overrides = ("data", "entry_data", "flags", "_entry", "_virtual_data", "columnCount")
        return (type(self) is FolderTreeModel and type(self).flags is QAbstractItemModel.flags
                and not any(name in self.__dict__ for name in overrides)
                and self._roles.get(NODE_ROLE) is self._node_role)

    def row_nodes(self, first: int, last: int, parent: ModelIndex) -> list[Node]:
        """Copy only real node references in one selected interval, without Qt indexes or descendants."""
        if first < 0 or last < first or (parent.isValid() and (parent.model() is not self or parent.column() != 0)):
            return []
        folder = self._entry(parent)
        if parent.isValid() and (folder is None or isinstance(folder, VirtualEntry)):
            return []
        rows = self.filesystem_rows(folder) if folder is not None else [self._root]
        return [node for node in rows[first:last+1] if node is not None and not isinstance(node, VirtualEntry)]

    def filesystem_rows(self, parent: Node) -> list[Node] | tuple[()]:
        """Borrow current real-row candidates in source order; archive preview groups are wholly virtual."""
        return () if parent in self._archives else self._ordered(parent)

    def _entry(self, index: ModelIndex) -> Node | None:
        if not index.isValid():
            return None
        return index.internalPointer()

    def index_for(self, node: Node) -> QModelIndex:
        """The index of ``node`` in column 0 (invalid when it is not in this tree)."""
        if not self._visible(node):
            return QModelIndex()
        if node is self._root:
            return self.createIndex(0, 0, node)
        parent = node.parent
        if parent is None:
            return QModelIndex()
        row = self._row_of(node)
        return self.createIndex(row, 0, node) if row >= 0 else QModelIndex()

    def indexes_for(self, nodes: Iterable[Node]) -> list[QModelIndex]:
        """Find column-zero indexes in input order, batching wide sibling searches and keeping invalid slots."""
        entries = list(nodes)
        self._prime_rows([(node, 0) for node in entries])
        return [self.index_for(node) for node in entries]

    def remove(self, node: Node) -> None:
        """Take ``node`` out of the tree after it was deleted from disk, updating every total above it."""
        self.remove_many((node,))

    def remove_many(self, nodes: Iterable[Node]) -> None:
        """Apply completed real-entry moves in one layout, retaining unaffected persistent indexes.

        Only this model's captured non-root filesystem entries are eligible. Virtual previews never
        authorize mutations. Sibling filtering preserves the scanner's order without subtree walks.
        Invalidate the old drive-capacity metadata in the same layout as the completed moves.
        """
        chosen = [node for node in nodes if node is not self._root and not isinstance(node, VirtualEntry)
                  and self._visible(node)]
        if not chosen:
            return
        parents = {node.parent for node in chosen if node.parent is not None}

        def change() -> None:
            self.invalidate_archives()
            self._drive_total = None
            detach_many(chosen)
            for parent in parents:
                self._invalidate_size_order(parent.parent)
        # 80 completed moves previously caused 80 full relayouts (2026-10-16).
        # General structural layout changes must not use the completed-sort hint.
        self._relayout(change)

    # --- QAbstractItemModel ------------------------------------------------

    def index(self, row: int, column: int, parent: ModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        """Qt: the index of a child of ``parent``."""
        if self._root is None or not 0 <= column < len(COLUMN_KEYS):
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(0, column, self._root) if row == 0 else QModelIndex()
        folder = self._entry(parent)
        children = self._ordered(folder) if folder is not None else []
        if not 0 <= row < len(children):
            return QModelIndex()
        return self.createIndex(row, column, children[row])

    def parent(self, index: ModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        """Qt: the index of the folder that holds ``index``."""
        node = self._entry(index)
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
        node = self._entry(parent)
        return len(self._ordered(node)) if node is not None else 0

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Qt: the number of columns."""
        return len(COLUMN_KEYS)

    def hasChildren(self, parent: ModelIndex = QModelIndex()) -> bool:  # noqa: B008
        """Qt: inspect existing/frozen child presence without sorting or copying unopened rows."""
        if not parent.isValid():
            return self._root is not None
        node = self._entry(parent)
        if parent.column() != 0 or node is None:
            return False
        return self.has_entry_children(node)

    def has_entry_children(self, node: Node | VirtualEntry) -> bool:
        """Inspect cached/raw child presence and preview eligibility without creating rows or sorting."""
        children = self._orders.get(id(node))
        if children is None:
            children = self._archives.get(node, node.children)
        # Ten unopened folders: the old check sorted/copied 200k rows (101.82 ms, 2026-10-16).
        return bool(children) or self.can_preview(node)

    def canFetchMore(self, parent: ModelIndex) -> bool:
        """Offer archive expansion only for completed, recorded regular-file entries."""
        return parent.column() == 0 and self.can_preview(self.node(parent))

    def can_preview(self, node: Node | VirtualEntry | None) -> bool:
        """Check the existing archive offer on this GUI thread without constructing a source index."""
        return bool(not self._live and node is not None and not isinstance(node, VirtualEntry)
                    and not node.is_dir and not node.is_link and node.error is None and node.snapshot is not None
                    and node not in self._archives and node not in self._archive_done
                    and node.name.lower().endswith((".zip", ".7z", ".rar")))

    def fetchMore(self, parent: ModelIndex) -> None:
        """Request metadata on expansion; the controller owns worker execution."""
        if self.canFetchMore(parent):
            node = self.node(parent)
            self.set_archive(node, [VirtualEntry(tr("archive_loading"), False, parent=node)])
            self.archive_requested.emit(node)

    def set_archive(self, node: Node, children: list[VirtualEntry]) -> None:
        """Replace display-only children without changing scan totals or real children."""
        index = self.index_for(node)
        if not index.isValid():
            return
        old = self._archives.get(node, [])
        if old:
            self.beginRemoveRows(index, 0, len(old) - 1)
            self._archives.pop(node, None)
            self._clear_caches()
            self.endRemoveRows()
        self._archive_done.add(node)
        if children:
            self.beginInsertRows(index, 0, len(children) - 1)
            self._archives[node] = children
            self._clear_caches()
            self.endInsertRows()
        self.dataChanged.emit(index, index)

    def invalidate_archives(self) -> None:
        """Invalidate metadata replies before any real tree replacement or mutation."""
        self.archives_invalidated.emit()
        self._archives.clear()
        self._archive_done.clear()
        self._archive_errors.clear()

    def archive_error(self, node: Node, reason: str) -> None:
        """Leave unavailable archives as plain files and expose failure in their tooltip."""
        self._archive_errors[node] = reason[:500]
        self.set_archive(node, [])

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
        return self.entry_data(self._entry(index), index.column(), role)

    def entry_data(self, node: Node | VirtualEntry | None, column: int, role: int) -> Any:
        """Format one recorded entry without allocating a Qt index; virtual rows remain read-only."""
        handler = self._roles.get(role)
        if node is None or handler is None:
            return None
        if isinstance(node, VirtualEntry):
            return self._virtual_data(node, column, role)
        return handler(node, column)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Qt: order every folder's children by ``column``; folders are re-sorted when next shown."""
        if not 0 <= column < len(COLUMN_KEYS):
            return
        if self._preserving_sort and (column, order) == (self._sort_column, self._sort_order):
            return

        def change() -> None:
            self._sort_column = column
            self._sort_order = order
        # Only completed sorts preserve every row and parent; live scans may have appended children.
        # Windows QTreeView, 100k rows / 1k selected: 2.009 s -> 0.094–0.170 s with this hint (2026-10-16).
        hint = (QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint if self._live
                else QAbstractItemModel.LayoutChangeHint.VerticalSortHint)
        self._relayout(change, hint=hint)

    @contextmanager
    def preserve_sort(self) -> Iterator[None]:
        """Skip identical sort requests during view rebinding; changed keys and explicit refresh still apply."""
        previous = self._preserving_sort
        self._preserving_sort = True
        try:
            yield
        finally:
            self._preserving_sort = previous

    def _relayout(self, change: Callable[[], None], *,
                  hint: QAbstractItemModel.LayoutChangeHint = QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint
                  ) -> None:
        """Apply ``change``, drop the cached orders and move every persistent index to its node's new row.

        The view keeps its expanded folders, selection and current item as
        persistent indexes, so they all follow their nodes.
        """
        self.layoutAboutToBeChanged[_LAYOUT_CHANGE_SIGNATURE].emit([], hint)
        persistent = self.persistentIndexList()
        nodes = [(self._entry(index), index.column()) for index in persistent]
        change()
        self._clear_caches()
        self._prime_rows(nodes)
        replacements = [self._index_at(node, column_number) for node, column_number in nodes]
        self.changePersistentIndexList(persistent, replacements)
        self.layoutChanged[_LAYOUT_CHANGE_SIGNATURE].emit([], hint)

    # --- helpers -----------------------------------------------------------

    def replace(self, old: Node, new: Node) -> None:
        """Swap a rescanned folder into the tree (``Node.replace_with``), keeping what the view still can.

        Expanded folders and the selection that were inside the old branch are
        dropped; everywhere else they follow their nodes as after a sort.
        """
        def change() -> None:
            self.invalidate_archives()
            parent = old.parent
            old.replace_with(new)
            self._invalidate_size_order(parent)
        self._relayout(change)

    def _index_at(self, node: Node | None, column: int) -> QModelIndex:
        if node is None:
            return QModelIndex()
        index = self.index_for(node)
        return index.siblingAtColumn(column) if index.isValid() else index

    def _visible(self, node: Node) -> bool:
        root = self._root
        if root is None:
            return False
        ancestor: Node | None = node
        while ancestor is not None and ancestor is not root:
            ancestor = ancestor.parent
        if ancestor is None:
            return False
        if not isinstance(node, VirtualEntry):
            return True
        if node is root:
            return True
        ancestors = []
        parent = node.parent
        while isinstance(parent, VirtualEntry) and parent is not root:
            ancestors.append(parent)
            parent = parent.parent
        return ((parent is root or parent in self._archives)
                and all(self._row_of(entry) >= 0 for entry in reversed(ancestors)))

    def _prime_rows(self, nodes: list[tuple[Node | None, int]]) -> None:
        """Locate large persistent selections once per visible parent, retaining only requested rows."""
        parents: dict[Node, set[Node]] = {}
        for node, _column in nodes:
            if node is not None and node.parent is not None and self._visible(node):
                parents.setdefault(node.parent, set()).add(node)
        for parent, wanted in parents.items():
            if len(wanted) < _BATCHED_ROW_MINIMUM:
                continue
            for row, child in enumerate(self._ordered(parent)):
                if child in wanted:
                    self._rows[id(child)] = row
                    wanted.remove(child)
                    if not wanted:
                        break
            for missing in wanted:
                self._rows[id(missing)] = -1

    def _clear_caches(self) -> None:
        self._orders.clear()
        self._rows.clear()
        for folder in tuple(self._size_order_changed):
            if not self._visible(folder):
                self._size_order_changed.discard(folder)
        for parent in tuple(self._queried_parents):
            if not self._visible(parent):
                self._queried_parents.discard(parent)

    def _invalidate_size_order(self, folder: Node | None) -> None:
        """Mark parents of resized entries, without reading sibling or descendant collections."""
        if folder is None or not self._visible(folder):
            return
        while folder is not None and folder not in self._size_order_changed:
            self._size_order_changed.add(folder)
            if folder is self._root:
                break
            folder = folder.parent

    def _repaint(self, columns: tuple[tuple[int, int], ...], roles: list[int]) -> None:
        """Notify queried sibling groups only; formatting never changes membership or frozen live orders."""
        if self._root is None:
            return
        groups = [(QModelIndex(), 1)]
        for parent in tuple(self._queried_parents):
            index = self.index_for(parent)
            if not index.isValid():
                self._queried_parents.discard(parent)
                continue
            count = len(self._ordered(parent))
            if count:
                groups.append((index, count))
        # Windows 100k rows / 1k selected: old full layout cost 455–504 ms for text/capacity (2026-10-16).
        for parent_index, count in groups:
            for first, last in columns:
                self.dataChanged.emit(self.index(0, first, parent_index),
                                      self.index(count - 1, last, parent_index), roles)

    def _ordered(self, folder: Node) -> list[Node] | tuple[()]:
        """``folder``'s children in the current sort order (a frozen copy while the scan is live)."""
        cached = self._orders.get(id(folder))
        # Sampled native 100k rows / 1k selected: first Name-sorted query 3.59 s -> 3.34 s (2026-10-17).
        if cached is not None:
            return cached
        children = self._archives.get(folder, folder.children)
        if children:
            self._queried_parents.add(folder)
        if not self._live and (not children or (self._sort_column in (SIZE, SHARE, DRIVE_SHARE)
                                               and self._sort_order == Qt.SortOrder.DescendingOrder
                                               and folder not in self._size_order_changed)):
            return children
        descending = self._sort_order == Qt.SortOrder.DescendingOrder
        cached = sorted(list(children), key=sort_key(self._sort_column), reverse=descending)
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

    def _display(self, node: Node, column: int) -> str:
        text = self._texts.get(column)
        if text is not None:
            return text(node)
        if not node.is_dir or node.is_link:
            return ""  # the file and folder counts are for folders only
        return format_count(node.file_count if column == FILES else node.dir_count)

    def _virtual_data(self, node: VirtualEntry, column: int, role: int) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            texts = {NAME: tr("archive_virtual_name", name=node.name),
                     SIZE: format_size(node.size, self._unit) if node.member else ""}
            return texts.get(column, "")
        if role == Qt.ItemDataRole.ToolTipRole:
            return tr("archive_virtual_hint")
        if role == Qt.ItemDataRole.DecorationRole and column == NAME:
            return self._icon(node)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _RIGHT if column in _NUMERIC_COLUMNS else None
        return None

    def _tooltip(self, node: Node) -> str:
        if node.error == NOT_SCANNED:
            return tr("tooltip_not_scanned", path=node.path)
        if node.error == EXCLUDED:
            return tr("tooltip_excluded", path=node.path)
        if node.error:
            return tr("tooltip_unreadable", path=node.path, reason=problem_text(node.error))
        if node.is_link:
            return tr("tooltip_link", path=node.path)
        extra = (tr("archive_failed", reason=self._archive_errors[node]) if node in self._archive_errors
                 else tr("archive_virtual_hint") if node in self._archives else "")
        return node_path(node) + ("\n" + extra if extra else "")

    def _icon(self, node: Node) -> QIcon:
        if node.error == EXCLUDED:
            key = "folder"  # skipped on purpose: not a problem, only greyed out
        elif node.error:
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


def _muted() -> QColor:
    """The greyed-out text colour of the current style (for skipped folders)."""
    return QApplication.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
