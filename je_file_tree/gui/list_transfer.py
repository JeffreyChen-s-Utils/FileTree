"""Yielding GUI-model capture for CSV and clipboard, without touching Qt models in workers."""

from __future__ import annotations

import csv
import io
import itertools
import queue
import threading
import time
from collections.abc import Iterator

from PySide6.QtCore import QModelIndex, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QApplication

from je_file_tree.core.export import spreadsheet_text
from je_file_tree.gui.i18n import tr

_CHUNK_ROWS = 128
_CHUNK_SECONDS = 0.004


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
                    return
                continue
            yield from batch


def _indexes(view: QAbstractItemView, selected: bool) -> Iterator[QModelIndex]:
    model = view.model()
    if selected:
        yield from sorted(view.selectionModel().selectedRows(0), key=_order_key)
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
        self.model = view.model()
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
                       self.model.rowsAboutToBeRemoved, self.model.rowsAboutToBeMoved):
            signal.connect(self.abort)
        if selected:
            view.selectionModel().selectionChanged.connect(self.abort)

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
            if self.stream is not None:
                self.stream.finish(tr('list_changed'))
            self.finished.emit()

    @Slot()
    def abort(self) -> None:
        """Discard mixed snapshots when the list changes during capture."""
        if self._active:
            self.failed.emit(tr('list_changed'))
            self.cancel()

    def _chunk(self) -> None:
        if not self._active:
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
            index = next(self._indexes, None)
            if index is None:
                self._complete = True
                break
            row = [_text(self.model.index(index.row(), column, index.parent()).data())
                   for column in range(len(self.header))]
            (self.rows if self.stream is None else self._pending).append(row)
            if time.monotonic() - started >= _CHUNK_SECONDS:
                break
        self._timer.start(0)


def install_copy(view: QAbstractItemView) -> None:
    """Give one list Ctrl+C scoped to the view; input fields keep their normal text copying."""
    shortcut = QShortcut(QKeySequence.StandardKey.Copy, view)
    shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
    captures: set[ListCapture] = set()

    def copy() -> None:
        for capture in list(captures):
            capture.cancel()
        capture = ListCapture(view, view, selected=True)
        captures.add(capture)
        capture.ready.connect(copy_table)
        capture.finished.connect(lambda: captures.discard(capture))
        capture.finished.connect(capture.deleteLater)
        capture.start()

    shortcut.activated.connect(copy)
    view.destroyed.connect(captures.clear)


def copy_table(header: tuple[str, ...], rows: list[list[str]]) -> None:
    """Copy selected rows as quoted TSV with headers, protecting spreadsheet formulas."""
    if not rows:
        return
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    for row in itertools.chain((header,), rows):
        writer.writerow([spreadsheet_text(cell) for cell in row])
    QApplication.clipboard().setText(stream.getvalue())
