"""Read-only mounted-volume capacity and Trash overview on an owned cancellable worker."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import threading
from typing import Any

from PySide6.QtCore import QSortFilterProxyModel, QStorageInfo, QThread, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QLabel, QPushButton,
                              QStyledItemDelegate, QStyle, QStyleOptionProgressBar, QTableView, QVBoxLayout, QWidget)

from je_file_tree.core.allocation import allocation_unit
from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.trash_size import TrashUsage, trash_usage
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tables import SORT_ROLE, Column, _TableModel

_LIMIT = 256
_FREE_COLUMN = 5


def _sort_amount(amount: int | None) -> int:
    return -1 if amount is None else amount


@dataclass(frozen=True, slots=True)
class Volume:
    """Copied scalar storage values; POSIX transfer block sizes are not cluster allocation sizes."""

    root: str
    name: str
    filesystem: str
    total: int
    used: int | None
    available: int | None
    cluster: int | None
    trash: TrashUsage


class VolumesModel(_TableModel[Volume]):
    """Mounted root, filesystem, OS capacity, available space bar, cluster and Trash totals."""

    def _size(self, value: int | None) -> str:
        return tr("size_unknown") if value is None else format_size(value, self.unit)

    def build_columns(self) -> Sequence[Column[Volume]]:
        """Keep numeric sorting independent of translated units and unavailable metadata."""
        return (Column("volume_root", lambda row: row.root, lambda row: row.root),
                Column("volume_name", lambda row: row.name, lambda row: row.name.casefold()),
                Column("volume_fs", lambda row: row.filesystem, lambda row: row.filesystem),
                Column("volume_total", lambda row: self._size(row.total), lambda row: row.total, numeric=True),
                Column("volume_used", lambda row: self._size(row.used), lambda row: _sort_amount(row.used),
                       numeric=True),
                Column("volume_free", lambda row: self._size(row.available), lambda row: _sort_amount(row.available),
                       numeric=True),
                Column("volume_cluster", lambda row: self._size(row.cluster), lambda row: row.cluster or -1,
                       numeric=True),
                Column("volume_trash", self._trash_size, lambda row: row.trash.size, numeric=True),
                Column("volume_trash_count", lambda row: format_count(row.trash.count) if row.trash.complete
                       else tr("volume_trash_partial", known=format_count(row.trash.count)),
                       lambda row: row.trash.count, numeric=True))

    def _trash_size(self, row: Volume) -> str:
        size = self._size(row.trash.size)
        return size if row.trash.complete else tr("volume_trash_partial", known=size)

    def extra_data(self, row: Volume, role: int) -> Any:
        """Expose scalar volume information for activation, free-space bars and error tooltips."""
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.trash.error or tr("volume_hint")
        return None


class FreeSpaceDelegate(QStyledItemDelegate):
    """Paint an available-space bar with the native palette and the capacity text."""

    def paint(self, painter, option, index) -> None:
        """Qt: show available share for the corresponding copied volume row."""
        row = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(row, Volume) or row.total <= 0 or row.available is None:
            super().paint(painter, option, index)
            return
        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(2, 2, -2, -2)
        bar.palette = option.palette
        bar.state = option.state | QStyle.StateFlag.State_Horizontal
        bar.direction = option.direction
        bar.minimum, bar.maximum = 0, 1000
        bar.progress = max(0, min(1000, round(1000 * row.available / row.total)))
        bar.text = f"{index.data()} ({round(100 * row.available / row.total)}%)"
        bar.textVisible = True
        bar.textAlignment = Qt.AlignmentFlag.AlignCenter
        QApplication.style().drawControl(QStyle.ControlElement.CE_ProgressBar, bar, painter)


class VolumesWorker(QThread):
    """Construct/refresh Qt storage values and query Trash outside the GUI thread."""

    ready = Signal(object, int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.cancel = threading.Event()

    def run(self) -> None:
        """Emit a bounded completed overview; Stop suppresses partial/late results."""
        rows, count = [], 0
        for storage in QStorageInfo.mountedVolumes():
            if self.cancel.is_set():
                return
            storage.refresh()
            if not storage.isValid() or not storage.isReady() or storage.bytesTotal() <= 0:
                continue
            count += 1
            if len(rows) >= _LIMIT:
                continue
            root = storage.rootPath()
            trash = trash_usage(root, cancel=self.cancel)
            if trash is None:
                return
            rows.append(Volume(root, storage.displayName(), bytes(storage.fileSystemType()).decode("utf-8", "replace"),
                               storage.bytesTotal(), storage.bytesTotal() - storage.bytesFree()
                               if storage.bytesFree() >= 0 else None,
                               storage.bytesAvailable() if storage.bytesAvailable() >= 0 else None,
                               allocation_unit(root),
                               trash))
        if not self.cancel.is_set():
            self.ready.emit(rows, count)


class VolumesDialog(QDialog):
    """Choose a mounted root to scan without changing any filesystem entry."""

    scan_requested = Signal(str)

    def __init__(self, unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_volumes"))
        self.resize(1270, 540)
        self._closed = False
        self.model = VolumesModel(self)
        self.model.unit = unit
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        for column, width in enumerate((140, 140, 90, 100, 100, 190, 115, 130, 110)):
            self.view.setColumnWidth(column, width)
        self.view.setItemDelegateForColumn(_FREE_COLUMN, FreeSpaceDelegate(self.view))
        self.view.doubleClicked.connect(self._scan)
        install_copy(self.view)
        hint = QLabel(tr("volume_hint"))
        hint.setWordWrap(True)
        self.status = QLabel(tr("volume_reading"))
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (hint, self.view, self.status, self.stop_button, close):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self.worker = VolumesWorker(self)
        self.worker.ready.connect(self._show)
        self.worker.start()

    def _show(self, rows: list[Volume], count: int) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self.model.set_rows(rows)
        self.stop_button.setEnabled(False)
        self.status.setText(tr("volume_summary", shown=format_count(len(rows)), count=format_count(count)))

    def _scan(self, index) -> None:
        row = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(row, Volume):
            self.accept()
            self.scan_requested.emit(row.root)

    def stop(self) -> None:
        """Cancel the volume/Trash survey; native calls finish before the worker returns."""
        self.worker.cancel.set()
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def shutdown(self) -> None:
        """Join the owned survey before destroying the modal view."""
        self._closed = True
        self.worker.cancel.set()
        wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: ignore queued replies and join before closing."""
        self.shutdown()
        super().done(result)
