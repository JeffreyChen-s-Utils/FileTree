"""A one-line label that shortens its text in the middle to the width it gets (for paths)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    """Plain text shortened in the middle (``C:\\Users\\…\\Photos``) to fit; the whole text is the tooltip.

    It asks for no width of its own, so a long path can never widen the window.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def full_text(self) -> str:
        """The text before shortening."""
        return self._full

    def setText(self, text: str) -> None:  # noqa: N802 - Qt's name
        """Qt: show ``text``, shortened to the current width."""
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Qt: shorten again for the new width."""
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        elided = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, max(self.width(), 1))
        super().setText(elided)
