"""The page shown while a scan runs: live counts, the folder being read, and a Stop button."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from file_tree.core.formatting import format_count, format_size
from file_tree.core.scanner import ScanProgress
from file_tree.gui.i18n import format_duration, tr


class ScanPage(QWidget):
    """Progress of the running scan."""

    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = ""
        self._started = time.monotonic()
        self._last: ScanProgress | None = None
        self._title = QLabel()
        self._counts = QLabel()
        self._current = QLabel()
        self._bar = QProgressBar()
        self._stop = QPushButton()
        self._build()
        self.retranslate()

    def start(self, path: str) -> None:
        """Reset for a new scan of ``path``."""
        self._path = path
        self._started = time.monotonic()
        self._last = None
        self._stop.setEnabled(True)
        self._update()

    def show_progress(self, progress: ScanProgress) -> None:
        """Show the latest counts."""
        self._last = progress
        self._update()

    def stopping(self) -> None:
        """Show that the scan is being stopped."""
        self._stop.setEnabled(False)
        self._title.setText(tr("scan_stopping"))

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self._stop.setText(tr("scan_stop"))
        self._stop.setToolTip(tr("action_stop_tip"))
        self._update()

    def _build(self) -> None:
        font = QFont(self._title.font())
        font.setPointSizeF(font.pointSizeF() * 1.5)
        font.setBold(True)
        self._title.setFont(font)
        self._title.setWordWrap(True)
        # A long path must not widen the window: the label takes any width and elides.
        self._current.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._current.setStyleSheet("color: palette(placeholder-text);")
        self._bar.setRange(0, 0)
        self._bar.setTextVisible(False)
        self._stop.setMinimumHeight(36)
        self._stop.clicked.connect(self.stop_requested)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.addStretch(1)
        for widget in (self._title, self._bar, self._counts, self._current):
            layout.addWidget(widget)
        layout.addWidget(self._stop, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(2)

    def _update(self) -> None:
        self._title.setText(tr("scan_title", path=self._path))
        progress = self._last
        elapsed = format_duration(time.monotonic() - self._started)
        if progress is None:
            self._counts.setText(tr("scan_starting"))
            self._current.setText("")
            return
        self._counts.setText(tr("scan_counts", files=format_count(progress.files),
                                folders=format_count(progress.folders), size=format_size(progress.size),
                                time=elapsed))
        width = max(100, self._current.width())
        self._current.setText(self._current.fontMetrics().elidedText(progress.current, Qt.TextElideMode.ElideMiddle,
                                                                     width))
