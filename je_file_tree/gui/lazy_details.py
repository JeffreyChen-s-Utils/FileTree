"""Message-box details that are built only when someone opens or copies them.

``QMessageBox.setDetailedText`` lays out the whole text in a ``QTextEdit`` at once. Natively on
Windows, 100,000 two-line entries took 0.74 s in Qt plus 0.14 s to join, before the question even
appeared; 10,000 took about 60 ms (U-20261018-80). The box here starts with a placeholder, so Qt
still adds its *Show Details…* button, and the real text is filled in the first time the details
are shown or the box is copied with the copy shortcut (Windows copies details even while hidden).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QMessageBox, QTextEdit

PLACEHOLDER = "…"  # never shown: the details are filled before they become visible


class _DetailsFiller(QObject):
    """Fills a message box's details text once, on first show or first copy."""

    def __init__(self, box: QMessageBox, view: QTextEdit, build: Callable[[], str]) -> None:
        super().__init__(box)
        self._box, self._view, self._build = box, view, build
        box.installEventFilter(self)
        view.installEventFilter(self)

    def fill(self) -> None:
        """Build the text now if it is still pending; later calls do nothing."""
        build, self._build = self._build, None
        if build is None:
            return
        self._box.removeEventFilter(self)
        self._view.removeEventFilter(self)
        # Filling the editor directly skips setDetailedText's layout rebuild; detailedText() reads it back.
        self._view.setPlainText(build())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        """Fill before the details appear or before the box's copy shortcut reads them; never consume events."""
        if self._build is None:
            return False
        shown = watched is self._view and event.type() == QEvent.Type.Show
        copied = (watched is self._box and event.type() == QEvent.Type.KeyPress
                  and event.matches(QKeySequence.StandardKey.Copy))
        if shown or copied:
            self.fill()
        return False


def set_lazy_details(box: QMessageBox, build: Callable[[], str]) -> None:
    """Give ``box`` details produced by ``build`` (which must return non-empty text) only when needed.

    ``build`` runs at most once, on the GUI thread, and must only read data that stays unchanged
    while the box is open. The box never becomes a native platform dialog, which would read the
    placeholder when shown (macOS already refuses native dialogs with details).
    """
    box.setOption(QMessageBox.Option.DontUseNativeDialog)
    box.setDetailedText(PLACEHOLDER)
    _DetailsFiller(box, box.findChild(QTextEdit), build)


def full_details(box: QMessageBox) -> str:
    """The box's complete details, building them first if they are still pending (as opening them would)."""
    filler = box.findChild(_DetailsFiller)
    if filler is not None:
        filler.fill()
    return box.detailedText()
