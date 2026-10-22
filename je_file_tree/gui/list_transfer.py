"""Yielding GUI-model capture for CSV and clipboard, without touching Qt models in workers."""

from __future__ import annotations

import csv
import heapq
import inspect
import io
import itertools
import queue
import threading
import time
from collections.abc import Generator, Iterator

from PySide6.QtCore import QAbstractItemModel, QItemSelectionModel, QModelIndex, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QAbstractItemView, QApplication, QTreeView

from je_file_tree.core.export import spreadsheet_text
from je_file_tree.gui.i18n import tr

_CHUNK_ROWS = 128
_CHUNK_SECONDS = 0.004
_END = object()
_SELECTABLE = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


def _text(value: object) -> str:
    return '' if value is None else str(value)


class ListStream:
    """Bounded text batches between GUI capture and a writer; cancellation aborts the atomic write."""

    def __init__(self) -> None:
        self.queue: queue.Queue[list[list[str]]] = queue.Queue(maxsize=8)
        self.closed = threading.Event()
        self.error = ''

    def offer(self, rows: list[list[str]]) -> bool:
        """Enqueue without blocking the GUI; callers retry after the writer catches up."""
        try:
            self.queue.put_nowait(rows)
        except queue.Full:
            return False
        return True

    def finish(self, error: str = '') -> None:
        """Stop the stream, failing the export if the capture was invalidated/cancelled."""
        self.error = error
        self.closed.set()

    def rows(self) -> Iterator[list[str]]:
        """Yield on a writer thread, keeping at most eight GUI batches queued."""
        while True:
            if self.closed.is_set() and self.error:
                raise ValueError(self.error)
            try:
                batch = self.queue.get(timeout=0.05)
            except queue.Empty:
                if self.closed.is_set():
                    if self.error:
                        raise ValueError(self.error) from None
                    return
                continue
            yield from batch


def _indexes(view: QAbstractItemView, selected: bool) -> Iterator[QModelIndex | None]:
    model = view.model()
    if selected:
        selection = view.selectionModel()
        methods = ('selectedRows', 'isRowSelected', 'selection')
        if (type(selection) is QItemSelectionModel and not any(name in selection.__dict__ for name in methods)
                and all(inspect.isbuiltin(getattr(selection, name)) for name in methods)):
            yield from _selected_indexes(selection)
        else:
            yield from sorted(selection.selectedRows(0), key=_order_key)
        return
    stack = [(QModelIndex(), 0)]
    while stack:
        parent, row = stack.pop()
        if row >= model.rowCount(parent):
            continue
        index = model.index(row, 0, parent)
        stack.append((parent, row + 1))
        stack.append((index, 0))
        yield index


def _parent_path(index: QModelIndex) -> Generator[None, None, tuple[int, ...]]:
    rows = []
    while index.isValid():
        rows.append(index.row())
        index = index.parent()
        yield None
    return tuple(reversed(rows))


def _selected_indexes(selection: QItemSelectionModel) -> Iterator[QModelIndex | None]:
    # Native 100k selected rows: eager selectedRows/sort stalled the first turn for 3.18 s (U-20261017-40).
    heap = []
    for serial, part in enumerate(selection.selection()):
        if part.isValid():
            parent = part.parent()
            path = yield from _parent_path(parent)
            whole = part.left() == 0 and part.right() == selection.model().columnCount(parent)-1
            heapq.heappush(heap, (path + (part.top(),), serial, part.bottom(), parent, whole))
        yield None
    previous = None
    parents = set()
    while heap:
        path, serial, bottom, parent, whole = heapq.heappop(heap)
        row = path[-1]
        if row < bottom:
            heapq.heappush(heap, (path[:-1] + (row + 1,), serial, bottom, parent, whole))
        if path != previous:
            previous = path
            parents.clear()
        if parent in parents:
            yield None
            continue
        parents.add(parent)
        selected = (_selectable_row(selection.model(), row, parent) if whole else
                    selection.isRowSelected(row, parent))
        yield selection.model().index(row, 0, parent) if selected else None


def _selectable_row(model: QAbstractItemModel, row: int, parent: QModelIndex) -> bool:
    # A full-width selected range already covers every column; retain Qt's per-cell flag checks.
    selectable = False
    for column in range(model.columnCount(parent)):
        selectable |= model.index(row, column, parent).flags() & _SELECTABLE == _SELECTABLE
    return selectable


def _order_key(index: QModelIndex) -> tuple[int, ...]:
    rows = []
    while index.isValid():
        rows.append(index.row())
        index = index.parent()
    return tuple(reversed(rows))


class ListCapture(QObject):
    """Capture the shown model order in short GUI turns, aborting on any model/selection change."""

    ready = Signal(object, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, view: QAbstractItemView, parent: QObject, *, selected: bool = False,
                 stream: ListStream | None = None) -> None:
        super().__init__(parent)
        self.view = view
        self.model = view.model()
        self.selection_model = view.selectionModel() if selected else None
        self.header = tuple(_text(self.model.headerData(column, Qt.Orientation.Horizontal))
                            for column in range(self.model.columnCount()))
        self.rows: list[list[str]] = []
        self._indexes = _indexes(view, selected)
        self._active = False
        self.stream = stream
        self._pending: list[list[str]] = []
        self._complete = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._chunk)
        for signal in (self.model.modelAboutToBeReset, self.model.layoutAboutToBeChanged, self.model.dataChanged,
                       self.model.headerDataChanged, self.model.rowsAboutToBeInserted,
                       self.model.rowsAboutToBeRemoved, self.model.rowsAboutToBeMoved,
                       self.model.columnsAboutToBeInserted, self.model.columnsAboutToBeRemoved,
                       self.model.columnsAboutToBeMoved):
            signal.connect(self.abort)
        # A view whose header has its own title model (grouped lists) announces new titles there.
        header = view.header() if isinstance(view, QTreeView) else getattr(view, 'horizontalHeader', lambda: None)()
        if header is not None and header.model() is not None and header.model() is not self.model:
            header.model().headerDataChanged.connect(self.abort)
        view.destroyed.connect(self.abort)
        if selected:
            self.selection_model.selectionChanged.connect(self.abort)
            self.selection_model.destroyed.connect(self.abort)

    def start(self) -> None:
        """Begin asynchronous capture after callers have connected completion signals."""
        self._active = True
        self._timer.start(0)

    def cancel(self) -> None:
        """Cancel without an error notification, including while the window closes."""
        if self._active:
            self._active = False
            self._timer.stop()
            self.rows.clear()
            self._pending.clear()
            self._indexes = iter(())
            if self.stream is not None:
                self.stream.finish(tr('list_changed'))
            self.finished.emit()

    @Slot()
    def abort(self) -> None:
        """Discard mixed snapshots when the list changes during capture."""
        if getattr(self, '_active', False):
            self.failed.emit(tr('list_changed'))
            self.cancel()

    def _chunk(self) -> None:
        if not self._active:
            return
        if (self.view.model() is not self.model or
                self.selection_model is not None and self.view.selectionModel() is not self.selection_model):
            self.abort()
            return
        if self._pending and self.stream is not None:
            if not self.stream.offer(self._pending):
                self._timer.start(5)
                return
            self._pending = []
        if self._complete:
            self._active = False
            if self.stream is not None:
                self.stream.finish()
            self.ready.emit(self.header, self.rows)
            self.finished.emit()
            return
        started = time.monotonic()
        for _ in range(_CHUNK_ROWS):
            index = next(self._indexes, _END)
            if not self._active:
                return
            if index is _END:
                self._complete = True
                break
            if index is not None:
                row = self._capture_row(index)
                if row is None:
                    return
                (self.rows if self.stream is None else self._pending).append(row)
            if time.monotonic() - started >= _CHUNK_SECONDS:
                break
        self._timer.start(0)

    def _capture_row(self, index: QModelIndex) -> list[str] | None:
        row = []
        for column in range(len(self.header)):
            row.append(_text(self.model.index(index.row(), column, index.parent()).data()))
            if not self._active:
                return None
        return row


def install_copy(view: QAbstractItemView) -> None:
    """Give one list Ctrl+C scoped to the view; input fields keep their normal text copying."""
    from je_file_tree.gui.clipboard_copy import install_copy as install  # noqa: PLC0415 - capture is defined first
    install(view)


def copy_table(header: tuple[str, ...], rows: list[list[str]]) -> None:
    """Copy selected rows as quoted TSV with headers, protecting spreadsheet formulas."""
    if not rows:
        return
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    for row in itertools.chain((header,), rows):
        writer.writerow([spreadsheet_text(cell) for cell in row])
    QApplication.clipboard().setText(stream.getvalue())
