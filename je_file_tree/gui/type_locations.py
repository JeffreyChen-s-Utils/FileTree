"""Background extension locations and their small table model."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal

from je_file_tree.core.formatting import format_count, format_share, format_size
from je_file_tree.core.node import Node
from je_file_tree.core.type_locations import TypeLocation, type_locations
from je_file_tree.gui.tables import Column, _TableModel
from je_file_tree.gui.tree_model import NODE_ROLE


class TypeLocationsWorker(QThread):
    """Compute extension/age matches and folder totals off the GUI thread, with cancellation."""

    done = Signal(object)

    def __init__(self, root: Node, keep: Callable[[Node], bool], parent: QObject) -> None:
        super().__init__(parent)
        self.root, self.keep = root, keep
        self.cancel = threading.Event()

    def stop(self) -> None:
        """Cancel an obsolete focus request without waiting on the GUI thread."""
        self.cancel.set()

    def run(self) -> None:
        """Emit only complete, uncancelled bounded lists."""
        result = type_locations(self.root, self.keep, cancel=self.cancel)
        if result is not None:
            self.done.emit(result)


class TypeLocationsModel(_TableModel[TypeLocation]):
    """Matching bytes per direct containing folder, with shares against all matching bytes."""

    def __init__(self, parent: QObject) -> None:
        self.total = 0
        super().__init__(parent)

    def build_columns(self) -> Sequence[Column[TypeLocation]]:
        """Path, matching size, matching files and matching share."""
        return (
            Column('column_folder', lambda row: row.folder.path, lambda row: row.folder.path.lower()),
            Column('type_location_size', lambda row: format_size(row.size, self.unit), lambda row: row.size,
                   numeric=True),
            Column('column_files', lambda row: format_count(row.count), lambda row: row.count, numeric=True),
            Column('column_share_total', lambda row: format_share(row.size / self.total if self.total else 0),
                   lambda row: row.size, numeric=True),
        )

    def extra_data(self, row: TypeLocation, role: int) -> Any:
        """Carry the actual containing folder for selection/navigation."""
        if role == NODE_ROLE:
            return row.folder
        return row.folder.path if role == Qt.ItemDataRole.ToolTipRole else None
