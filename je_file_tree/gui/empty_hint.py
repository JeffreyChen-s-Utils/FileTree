"""A muted sentence in the middle of an empty list, so an empty table explains itself."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel

_MARGIN = 24


class EmptyHint(QObject):
    """Show ``text()`` over ``view``'s viewport while its model has no rows; an empty text shows nothing.

    Only the row count is read, on the GUI thread, when the model announces a change: the hint never
    walks the rows or the scanned tree. The label ignores the mouse, so clicks still reach the view.
    """

    def __init__(self, view: QAbstractItemView, text: Callable[[], str]) -> None:
        super().__init__(view)
        self._text = text
        # Kept: while the view is being destroyed its viewport still delivers events here, and asking
        # the half-deleted view for its viewport or model then raises.
        self._viewport = view.viewport()
        self.label = QLabel(self._viewport)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.setStyleSheet("color: palette(placeholder-text);")
        self.label.hide()
        self._viewport.installEventFilter(self)
        self._model = model = view.model()
        for signal in (model.modelReset, model.rowsInserted, model.rowsRemoved, model.layoutChanged):
            signal.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args: object) -> None:
        """Re-read the text and show it only while the list is empty."""
        text = self._text() if self._model.rowCount() == 0 else ""
        self.label.setText(text)
        self.label.setAccessibleName(text)
        self.label.setVisible(bool(text))
        if text:
            self._place()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Qt: keep the sentence centred when the viewport is resized."""
        if event.type() == QEvent.Type.Resize and watched is self._viewport:
            self._place()
        return False

    def _place(self) -> None:
        self.label.setGeometry(self._viewport.rect().adjusted(_MARGIN, _MARGIN, -_MARGIN, -_MARGIN))
