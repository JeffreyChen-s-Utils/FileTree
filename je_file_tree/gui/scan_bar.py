"""The bar above the results while a scan runs: live counts, the folder being read, and a Stop button."""

from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from je_file_tree.core.formatting import format_count, format_size
from je_file_tree.core.scanner import ScanProgress
from je_file_tree.gui.i18n import format_duration, tr
from je_file_tree.gui.elided_label import ElidedLabel

_BUSY_BAR_WIDTH = 120


class ScanBar(QFrame):
    """Progress of the running scan, shown above the tree that is filling in."""

    stop_requested = Signal()
    pause_requested = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._started = time.monotonic()
        self._last: ScanProgress | None = None
        self._stopping = False
        self._analysing = False
        self._counts = QLabel()
        self._current = ElidedLabel()
        self._feedback = QLabel()
        self._feedback.setTextFormat(Qt.TextFormat.PlainText)
        self._counts.setTextFormat(Qt.TextFormat.PlainText)
        self._busy = QProgressBar()
        self._stop = QPushButton()
        self._pause = QPushButton()
        self._pause.setCheckable(True)
        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._update)
        self._build()
        self.retranslate()

    def start(self) -> None:
        """Reset for a new scan and show the bar."""
        self._started = time.monotonic()
        self._last = None
        self._stopping = False
        self._analysing = False
        self._pause.setChecked(False)
        self._pause.setEnabled(True)
        self._stop.setEnabled(True)
        self._update()
        self.show()

    def show_progress(self, progress: ScanProgress) -> None:
        """Show the latest counts."""
        self._last = progress
        self._update()

    def stopping(self) -> None:
        """Show that the scan is being stopped."""
        self._stopping = True
        self._pause.setEnabled(False)
        self._stop.setEnabled(False)
        self._update()

    def analysing(self) -> None:
        """Folder reads finished: pause no longer applies to final analysis."""
        self._analysing = True
        self._pause.setEnabled(False)
        self._update()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self._stop.setText(tr("scan_stop"))
        self._stop.setToolTip(tr("action_stop_tip"))
        self._pause.setToolTip(tr("scan_pause_tip"))
        self._update()

    def _build(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._busy.setRange(0, 0)
        self._busy.setTextVisible(False)
        self._busy.setFixedWidth(_BUSY_BAR_WIDTH)
        # A long path must not widen the window: the label takes any width and elides.
        self._current.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._current.setStyleSheet("color: palette(placeholder-text);")
        self._stop.clicked.connect(self.stop_requested)
        self._pause.clicked.connect(self.pause_requested)
        self._pause.toggled.connect(self._update)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(self._counts)
        texts.addWidget(self._current)
        row = QHBoxLayout(self)
        texts.addWidget(self._feedback)
        self._feedback.setWordWrap(True)
        self._feedback.setStyleSheet("color: palette(placeholder-text);")
        row.setContentsMargins(12, 10, 12, 10)
        row.addWidget(self._busy)
        row.addLayout(texts, 1)
        row.addWidget(self._pause)
        row.addWidget(self._stop)
        self.hide()

    def _update(self) -> None:
        self._pause.setText(tr("scan_resume" if self._pause.isChecked() else "scan_pause"))
        paused = self._pause.isChecked() and not self._analysing and not self._stopping
        self._busy.setRange(0, 1 if paused else 0)
        self._busy.setValue(0)
        phase = "stopping" if self._stopping else "analysing" if self._analysing else "paused" if paused else "running"
        self._feedback.setText(tr("overview_scan_" + phase) + " · "
                               + tr("overview_scan_elapsed", time=format_duration(time.monotonic() - self._started)))
        self._busy.setAccessibleName(tr("overview_scan_" + phase))
        if self._stopping:
            self._counts.setText(tr("scan_stopping"))
            return
        if self._analysing:
            self._counts.setText(tr("scan_analysing"))
            return
        progress = self._last
        if progress is None:
            text = tr("scan_starting")
            self._counts.setText(tr("scan_paused", progress=text) if self._pause.isChecked() else text)
            self._current.setText("")
            return
        elapsed = format_duration(time.monotonic() - self._started)
        self._counts.setText(tr("scan_progress", files=format_count(progress.files),
                                folders=format_count(progress.folders), size=format_size(progress.size),
                                time=elapsed))
        if self._pause.isChecked():
            self._counts.setText(tr("scan_paused", progress=self._counts.text()))
        self._current.setText(progress.current)

    def showEvent(self, event: QShowEvent) -> None:
        """Qt: refresh elapsed feedback even while a worker is waiting inside one native read."""
        super().showEvent(event)
        self._clock.start()

    def hideEvent(self, event: QHideEvent) -> None:
        """Qt: stop presentation updates when no scan bar is visible."""
        self._clock.stop()
        super().hideEvent(event)
