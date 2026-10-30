"""Local scan-history settings, cancellable reads and a size-over-time chart."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from pathlib import Path
import threading

from PySide6.QtCore import QPointF, QSettings, QStandardPaths, QThread, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTableView, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from je_file_tree.core.compare import SavedScan
from je_file_tree.core.formatting import format_change, format_count, format_size
from je_file_tree.core.history import HistoryCancelledError, HistoryEntry, HistoryRead, ScanHistory, load_history
from je_file_tree.core.trends import HistoryTrend, TrendPoint, TrendQuery, query_trend
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.loaded_folder import LoadedFolderDialog
from je_file_tree.gui.list_transfer import install_copy
from je_file_tree.gui.optional_date import OptionalDateEdit
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import WorkerDialog, after_threads, retire_worker
from je_file_tree.gui.tables import Column, _TableModel

_MIB = 1024 * 1024
_DEFAULT_MIB = 1024
_MAX_MIB = 16384
_POINT_CHANGE_COLUMN = 2
_CHILD_CHANGE_COLUMN = 3


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

    point_selected = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.entries: list[HistoryEntry] = []
        self.points: tuple[TrendPoint, ...] = ()
        self.unit = "auto"
        self.selected_point: int | None = None
        self.setMinimumHeight(130)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(tr("history_chart"))

    def set_entries(self, entries: list[HistoryEntry], unit: str) -> None:
        """Use bounded scalar entries already read by the worker; expose an accessible range summary."""
        self.entries, self.unit = entries, unit
        self.points = ()
        self.selected_point = None
        if entries:
            self.setAccessibleDescription(tr("history_chart_range", first=_date(entries[0]), last=_date(entries[-1]),
                                             before=format_size(entries[0].size, unit),
                                             after=format_size(entries[-1].size, unit)))
        else:
            self.setAccessibleDescription(tr("history_empty"))
        self.update()

    def set_trend(self, trend: HistoryTrend, unit: str) -> None:
        """Draw known folder sizes and expose unknown observations in the accessible summary."""
        self.entries, self.points, self.unit = [], trend.points, unit
        self.selected_point = None
        known = sum(point.size is not None for point in trend.points)
        self.setAccessibleDescription(tr("trend_chart_known", known=known, total=len(trend.points))
                                      if known else tr("trend_chart_unknown"))
        self.update()

    def set_selected_point(self, index: int | None) -> None:
        """Set the shared observation index without emitting a selection signal."""
        self.selected_point = index if index is not None and 0 <= index < len(self.points) else None
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Visit every observation, including overlapping timestamps and unknown sizes."""
        keys = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                Qt.Key.Key_Home, Qt.Key.Key_End)
        if not self.points or event.key() not in keys:
            super().keyPressEvent(event)
            return
        current = self.selected_point
        if event.key() == Qt.Key.Key_Home:
            index = 0
        elif event.key() == Qt.Key.Key_End:
            index = len(self.points) - 1
        else:
            step = -1 if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up) else 1
            index = 0 if current is None else max(0, min(len(self.points) - 1, current + step))
        self.set_selected_point(index)
        self.point_selected.emit(index)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Select the nearest plotted observation, cycling observations that overlap."""
        if self.points and event.button() == Qt.MouseButton.LeftButton:
            positions = self._positions(self.points)
            distances = [(position - event.position()).manhattanLength() for position in positions]
            nearest = min(distances)
            matches = [index for index, distance in enumerate(distances) if abs(distance - nearest) < 1]
            index = matches[(matches.index(self.selected_point) + 1) % len(matches)] \
                if self.selected_point in matches else matches[0]
            self.set_selected_point(index)
            self.point_selected.emit(index)
            self.setFocus()
        super().mousePressEvent(event)

    def _positions(self, values: Sequence[TrendPoint] | Sequence[HistoryEntry]) -> list[QPointF]:
        area = self.rect().adjusted(100, 15, -25, -55)
        peak = max((item.size or 0 for item in values), default=1) or 1
        entries = [item.entry if isinstance(item, TrendPoint) else item for item in values]
        times = [datetime.fromisoformat(entry.saved).timestamp() for entry in entries]
        start, end = times[0], times[-1]
        return [QPointF(area.left() + ((stamp - start) / (end - start) if end > start else .5) * area.width(),
                        area.bottom() + 20 if item.size is None else area.bottom() - item.size / peak * area.height())
                for item, stamp in zip(values, times, strict=True)]

    def paintEvent(self, event: QPaintEvent) -> None:
        """Qt: draw total logical bytes; metadata rows retain all exact displayed values."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().base())
        area = self.rect().adjusted(100, 15, -25, -55)
        painter.setPen(self.palette().text().color())
        if not self.entries and not self.points:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("history_empty"))
            return
        values = self.points or self.entries
        peak = max((item.size or 0 for item in values), default=1) or 1
        painter.drawLine(area.bottomLeft(), area.bottomRight())
        painter.drawLine(area.bottomLeft(), area.topLeft())
        painter.drawText(5, area.top() + 10, format_size(peak, self.unit))
        painter.drawText(5, area.bottom(), "0")
        if any(item.size is None for item in values):
            painter.drawText(5, area.bottom() + 23, tr('trend_unknown'))
        painter.drawText(area.left(), self.height() - 10, _date(values[0].entry if self.points else values[0]))
        painter.drawText(area.right() - 145, self.height() - 10, _date(values[-1].entry if self.points else values[-1]))
        painter.setPen(QPen(self.palette().highlight().color(), 2))
        previous = None
        for index, (item, point) in enumerate(zip(values, self._positions(values), strict=True)):
            if item.size is None:
                previous = None
                painter.drawText(point + QPointF(-4, 4), '?')
            else:
                if self.points and item.change is None:
                    previous = None
                if previous is not None:
                    painter.drawLine(previous, point)
                painter.drawEllipse(point, 3, 3)
                previous = point
            if self.points and index == self.selected_point:
                painter.drawEllipse(point, 7, 7)
        if self.hasFocus():
            painter.setPen(QPen(self.palette().text().color(), 1, Qt.PenStyle.DotLine))
            painter.drawRect(self.rect().adjusted(2, 2, -3, -3))


class HistoryWorker(QThread):
    """Read bounded headers or one iterative saved tree without blocking the event loop."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, store: ScanHistory, root: str, parent: QWidget, *, entry: HistoryEntry | None = None,
                 query: TrendQuery | None = None) -> None:
        super().__init__(parent)
        self.store, self.root, self.entry = store, root, entry
        self.query = query
        self.cancel = threading.Event()

    def run(self) -> None:
        """Suppress canceled/late replies and keep corrupt history visible as errors."""
        try:
            result = (load_history(self.entry, cancel=self.cancel) if self.entry is not None else
                      query_trend(self.store, self.query, cancel=self.cancel) if self.query is not None else
                      self.store.read(self.root, cancel=self.cancel))
        except HistoryCancelledError:
            return
        except (OSError, ValueError, UnicodeError, RecursionError) as error:
            if not self.cancel.is_set():
                self.failed.emit(str(error))
            return
        if not self.cancel.is_set():
            self.ready.emit(result)


class HistoryDialog(WorkerDialog):
    """Review past totals and choose an earlier scan, without selecting an export file."""

    compare_requested = Signal(object)

    def __init__(self, store: ScanHistory, root: str, unit: str, parent: QWidget,
                 *, folder: str = "", loaded_root: Node | None = None) -> None:
        super().__init__(parent)
        self._closed = False
        self.store, self.root = store, root
        self.loaded_root = loaded_root
        self.folder_dialog: LoadedFolderDialog | None = None
        self.trend: HistoryTrend | None = None
        self.setWindowTitle(tr("action_history"))
        self.resize(900, 760)
        self.model = HistoryModel(self)
        self.model.unit = unit
        self.chart = HistoryChart(self)
        self._make_trend_controls(folder)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setTabKeyNavigation(False)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for column, width in enumerate((230, 170, 200, 210)):
            self.view.setColumnWidth(column, width)
        install_copy(self.view)
        self.view.doubleClicked.connect(lambda _index: self.compare_selected())
        self.view.selectionModel().selectionChanged.connect(self._selection)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.trend_view, tr("trend_tab_sizes"))
        self.tabs.addTab(self.children_view, tr("trend_tab_sources"))
        self.tabs.addTab(self.view, tr("trend_tab_compare"))
        self.tabs.currentChanged.connect(lambda _index: self._selection())
        self.compare_button = QPushButton(tr("history_compare"))
        self.compare_button.clicked.connect(self.compare_selected)
        self.compare_button.setEnabled(False)
        self.stop_button = QPushButton(tr("action_stop"))
        self.stop_button.clicked.connect(self.stop)
        self.status = QLabel(tr("history_reading"))
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self._build_layout()
        self.worker = HistoryWorker(store, root, self, query=TrendQuery(root, folder))
        self._running = True
        self._start_read()

    def _build_layout(self) -> None:
        hint = QLabel(tr("history_hint"))
        hint.setWordWrap(True)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        filters = QFormLayout()
        folder_row = QHBoxLayout()
        for widget in (self.folder_input, self.choose_folder_button, self.root_button):
            folder_row.addWidget(widget)
        filters.addRow(tr("trend_folder"), folder_row)
        filters.addRow(tr('trend_full_path'), self.full_path)
        filters.addRow(tr('trend_period'), self.period)
        dates = QHBoxLayout()
        for key, widget in (('trend_start', self.start_input), ('trend_end', self.end_input)):
            label = QLabel(tr(key))
            label.setBuddy(widget)
            dates.addWidget(label)
            dates.addWidget(widget, 1)
        dates.addWidget(self.apply_button)
        filters.addRow(dates)
        layout.addLayout(filters)
        for widget in (hint, self.chart, self.point_details, self.net_label, self.tabs, self.status):
            layout.addWidget(widget, 1 if widget is self.tabs else 0)
        actions = QHBoxLayout()
        actions.addWidget(self.compare_button)
        actions.addWidget(self.stop_button)
        actions.addStretch()
        actions.addWidget(close)
        layout.addLayout(actions)

    def _make_trend_controls(self, folder: str) -> None:
        """Build editable query inputs and bounded result tables."""
        self.folder_input = QLineEdit(folder)
        self.folder_input.setPlaceholderText(tr("trend_folder_hint"))
        self.folder_input.setAccessibleName(tr('trend_folder'))
        self.choose_folder_button = QPushButton(tr('trend_choose_folder'))
        self.choose_folder_button.setEnabled(self.loaded_root is not None)
        self.choose_folder_button.clicked.connect(self.choose_folder)
        self.root_button = QPushButton(tr('trend_root'))
        self.root_button.clicked.connect(self.return_to_root)
        self.full_path = QLineEdit()
        self.full_path.setReadOnly(True)
        self.full_path.setAccessibleName(tr('trend_full_path'))
        self._update_path()
        self.folder_input.textChanged.connect(self._update_path)
        self.period = QComboBox()
        for key in ('all', '30', '90', 'custom'):
            self.period.addItem(tr('trend_period_' + key), key)
        self.period.currentIndexChanged.connect(self._period_changed)
        self.start_input, self.end_input = OptionalDateEdit(), OptionalDateEdit()
        for field, key in ((self.start_input, 'trend_start'), (self.end_input, 'trend_end')):
            field.edit.setAccessibleName(tr(key))
            field.text_changed.connect(self._custom_period)
        self.apply_button = QPushButton(tr("trend_apply"))
        self.apply_button.clicked.connect(self.apply_trend)
        self.trend_view = QTableWidget(0, 4)
        self.trend_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.trend_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.trend_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.trend_view.currentCellChanged.connect(lambda row, *_args: self.select_point(row))
        self.trend_view.setHorizontalHeaderLabels([tr("history_time"), tr("history_logical"),
                                                   tr("trend_change"), tr("history_coverage")])
        for column, width in enumerate((180, 130, 150, 220)):
            self.trend_view.setColumnWidth(column, width)
        self.children_view = QTableWidget(0, 4)
        self.children_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.children_view.setHorizontalHeaderLabels([tr("trend_child"), tr("trend_before"),
                                                      tr("trend_after"), tr("trend_change")])
        for column, width in enumerate((220, 130, 130, 150)):
            self.children_view.setColumnWidth(column, width)
        self.net_label = QLabel(tr("trend_net_unknown"))
        self.net_label.setWordWrap(True)
        self.point_details = QPlainTextEdit()
        self.point_details.setReadOnly(True)
        self.point_details.setTabChangesFocus(True)
        self.point_details.setMaximumHeight(76)
        self.point_details.setAccessibleName(tr('trend_point_details'))
        self.point_details.setPlainText(tr('trend_select_point'))
        self.chart.point_selected.connect(self.select_point)
        for table in (self.trend_view, self.children_view):
            table.setTabKeyNavigation(False)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            install_copy(table)
        for button in (self.choose_folder_button, self.root_button, self.apply_button):
            button.setAutoDefault(False)

    def _update_path(self) -> None:
        folder = self.folder_input.text()
        self.full_path.setText(str(Path(self.root) / folder) if folder else self.root)
        self.full_path.setCursorPosition(0)

    def _custom_period(self) -> None:
        self.period.blockSignals(True)
        self.period.setCurrentIndex(self.period.findData('custom'))
        self.period.blockSignals(False)

    def _period_changed(self) -> None:
        key = self.period.currentData()
        if key == 'custom':
            return
        today = date.today()
        for field in (self.start_input, self.end_input):
            field.blockSignals(True)
        self.start_input.setText('' if key == 'all' else (today - timedelta(days=int(key) - 1)).isoformat())
        self.end_input.setText('' if key == 'all' else today.isoformat())
        for field in (self.start_input, self.end_input):
            field.blockSignals(False)

    def choose_folder(self) -> None:
        """Browse only the current loaded tree with an independently owned worker."""
        if self.loaded_root is None or self.folder_dialog is not None:
            return
        dialog = LoadedFolderDialog(self.loaded_root, self)
        self.folder_dialog = dialog
        if self.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen):
            dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.finished.connect(lambda result: self._folder_chosen(dialog, result))
        dialog.open()

    def _folder_chosen(self, dialog: LoadedFolderDialog, result: int) -> None:
        if result == QDialog.DialogCode.Accepted and dialog.selected is not None and not self._closed:
            names = []
            node = dialog.selected
            while node is not self.loaded_root and node is not None:
                names.append(node.name)
                node = node.parent
            if node is self.loaded_root:
                self.folder_input.setText('/'.join(reversed(names)))
                self.apply_trend()
        self.folder_dialog = None
        dialog.deleteLater()
        self.choose_folder_button.setFocus()

    def return_to_root(self) -> None:
        """Query the original scan root while retaining the current date period."""
        self.folder_input.clear()
        self.apply_trend()

    def _start_read(self) -> None:
        worker = self.worker
        worker.ready.connect(lambda result: after_threads(
            (worker,), lambda: worker is self.worker and self._show(result), self))
        worker.failed.connect(lambda reason: after_threads(
            (worker,), lambda: worker is self.worker and self._failed(reason), self))
        previous = [thread for thread in self.findChildren(HistoryWorker) if thread is not worker]
        after_threads((*previous, *self.pending_source_workers()),
                      lambda: worker.start() if not self._closed and self.worker is worker
                      and not worker.cancel.is_set() else None, self)

    def _show(self, result: HistoryRead | SavedScan | HistoryTrend) -> None:
        if self._closed or self.worker.cancel.is_set():
            return
        self._running = False
        self.stop_button.setEnabled(False)
        if isinstance(result, SavedScan):
            self.accept()
            self.compare_requested.emit(result)
            return
        if isinstance(result, HistoryTrend):
            self._show_trend(result)
            return
        self.model.set_rows(result.entries)
        self.tabs.setCurrentWidget(self.view)
        self.chart.set_entries(result.entries, self.model.unit)
        self.status.setText(tr("history_summary", shown=format_count(len(result.entries)),
                               count=format_count(result.count), invalid=format_count(result.invalid)))
        self._selection()

    def _show_trend(self, result: HistoryTrend) -> None:
        self.trend = result
        self.model.set_rows([point.entry for point in result.points])
        self.tabs.setCurrentWidget(self.trend_view)
        self.trend_view.blockSignals(True)
        self.trend_view.clearSelection()
        self.trend_view.setCurrentCell(-1, -1)
        self.trend_view.setRowCount(len(result.points))
        for row, point in enumerate(result.points):
            labels = (_date(point.entry), self._size(point.size), self._signed(point.change),
                      self._point_reasons(point))
            for column, label in enumerate(labels):
                value = (None, point.size, point.change, None)[column]
                self.trend_view.setItem(row, column,
                                       self._item(label, value, change=column == _POINT_CHANGE_COLUMN))
        self.trend_view.blockSignals(False)
        self.children_view.setRowCount(len(result.children))
        for row, child in enumerate(result.children):
            labels = (child.folder or tr("trend_direct_files"), self._size(child.before),
                      self._size(child.after), self._signed(child.change))
            for column, label in enumerate(labels):
                value = (None, child.before, child.after, child.change)[column]
                item = self._item(label, value, change=column == _CHILD_CHANGE_COLUMN)
                if child.reason is not None:
                    reason = tr("trend_reason_" + child.reason.value)
                    item.setToolTip(item.toolTip() + '\n' + reason)
                    item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, reason)
                self.children_view.setItem(row, column, item)
        self.chart.set_trend(result, self.model.unit)
        self.net_label.setText(tr("trend_net", change=self._signed(result.net)) if result.net is not None
                               else tr("trend_net_reason", reason=tr("trend_reason_" + result.net_reason.value))
                               if result.net_reason else tr("trend_net_unknown"))
        exact = format_change(result.net, 'B') if result.net is not None else self.net_label.text()
        self.net_label.setToolTip(exact)
        self.net_label.setAccessibleDescription(exact)
        if not result.points:
            self.net_label.setText(tr('history_empty'))
        self.select_point(0 if result.points else -1)
        self.status.setText(tr("trend_summary", shown=len(result.points), count=result.count,
                               invalid=result.invalid, children=len(result.children),
                               child_count=result.children_count,
                               cap=tr("trend_capped") if result.truncated else ""))
        self._selection()

    def _size(self, value: int | None) -> str:
        return format_size(value, self.model.unit) if value is not None else tr("trend_unknown")

    def _signed(self, value: int | None) -> str:
        return format_change(value, self.model.unit) if value is not None else tr("trend_unknown")

    @staticmethod
    def _item(label: str, value: int | None, *, change: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(label)
        exact = (format_change(value, 'B') if change else format_size(value, 'B')) if value is not None else label
        item.setToolTip(exact)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, f'{label}; {exact}' if exact != label else label)
        return item

    @staticmethod
    def _point_reasons(point: TrendPoint) -> str:
        reasons = []
        if point.size is None:
            reason = tr('trend_reason_' + point.reason.value) if point.reason else tr('trend_unknown')
            reasons.append(tr('trend_size_reason', reason=reason))
        if point.change is None:
            reason = tr('trend_reason_' + point.change_reason.value) if point.change_reason else tr('trend_first_point')
            reasons.append(tr('trend_change_reason', reason=reason))
        return '\n'.join(reasons) or tr('history_complete')

    def select_point(self, index: int) -> None:
        """Synchronize chart, row and exact details using the immutable result's point index."""
        if self.trend is None or not 0 <= index < len(self.trend.points):
            self.chart.set_selected_point(None)
            self.point_details.setPlainText(tr('trend_select_point'))
            return
        point = self.trend.points[index]
        self.chart.set_selected_point(index)
        self.trend_view.blockSignals(True)
        self.trend_view.setCurrentCell(index, 0)
        self.trend_view.selectRow(index)
        self.trend_view.blockSignals(False)
        exact_size = format_size(point.size, 'B') if point.size is not None else tr('trend_unknown')
        exact_change = format_change(point.change, 'B') if point.change is not None else tr('trend_unknown')
        details = tr('trend_point_value', date=_date(point.entry), size=self._size(point.size),
                     exact_size=exact_size, change=self._signed(point.change), exact_change=exact_change)
        details += '\n' + self._point_reasons(point)
        self.point_details.setPlainText(details)
        self.chart.setAccessibleDescription(details)

    def apply_trend(self) -> None:
        """Parse local inclusive dates, clear stale results, then query on an owned worker."""
        self._period_changed()
        self.trend = None
        self.trend_view.setRowCount(0)
        self.children_view.setRowCount(0)
        self.model.set_rows([])
        self.chart.set_entries([], self.model.unit)
        self.net_label.setText(tr("trend_net_unknown"))
        self.net_label.setToolTip('')
        self.net_label.setAccessibleDescription('')
        self.select_point(-1)
        try:
            invalid_field = self.start_input
            start = self._day(self.start_input.text())
            start_bound = self._midnight(start) if start is not None else None
            invalid_field = self.end_input
            last = self._day(self.end_input.text())
            end = self._midnight(last + timedelta(days=1)) if last is not None else None
            if start is not None and last is not None and start > last:
                invalid_field = self.end_input
                raise ValueError(tr('trend_date_order'))
            invalid_field = self.folder_input
            query = TrendQuery(self.root, self.folder_input.text(), start_bound, end)
        except (ValueError, OverflowError, OSError) as error:
            self.worker.cancel.set()
            self._running = False
            self.stop_button.setEnabled(False)
            self.status.setText(tr("trend_invalid", reason=str(error)))
            invalid_field.setFocus()
            self._selection()
            return
        self.worker.cancel.set()
        retire_worker(self.worker, self)
        self.worker = HistoryWorker(self.store, self.root, self, query=query)
        self._running = True
        self.stop_button.setEnabled(True)
        self.status.setText(tr("history_reading"))
        self._start_read()

    @staticmethod
    def _day(text: str) -> date | None:
        return date.fromisoformat(text.strip()) if text.strip() else None

    @staticmethod
    def _midnight(day: date) -> datetime:
        return datetime.combine(day, time.min).astimezone()

    def _selection(self) -> None:
        self.compare_button.setEnabled(not self._running and self.tabs.currentWidget() is self.view
                                       and self.view.currentIndex().isValid())

    def compare_selected(self) -> None:
        """Load only the selected snapshot on a worker; accept before delivering a stable SavedScan."""
        index = self.view.currentIndex()
        if self._running or not index.isValid():
            return
        entry = self.model.rows()[index.row()]
        self.worker.cancel.set()
        retire_worker(self.worker, self)
        self.worker = HistoryWorker(self.store, self.root, self, entry=entry)
        self._running = True
        self.compare_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status.setText(tr("history_reading"))
        self._start_read()

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

    def shutdown(self, *, wait: bool = True) -> None:
        """Reject queued replies and join the owned worker before destroying this dialog."""
        self._closed = True
        if self.folder_dialog is not None:
            self.folder_dialog.shutdown(wait=wait)
        for worker in self.findChildren(HistoryWorker):
            worker.cancel.set()
            if wait:
                wait_for(worker)

    def done(self, result: int) -> None:
        """Qt: wait for worker cancellation on Close, Escape or successful selection."""
        if self.defer_done(result):
            return
        self.shutdown()
        super().done(result)
