"""Flat result lists: the largest files, space per file type, and the entries that could not be read."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPersistentModelIndex, Qt

from file_tree.core.analysis import AGES, AgeStat, ExtensionStat
from file_tree.core.formatting import AUTO_UNIT, format_count, format_share, format_size, format_time
from file_tree.core.node import Node
from file_tree.gui.i18n import tr
from file_tree.gui.reasons import problem_text
from file_tree.gui.tree_model import NODE_ROLE, SHARE_ROLE

SORT_ROLE = Qt.ItemDataRole.UserRole + 10
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

Row = TypeVar("Row")


@dataclass(frozen=True, slots=True)
class Column(Generic[Row]):
    """One column of a table: its translated title key, the text it shows and the value it sorts by."""

    title_key: str
    text: Callable[[Row], str]
    sort_value: Callable[[Row], Any]
    numeric: bool = False


class _TableModel(QAbstractTableModel, Generic[Row]):
    """A read-only table over a list of rows."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[Row] = []
        self.unit = AUTO_UNIT
        self._columns = self.build_columns()

    def build_columns(self) -> Sequence[Column[Row]]:
        """The columns of this table (called once)."""
        raise NotImplementedError

    def columns(self) -> Sequence[Column[Row]]:
        """The columns of this table."""
        return self._columns

    def set_rows(self, rows: Sequence[Row]) -> None:
        """Replace the rows."""
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rows(self) -> list[Row]:
        """A copy of the rows, in model order."""
        return list(self._rows)

    def row_at(self, row: int) -> Row | None:
        """The row object at ``row`` (None when out of range)."""
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def refresh(self) -> None:
        """Repaint every cell and header (after a unit or language change)."""
        if self._rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, self.columnCount() - 1))
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, self.columnCount() - 1)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Qt: the number of rows."""
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        """Qt: the number of columns."""
        return 0 if parent.isValid() else len(self.columns())

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Qt: the translated column titles."""
        columns = self.columns()
        if orientation != Qt.Orientation.Horizontal or not 0 <= section < len(columns):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return tr(columns[section].title_key)
        if role == Qt.ItemDataRole.TextAlignmentRole and columns[section].numeric:
            return _RIGHT
        return None

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Qt: what a cell shows."""
        row = self.row_at(index.row())
        if row is None or not index.isValid():
            return None
        column = self.columns()[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return column.text(row)
        if role == SORT_ROLE:
            return column.sort_value(row)
        if role == Qt.ItemDataRole.TextAlignmentRole and column.numeric:
            return _RIGHT
        return self.extra_data(row, role)

    def extra_data(self, row: Row, role: int) -> Any:
        """Other roles a table supports (tooltips, the node behind a row...)."""
        return None


class LargestFilesModel(_TableModel[Node]):
    """The largest files of the scan."""

    def build_columns(self) -> Sequence[Column[Node]]:
        """Name, size, folder, modified."""
        return (
            Column("column_name", lambda node: node.name, lambda node: node.name.lower()),
            Column("column_size", lambda node: format_size(node.size, self.unit), lambda node: node.size,
                   numeric=True),
            Column("column_folder", _folder_of, _folder_of),
            Column("column_modified", lambda node: format_time(node.modified), lambda node: node.modified),
        )

    def extra_data(self, row: Node, role: int) -> Any:
        """The node itself, and its full path as the tooltip."""
        if role == NODE_ROLE:
            return row
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.path
        return None


class FileTypesModel(_TableModel[ExtensionStat]):
    """Space taken per extension."""

    def __init__(self, parent: QObject | None = None) -> None:
        self._total = 0
        super().__init__(parent)

    def set_rows(self, rows: Sequence[ExtensionStat]) -> None:
        """Replace the rows; shares are relative to their sum."""
        self._total = sum(stat.size for stat in rows)
        super().set_rows(rows)

    def build_columns(self) -> Sequence[Column[ExtensionStat]]:
        """Extension, type, size, share, files."""
        return (
            Column("column_extension", _extension_text, lambda stat: stat.extension),
            Column("column_type", lambda stat: tr(f"category_{stat.category}"), lambda stat: stat.category),
            Column("column_size", lambda stat: format_size(stat.size, self.unit), lambda stat: stat.size,
                   numeric=True),
            Column("column_share_total", lambda stat: format_share(self._share(stat)), lambda stat: stat.size,
                   numeric=True),
            Column("column_files", lambda stat: format_count(stat.count), lambda stat: stat.count, numeric=True),
        )

    def extra_data(self, row: ExtensionStat, role: int) -> Any:
        """The share of the total, for the bar."""
        if role == SHARE_ROLE:
            return self._share(row)
        return None

    def _share(self, stat: ExtensionStat) -> float:
        return stat.size / self._total if self._total else 0.0


class AgeModel(_TableModel[AgeStat]):
    """Space taken per age group (time since files last changed)."""

    def __init__(self, parent: QObject | None = None) -> None:
        self._total = 0
        super().__init__(parent)

    def set_rows(self, rows: Sequence[AgeStat]) -> None:
        """Replace the rows; shares are relative to their sum."""
        self._total = sum(stat.size for stat in rows)
        super().set_rows(rows)

    def build_columns(self) -> Sequence[Column[AgeStat]]:
        """Age group, size, share, files."""
        return (
            Column("column_age", lambda stat: tr(f"age_{stat.age}"), lambda stat: AGES.index(stat.age)),
            Column("column_size", lambda stat: format_size(stat.size, self.unit), lambda stat: stat.size,
                   numeric=True),
            Column("column_share_total", lambda stat: format_share(self._share(stat)), lambda stat: stat.size,
                   numeric=True),
            Column("column_files", lambda stat: format_count(stat.count), lambda stat: stat.count, numeric=True),
        )

    def extra_data(self, row: AgeStat, role: int) -> Any:
        """The share of the total, for the bar."""
        if role == SHARE_ROLE:
            return self._share(row)
        return None

    def _share(self, stat: AgeStat) -> float:
        return stat.size / self._total if self._total else 0.0


class ProblemsModel(_TableModel[tuple[str, str]]):
    """Entries that could not be read, with the reason."""

    def build_columns(self) -> Sequence[Column[tuple[str, str]]]:
        """Path, problem."""
        return (
            Column("column_path", lambda row: row[0], lambda row: row[0].lower()),
            Column("column_problem", lambda row: problem_text(row[1]), lambda row: row[1]),
        )

    def extra_data(self, row: tuple[str, str], role: int) -> Any:
        """The full path as the tooltip."""
        return row[0] if role == Qt.ItemDataRole.ToolTipRole else None


def _folder_of(node: Node) -> str:
    return os.path.dirname(node.path)


def _extension_text(stat: ExtensionStat) -> str:
    return stat.extension or tr("no_extension")
