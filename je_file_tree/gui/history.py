"""Local scan-history settings, cancellable reads and a size-over-time chart."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
import threading

from PySide6.QtCore import QPointF, QSettings, QStandardPaths, QThread, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QPushButton,
    QSpinBox, QTableView, QVBoxLayout, QWidget,
)

from je_file_tree.core.compare import SavedScan
from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.history import HistoryCancelledError, HistoryEntry, HistoryRead, ScanHistory, load_history
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.tables import Column, _TableModel

_MIB = 1024 * 1024
_DEFAULT_MIB = 1024
_MAX_MIB = 16384


def history_folder() -> Path:
    """Application-owned local metadata, outside the user's selected export locations."""
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "history"


def history_limit(settings: QSettings) -> int:
    """Read a validated 1–16384 MiB cap, falling back to 1 GiB for malformed saved settings."""
    value = settings.value("history_limit_mib", _DEFAULT_MIB)
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return _DEFAULT_MIB
    try:
        amount = int(value)
    except ValueError:
        return _DEFAULT_MIB
    return amount if 1 <= amount <= _MAX_MIB else _DEFAULT_MIB


def configured_history(settings: QSettings) -> ScanHistory | None:
    """Capture history options on the GUI thread for the next full scan; default is enabled."""
    enabled = settings.value("history_enabled", True)
    if enabled is False or str(enabled).lower() == "false":
        return None
    return ScanHistory(history_folder(), max_bytes=history_limit(settings) * _MIB)


class HistorySettings(QDialog):
    """Enable local metadata retention and choose its global cap; changing it affects future saves."""

    def __init__(self, settings: QSettings, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("action_history_settings"))
        self.enabled = QCheckBox(tr("history_enable"))
        self.enabled.setChecked(configured_history(settings) is not None)
        self.limit = QSpinBox()
        self.limit.setRange(1, _MAX_MIB)
        self.limit.setValue(history_limit(settings))
        self.limit.setSuffix(" MiB")
        self.limit.setEnabled(self.enabled.isChecked())
        self.enabled.toggled.connect(self.limit.setEnabled)
        hint = QLabel(tr("history_settings_hint"))
        hint.setWordWrap(True)
        layout = QFormLayout(self)
        layout.addRow(hint)
        layout.addRow(self.enabled)
        layout.addRow(tr("history_limit"), self.limit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


def _date(entry: HistoryEntry) -> str:
    return datetime.fromisoformat(entry.saved).astimezone().strftime("%Y-%m-%d %H:%M:%S")


class HistoryModel(_TableModel[HistoryEntry]):
    """Chronological, immutable metadata rows; the underlying recorded filesystem is never opened."""

    def build_columns(self) -> Sequence[Column[HistoryEntry]]:
        """Dates, logical totals, allocated named totals and explicit coverage."""
        return (Column("history_time", _date, lambda row: row.saved),
                Column("history_logical", lambda row: format_size(row.size, self.unit), lambda row: row.size,
                       numeric=True),
                Column("history_allocated", lambda row: format_size(row.allocated, self.unit),
                       lambda row: row.allocated, numeric=True),
                Column("history_coverage", lambda row: tr("history_incomplete" if row.incomplete
                                                         else "history_complete"), lambda row: row.incomplete))


class HistoryChart(QWidget):
    """A bounded size-over-time line plot, using timestamp spacing and the current window palette."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.entries: list[HistoryEntry] = []
        self.unit = "auto"
        self.setMinimumHeight(180)
        self.setAccessibleName(tr("history_chart"))

    def set_entries(self, entries: list[HistoryEntry], unit: str) -> None:
        """Use bounded scalar entries already read by the worker; expose an accessible range summary."""
        self.entries, self.unit = entries, unit
        if entries:
            self.setAccessibleDescription(tr("history_chart_range", first=_date(entries[0]), last=_date(entries[-1]),
                                             before=format_size(entries[0].size, unit),
                                             after=format_size(entries[-1].size, unit)))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Qt: draw total logical bytes; metadata rows retain all exact displayed values."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().base())
        area = self.rect().adjusted(100, 25, -25, -40)
        painter.setPen(self.palette().text().color())
        if not self.entries:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("history_empty"))
            return
        values = self.entries
        peak = max((entry.size for entry in values), default=1) or 1
        start, end = (datetime.fromisoformat(values[index].saved).timestamp() for index in (0, -1))
        painter.drawLine(area.bottomLeft(), area.bottomRight())
        painter.drawLine(area.bottomLeft(), area.topLeft())
        painter.drawText(5, area.top() + 10, format_size(peak, self.unit))
        painter.drawText(5, area.bottom(), "0")
        painter.drawText(area.left(), self.height() - 10, _date(values[0]))
        painter.drawText(area.right() - 145, self.height() - 10, _date(values[-1]))
        painter.setPen(QPen(self.palette().highlight().color(), 2))
        previous = None
        for entry in values:
            timestamp = datetime.fromisoformat(entry.saved).timestamp()
            fraction = (timestamp - start) / (end - start) if end > start else .5
            point = QPointF(area.left() + fraction * area.width(), area.bottom() - entry.size / peak * area.height())
            if previous is not None:
                painter.drawLine(previous, point)
            painter.drawEllipse(point, 3, 3)
            previous = point


class HistoryWorker(QThread):
    """Read bounded headers or one iterative saved tree without blocking the event loop."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, store: ScanHistory, root: str, parent: QWidget, *, entry: HistoryEntry | None = None) -> None:
        super().__init__(parent)
        self.store, self.root, self.entry = store, root, entry
        self.cancel = threading.Event()

    def run(self) -> None:
        """Suppress canceled/late replies and keep corrupt history visible as errors."""
        try:
            result = (load_history(self.entry, cancel=self.cancel) if self.entry is not None else
                      self.store.read(self.root, cancel=self.cancel))
        except HistoryCancelledError:
            return
        except (OSError, ValueError, UnicodeError, RecursionError) as error:
            if not self.cancel.is_set():
                self.failed.emit(str(error))
            return
        if not self.cancel.is_set():
            self.ready.emit(result)


class HistoryDialog(QDialog):
    """Review past totals and choose an earlier scan, without selecting an export file."""

    compare_requested = Signal(object)

    def __init__(self, store: ScanHistory, root: str, unit: str, parent: QWidget) -> None:
        super().__init__(parent)
        self._closed = False
        self.store, self.root = store, root
        self.setWindowTitle(tr("action_history"))
        self.resize(870, 640)
        self.model = HistoryModel(self)
        self.model.unit = unit
        self.chart = HistoryChart(self)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for column, width in enumerate((230, 170, 200, 210)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        self.view.doubleClicked.connect(lambda _index: self.compare_selected())
        self.view.selectionModel().selectionChanged.connect(self._selection)
        self.compare_button = QPushButton(tr("history_compare"))
        self.compare_button.clicked.connect(self.compare_selected)
        self.compare_button.setEnabled(False)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        self.status = QLabel(tr("history_reading"))
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        hint, location = QLabel(tr("history_hint")), QLabel(root)
        hint.setWordWrap(True)
        location.setTextFormat(Qt.TextFormat.PlainText)
        location.setWordWrap(True)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (location, hint, self.chart, self.view, self.status, self.compare_button,
                       self.stop_button, close):
            layout.addWidget(widget, 1 if widget is self.view else 0)
        self.worker = HistoryWorker(store, root, self)
        self._running = True
        self.worker.ready.connect(self._show)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _show(self, result: HistoryRead | SavedScan) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self._running = False
        self.stop_button.setEnabled(False)
        if isinstance(result, SavedScan):
            self.accept()
            self.compare_requested.emit(result)
            return
        self.model.set_rows(result.entries)
        self.chart.set_entries(result.entries, self.model.unit)
        self.status.setText(tr("history_summary", shown=format_count(len(result.entries)),
                               count=format_count(result.count), invalid=format_count(result.invalid)))
        self._selection()

    def _selection(self) -> None:
        self.compare_button.setEnabled(not self._running and self.view.currentIndex().isValid())

    def compare_selected(self) -> None:
        """Load only the selected snapshot on a worker; accept before delivering a stable SavedScan."""
        index = self.view.currentIndex()
        if self._running or not index.isValid():
            return
        entry = self.model.rows()[index.row()]
        wait_for(self.worker)
        self.worker.deleteLater()
        self.worker = HistoryWorker(self.store, self.root, self, entry=entry)
        self.worker.ready.connect(self._show)
        self.worker.failed.connect(self._failed)
        self._running = True
        self.compare_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status.setText(tr("history_reading"))
        self.worker.start()

    def _failed(self, reason: str) -> None:
        if not self._closed and not self.worker.cancel.is_set():
            self._running = False
            self.stop_button.setEnabled(False)
            self.status.setText(tr("history_failed", reason=reason))
            self._selection()

    def stop(self) -> None:
        """Cancel reading; partial replies never replace the chart or enable comparison."""
        self.worker.cancel.set()
        self.compare_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.status.setText(tr("scan_cancelled"))

    def shutdown(self) -> None:
        """Reject queued replies and join the owned worker before destroying this dialog."""
        self._closed = True
        self.worker.cancel.set()
        wait_for(self.worker)

    def done(self, result: int) -> None:
        """Qt: wait for worker cancellation on Close, Escape or successful selection."""
        self.shutdown()
        super().done(result)
