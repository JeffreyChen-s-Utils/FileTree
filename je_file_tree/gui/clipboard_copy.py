"""Encode copied rows within capture turns; publish only the current complete request.

Rows are written straight into UTF-8 bytes and published as ``text/plain;charset=utf-8``. Hosted
measurement (U-20261017-70) found that publishing a ``str`` spends the whole pause converting it to a
QString on the GUI thread (317 ms at 13.5 M and 1,328 ms at 56.7 M characters) while the native
clipboard call takes 3 ms; bytes cross into Qt as a copy and are decoded only if a reader asks.
"""

from __future__ import annotations

import atexit
import csv
import io

import shiboken6
from PySide6.QtCore import QEvent, QMimeData, QModelIndex, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QApplication, QWidget

from je_file_tree.core.export import spreadsheet_text
from je_file_tree.gui.list_transfer import ListCapture

UTF8_TEXT = 'text/plain;charset=utf-8'


class _ClipboardCapture(ListCapture):
    def __init__(self, view: QAbstractItemView) -> None:
        super().__init__(view, view, selected=True)
        self._bytes = io.BytesIO()
        self._output = io.TextIOWrapper(self._bytes, encoding='utf-8', newline='', write_through=True)
        self._writer = csv.writer(self._output, delimiter='\t', lineterminator='\n')
        self._writer.writerow([spreadsheet_text(cell) for cell in self.header])
        self.finished.connect(self._output.close)

    def _capture_row(self, index: QModelIndex) -> list[str] | None:
        row = super()._capture_row(index)
        if row is not None:
            cells = [spreadsheet_text(cell) for cell in row]
            if not self._active:
                return None
            self._writer.writerow(cells)
        return row

    def encoded_utf8(self) -> bytes:
        """Return the already encoded complete UTF-8 text; the caller owns publication checks."""
        self._output.flush()
        return self._bytes.getvalue()


class _CopyController(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._app = app
        self._current: _ClipboardCapture | None = None
        self._generation = 0
        self._publishing = 0
        self._published: QMimeData | None = None
        self._clipboard = QApplication.clipboard()
        self._clipboard.dataChanged.connect(self._clipboard_changed)
        app.aboutToQuit.connect(self.cancel)
        atexit.register(self._release_published)

    def copy(self, view: QAbstractItemView) -> None:
        """Supersede copies in any view; keep the original clipboard until complete publication."""
        self.cancel()
        generation = self._generation
        capture = _ClipboardCapture(view)
        if generation != self._generation:
            capture._output.close()
            capture.deleteLater()
            return
        self._current = capture
        capture.ready.connect(lambda _header, rows: self._publish(capture, rows))
        capture.finished.connect(lambda: self._finished(capture))
        capture.finished.connect(capture.deleteLater)
        self._app.installEventFilter(self)
        capture.start()

    def _publish(self, capture: _ClipboardCapture, rows: list[list[str]]) -> None:
        if (getattr(self, '_current', None) is not capture or capture._active
                or not capture._complete or not rows):
            return
        data = capture.encoded_utf8()
        if self._current is not capture:
            return
        mime = QMimeData()
        mime.setData(UTF8_TEXT, data)
        self._publishing += 1
        try:
            self._clipboard.setMimeData(mime)  # the clipboard takes ownership
            self._published = mime
        finally:
            self._publishing -= 1

    def _release_published(self) -> None:
        """Before interpreter shutdown, hand a copy that is still on the clipboard back to Qt as text.

        Qt destroying this Python-created QMimeData during interpreter finalization calls back into a
        dead interpreter (access violation at exit, U-20261017-70). As text, the copy still stays on
        the system clipboard after FileTree exits; a copy already replaced elsewhere is left alone.
        """
        mime, self._published = self._published, None
        current = getattr(self._clipboard, 'mimeData', None)
        if mime is None or current is None or not shiboken6.isValid(mime):
            return
        if current() is mime:
            self._clipboard.setText(mime.text())

    def _clipboard_changed(self) -> None:
        if not getattr(self, '_publishing', 0):
            self.cancel()

    def _finished(self, capture: _ClipboardCapture) -> None:
        if getattr(self, '_current', None) is capture:
            self._current = None
            self._app.removeEventFilter(self)

    def cancel(self) -> None:
        """Cancel only the pending request; a native clipboard call already in progress cannot be interrupted."""
        self._generation = getattr(self, '_generation', 0) + 1
        if capture := getattr(self, '_current', None):
            self._current = None
            self._app.removeEventFilter(self)
            capture.cancel()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Stop pending copies when their view/ancestor closes or their top-level window explicitly hides."""
        capture = getattr(self, '_current', None)
        if capture is not None and isinstance(watched, QWidget):
            closing = event.type() == QEvent.Type.Close and (
                watched is capture.view or watched.isAncestorOf(capture.view))
            hiding = (event.type() == QEvent.Type.Hide and not event.spontaneous()
                      and watched is capture.view.window())
            if closing or hiding:
                self.cancel()
        return False


def _controller() -> _CopyController:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError('A GUI application is required for list copying')
    controller = getattr(app, '_filetree_clipboard_copy', None)
    if controller is None:
        controller = _CopyController(app)
        app._filetree_clipboard_copy = controller
    return controller


def install_copy(view: QAbstractItemView) -> None:
    """Keep the copy shortcut on this view, with one latest pending request per application."""
    shortcut = QShortcut(QKeySequence.StandardKey.Copy, view)
    shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
    shortcut.activated.connect(lambda: _controller().copy(view))
