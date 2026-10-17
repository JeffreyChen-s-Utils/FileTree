"""Lazy sibling mappings over worker-approved filesystem nodes, without per-row Qt filtering."""

from __future__ import annotations

from array import array
from bisect import bisect_left, bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QAbstractProxyModel, QModelIndex, QObject, Qt, SignalInstance

from je_file_tree.core.archives import VirtualEntry
from je_file_tree.core.node import Node
from je_file_tree.gui.tree_model import FolderTreeModel, ModelIndex, _LAYOUT_CHANGE_SIGNATURE

_FLAGS = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
_NO_HINT = QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint


@dataclass(slots=True)
class _Group:
    nodes: list[Node]
    # 100k rows: retained Python mapping cache 12.4 MB -> 1.6 MB with 64-bit row coordinates (2026-10-17).
    source_rows: array
    source_parent: QModelIndex

    def position(self, source_row: int) -> int | None:
        """Find an accepted source row in the compact increasing position buffer."""
        row = bisect_left(self.source_rows, source_row)
        return row if row < len(self.source_rows) and self.source_rows[row] == source_row else None


class ExpandedTreeProxy(QAbstractProxyModel):
    """Map queried sibling groups once; preserve the source's order, identities and native metadata."""

    # Native 100k rows / 1k selected: first query 3.16 s -> 2.46 s; GUI gap 2.52 s -> 1.31 s (2026-10-17).

    def __init__(self, source: FolderTreeModel | None, parent: QObject) -> None:
        super().__init__(parent)
        self.allowed: frozenset[int] = frozenset()
        self.searched: frozenset[Node] | None = None
        self._source: FolderTreeModel | None = None
        self._root: Node | None = None
        self._root_accepted: bool | None = None
        self._columns = 0
        self._groups: dict[Node, _Group] = {}
        self._links: list[tuple[SignalInstance, Callable[..., None]]] = []
        self._pending: tuple[list[QModelIndex], list[tuple[Node | None, int]]] | None = None
        self._hint = _NO_HINT
        self.setSourceModel(source)

    def setSourceModel(self, source: FolderTreeModel | None) -> None:
        """Qt: bind owned signal forwarding only while this filtered view needs the source."""
        if source is self._source:
            return
        for signal, callback in self._links:
            signal.disconnect(callback)
        self._links.clear()
        self.beginResetModel()
        super().setSourceModel(source)
        self._source = source
        self._reset_rows()
        if source is not None:
            self._connect_source(source)
        self.endResetModel()

    def _connect_source(self, source: FolderTreeModel) -> None:
        links = (
            (source.layoutAboutToBeChanged[_LAYOUT_CHANGE_SIGNATURE], self._about_layout),
            (source.layoutChanged[_LAYOUT_CHANGE_SIGNATURE], self._changed),
            (source.rowsAboutToBeInserted, self._about_rows), (source.rowsInserted, self._changed),
            (source.rowsAboutToBeRemoved, self._about_rows), (source.rowsRemoved, self._changed),
            (source.modelAboutToBeReset, self.beginResetModel), (source.modelReset, self._reset_finished),
            (source.dataChanged, self._data_changed),
            (source.headerDataChanged, self.headerDataChanged.emit), (source.destroyed, self._source_destroyed),
        )
        for signal, callback in links:
            signal.connect(callback)
            self._links.append((signal, callback))

    def _reset_rows(self) -> None:
        self._groups.clear()
        self._pending = None
        self._root_accepted = None
        source = self._source
        self._root = source.node_at(0, QModelIndex()) if source is not None else None
        self._columns = source.columnCount() if source is not None else 0

    def _reset_finished(self) -> None:
        self._reset_rows()
        self.endResetModel()

    def _source_destroyed(self) -> None:
        self._links.clear()
        self.beginResetModel()
        self._source = None
        self._reset_rows()
        self.endResetModel()

    def _about_layout(self, _parents: list, hint: QAbstractItemModel.LayoutChangeHint) -> None:
        self._begin_change(hint)

    def _about_rows(self, _parent: QModelIndex, _first: int, _last: int) -> None:
        self._begin_change(_NO_HINT)

    def _begin_change(self, hint: QAbstractItemModel.LayoutChangeHint) -> None:
        if self._pending is not None:
            return
        self._hint = hint
        self.layoutAboutToBeChanged[_LAYOUT_CHANGE_SIGNATURE].emit([], hint)
        indexes = self.persistentIndexList()
        self._pending = indexes, [(self._entry(index), index.column()) for index in indexes]

    def _changed(self, *_args: object) -> None:
        if self._pending is None:
            self._begin_change(_NO_HINT)
        indexes, entries = self._pending
        self._groups.clear()
        self._root_accepted = None
        nodes = [node for node, _column in entries if node is not None]
        mapped = iter(self._source.indexes_for(nodes) if self._source is not None else [])
        replacements = [self.mapFromSource(next(mapped).siblingAtColumn(column)) if node is not None
                        else QModelIndex() for node, column in entries]
        self.changePersistentIndexList(indexes, replacements)
        self._pending = None
        self.layoutChanged[_LAYOUT_CHANGE_SIGNATURE].emit([], self._hint)

    def invalidate(self) -> None:
        """Apply changed worker membership, retaining every surviving persistent node and column."""
        self._begin_change(_NO_HINT)
        self._changed()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        """Keep the compatibility row predicate without allocating source indexes or dispatching data."""
        source = self._source
        node = source.node_at(row, parent) if source is not None else None
        return node is not None and (node is self._root or id(node) in self.allowed)

    def _custom_filter(self) -> bool:
        return (type(self).filterAcceptsRow is not ExpandedTreeProxy.filterAcceptsRow
                or "filterAcceptsRow" in self.__dict__)

    def _accept_root(self) -> bool:
        if self._root_accepted is None:
            self._root_accepted = (self._root is not None
                                   and (not self._custom_filter() or self.filterAcceptsRow(0, QModelIndex())))
        return self._root_accepted

    def _group(self, parent: Node) -> _Group:
        cached = self._groups.get(parent)
        if cached is not None:
            return cached
        rows, positions = [], array("q")
        source = self._source
        if source is not None and source._visible(parent):
            custom = self._custom_filter()
            source_parent = source.index_for(parent) if custom else QModelIndex()
            for source_row, child in enumerate(source.filesystem_rows(parent)):
                accepted = (self.filterAcceptsRow(source_row, source_parent) if custom
                            else id(child) in self.allowed)
                if not isinstance(child, VirtualEntry) and accepted:
                    rows.append(child)
                    positions.append(source_row)
        cached = _Group(rows, positions, source.index_for(parent) if rows and source is not None else QModelIndex())
        self._groups[parent] = cached
        return cached

    def _entry(self, index: ModelIndex) -> Node | None:
        return index.internalPointer() if index.isValid() and index.model() is self else None

    def index(self, row: int, column: int, parent: ModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        """Qt: create only the requested index over a cached group of borrowed real nodes."""
        if self._root is None or self._root_accepted is False or row < 0 or not 0 <= column < self._columns:
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(0, column, self._root) if row == 0 and self._accept_root() else QModelIndex()
        node = self._entry(parent)
        if node is None or parent.column() != 0:
            return QModelIndex()
        rows = self._group(node).nodes
        return self.createIndex(row, column, rows[row]) if row < len(rows) else QModelIndex()

    def parent(self, index: ModelIndex = QModelIndex()) -> QModelIndex:  # noqa: B008
        """Qt: retain the single displayed root even when its original parent remains attached."""
        node = self._entry(index)
        if node is None or node is self._root or node.parent is None:
            return QModelIndex()
        return self.mapFromSource(self._group(node.parent).source_parent)

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Qt: mapping visits one explicitly queried source sibling group, never its descendants."""
        if self._root is None:
            return 0
        if not parent.isValid():
            return int(self._accept_root())
        node = self._entry(parent)
        return len(self._group(node).nodes) if node is not None and parent.column() == 0 else 0

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Qt: retain all source columns, including currently hidden ones."""
        return self._columns

    def row_nodes(self, first: int, last: int, parent: ModelIndex) -> list[Node]:
        """Copy real references from one visible selected interval in the current sibling mapping."""
        if first < 0 or last < first or not self._accept_root():
            return []
        if not parent.isValid():
            return [self._root] if first == 0 else []
        node = self._entry(parent)
        if node is None or parent.column() != 0:
            return []
        return self._group(node).nodes[first:last+1]

    def map_selection_rows(self, groups: dict[QModelIndex, list[int]]) -> dict[QModelIndex, list[int]]:
        """Project source row groups using numeric coordinates; hidden ancestors cannot create roots."""
        if self._source is None or not self._accept_root():
            return {}
        result = {}
        for parent, positions in groups.items():
            if not parent.isValid():
                if 0 in positions:
                    result[QModelIndex()] = [0]
                continue
            if parent.model() is not self._source or parent.column() != 0:
                continue
            mapped = self.mapFromSource(parent)
            if not mapped.isValid():
                continue
            group = self._group(self._source.node(parent))
            rows = [row for position in positions if (row := group.position(position)) is not None]
            if rows:
                result[mapped] = rows
        return result

    def mapFromSource(self, index: ModelIndex) -> QModelIndex:
        """Qt: virtual preview entries and indexes from foreign models never become real rows."""
        source = self._source
        if source is None or not index.isValid() or index.model() is not source or not self._accept_root():
            return QModelIndex()
        node = source.node(index)
        if node is self._root:
            return self.createIndex(0, index.column(), node)
        if node is None or node.parent is None or not source._visible(node):
            return QModelIndex()
        group = self._group(node.parent)
        row = group.position(index.row())
        if row is None or group.nodes[row] is not node:
            return QModelIndex()
        if not self._ancestors_mapped(node.parent, group):
            return QModelIndex()
        return self.createIndex(row, index.column(), node)

    def _ancestors_mapped(self, ancestor: Node, group: _Group) -> bool:
        while ancestor is not self._root:
            above = ancestor.parent
            if above is None:
                return False
            above_group = self._group(above)
            above_row = above_group.position(group.source_parent.row())
            if above_row is None or above_group.nodes[above_row] is not ancestor:
                return False
            ancestor, group = above, above_group
        return True

    def mapToSource(self, index: ModelIndex) -> QModelIndex:
        """Qt: validate current source membership before mapping a real filesystem node."""
        node = self._entry(index)
        if node is None or self._source is None:
            return QModelIndex()
        if node is self._root:
            source = self._source.index(0, index.column())
        else:
            group = self._group(node.parent)
            row = index.row()
            if row >= len(group.nodes) or group.nodes[row] is not node:
                return QModelIndex()
            source_row = group.source_rows[row]
            source = self._source.index(source_row, index.column(), group.source_parent)
        return source if self.mapFromSource(source) == index else QModelIndex()

    def hasChildren(self, parent: ModelIndex = QModelIndex()) -> bool:  # noqa: B008
        """Qt: expander checks skip unsearched groups and physical files' virtual preview rows."""
        source = self._source
        if source is None or self._root is None:
            return False
        if not parent.isValid():
            return self._accept_root()
        node = self._entry(parent)
        if node is None or parent.column() != 0:
            return False
        if self.searched is not None and (node not in self.searched or (not node.is_dir and not node.children)):
            return source.can_preview(node)
        if not source.has_entry_children(node):
            return False
        return bool(self._group(node).nodes) or source.can_preview(node)

    def flags(self, index: ModelIndex) -> Qt.ItemFlag:
        """Qt: reuse the native read-only mask; custom source permissions still delegate exactly."""
        source = self._source
        if source is None or not index.isValid() or index.model() is not self:
            return Qt.ItemFlag.NoItemFlags
        if type(source).flags is QAbstractItemModel.flags and "flags" not in source.__dict__:
            return _FLAGS
        return source.flags(self.mapToSource(index))

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Qt: format borrowed entries directly while preserving custom source data overrides."""
        source, node = self._source, self._entry(index)
        if source is None or node is None:
            return None
        if getattr(source.data, "__func__", None) is FolderTreeModel.data:
            return source.entry_data(node, index.column(), role)
        return source.data(self.mapToSource(index), role)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Qt: source translations, alignment and header notifications remain authoritative."""
        return self._source.headerData(section, orientation, role) if self._source is not None else None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Qt: let the source own sorting and remap this view through its layout notifications."""
        if self._source is not None:
            self._source.sort(column, order)

    def _data_changed(self, first: QModelIndex, last: QModelIndex, roles: list[int]) -> None:
        if (self._source is None or self._root is None or self._root_accepted is not True
                or first.parent() != last.parent()):
            return
        parent = first.parent()
        if not parent.isValid():
            self.dataChanged.emit(self.index(0, first.column()), self.index(0, last.column()), roles)
            return
        node = self._source.node(parent)
        cached = self._groups.get(node)
        if cached is None:
            return
        source_rows = cached.source_rows
        start, stop = bisect_left(source_rows, first.row()), bisect_right(source_rows, last.row())
        if start < stop:
            mapped_parent = self.mapFromSource(cached.source_parent)
            self.dataChanged.emit(self.index(start, first.column(), mapped_parent),
                                  self.index(stop-1, last.column(), mapped_parent), roles)
