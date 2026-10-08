"""The first page: pick a folder or a drive to scan, in one click."""

from __future__ import annotations

from dataclasses import dataclass
import threading

from PySide6.QtCore import QStorageInfo, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from je_file_tree.core.formatting import AUTO_UNIT, format_size
from je_file_tree.core.trash_size import TrashUsage
from je_file_tree.gui.bin_labels import bin_caption, bin_key
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.worker_lifecycle import after_threads

_MAX_RECENT = 6


def drives() -> list[QStorageInfo]:
    """Mounted volumes that are ready and have a size, as shown on the welcome page."""
    return [volume for volume in QStorageInfo.mountedVolumes()
            if volume.isValid() and volume.isReady() and volume.bytesTotal() > 0]


@dataclass(frozen=True, slots=True)
class DriveSnapshot:
    """Copied native drive values; UI rendering never queries storage."""

    root: str
    name: str
    total: int
    available: int


class DriveWorker(QThread):
    """Discover native volumes on a cancellable worker, publishing copied values only."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.cancel = threading.Event()

    def run(self) -> None:
        """An in-progress OS query remains owned; canceled results never refresh the UI."""
        try:
            rows = []
            for volume in drives():
                if self.cancel.is_set():
                    return
                rows.append(DriveSnapshot(volume.rootPath(), volume.displayName(),
                                          volume.bytesTotal(), volume.bytesAvailable()))
            if not self.cancel.is_set():
                self.ready.emit(tuple(rows))
        except (OSError, ValueError) as error:
            if not self.cancel.is_set():
                self.failed.emit(str(error))


class WelcomePage(QWidget):
    """A big "choose a folder" button, one button per drive, and the recently scanned folders."""

    choose_folder_requested = Signal()
    scan_requested = Signal(str)
    scan_all_requested = Signal()
    overview_requested = Signal()
    bins_requested = Signal()
    bin_refresh_requested = Signal()
    drives_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recent: list[str] = []
        self.drive_rows: tuple[DriveSnapshot, ...] = ()
        self._drive_worker: DriveWorker | None = None
        self._drive_refresh_pending = False
        self._closed = False
        self.unit = AUTO_UNIT
        self._bin_data: dict[str, TrashUsage] = {}
        self._bin_labels: dict[str, tuple[str, QLabel]] = {}
        self._title = QLabel()
        self._subtitle = QLabel()
        self._choose = QPushButton()
        self.scan_all = QPushButton()
        self.scan_all.clicked.connect(self.scan_all_requested)
        self._drives_title = QLabel()
        self._overview = QPushButton()
        self._overview.clicked.connect(self.overview_requested)
        self._bins = QPushButton()
        self._bins.clicked.connect(self.bins_requested)
        self.bin_refresh = QPushButton()
        self.bin_refresh.clicked.connect(self.bin_refresh_requested)
        self._drives = QGridLayout()
        self._recent_title = QLabel()
        self._recent_box = QVBoxLayout()
        self._tip = QLabel()
        self._build()
        self.retranslate()
        self._drive_timer = QTimer(self)
        self._drive_timer.setSingleShot(True)
        self._drive_timer.timeout.connect(self.refresh_drives)
        self._drive_timer.start(0)

    def set_recent(self, folders: list[str]) -> None:
        """Show these recently scanned folders (most recent first)."""
        self._recent = folders[:_MAX_RECENT]
        self._fill_recent()

    def refresh_drives(self) -> None:
        """Queue native discovery; repeated requests coalesce while one OS query is active."""
        if self._closed:
            return
        self._drive_timer.stop()
        if self._drive_worker is not None:
            self._drive_refresh_pending = True
            return
        worker = DriveWorker(self)
        self._drive_worker = worker
        worker.ready.connect(lambda rows: self._show_drives(worker, rows))
        worker.failed.connect(lambda reason: not self._closed and self._drives_title.setToolTip(reason))
        worker.finished.connect(lambda: after_threads((worker,), lambda: self._drive_finished(worker), self))
        worker.start()

    def _show_drives(self, worker: DriveWorker, rows: tuple[DriveSnapshot, ...]) -> None:
        if self._closed or worker is not self._drive_worker or worker.cancel.is_set():
            return
        self.drive_rows = rows
        self._drives_title.setToolTip("")
        self._fill_drives()
        self.drives_changed.emit()

    def _drive_finished(self, worker: DriveWorker) -> None:
        self._drive_worker = None
        worker.deleteLater()
        if self._drive_refresh_pending and not self._closed:
            self._drive_refresh_pending = False
            self.refresh_drives()

    def shutdown(self) -> None:
        """Invalidate replies and join discovery before this page is destroyed."""
        self._closed = True
        self._drive_timer.stop()
        if self._drive_worker is not None:
            self._drive_worker.cancel.set()
            wait_for(self._drive_worker)

    def set_bin_metadata(self, rows: dict[str, TrashUsage]) -> None:
        """Update visible drive labels with copied query results; missing scopes remain unqueried."""
        self._bin_data = dict(rows)
        self._update_bin_labels()

    def set_unit(self, unit: str) -> None:
        """Format cached per-drive bin amounts in the current size unit."""
        self.unit = unit
        self._update_bin_labels()

    def _update_bin_labels(self) -> None:
        for key, (root, label) in self._bin_labels.items():
            label.setText(bin_caption(root, self._bin_data.get(key), self.unit))

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self._title.setText(tr("welcome_title"))
        self._subtitle.setText(tr("welcome_subtitle"))
        self._choose.setText(tr("welcome_choose"))
        self._choose.setToolTip(tr("action_open_tip"))
        self.scan_all.setText(tr("scan_all_drives"))
        self.scan_all.setToolTip(tr("multi_hint"))
        self._drives_title.setText(tr("welcome_drives"))
        self._overview.setText(tr("action_volumes"))
        self._overview.setToolTip(tr("action_volumes_tip"))
        self._bins.setText(tr("action_bins"))
        self.bin_refresh.setText(tr("bin_labels_refresh"))
        self.bin_refresh.setToolTip(tr("bin_labels_hint"))
        self._recent_title.setText(tr("welcome_recent"))
        self._tip.setText(tr("welcome_tip"))
        self._fill_drives()
        self._fill_recent()

    def _build(self) -> None:
        title_font = QFont(self._title.font())
        title_font.setPointSizeF(title_font.pointSizeF() * 1.8)
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._subtitle.setWordWrap(True)
        self._choose.setMinimumHeight(44)
        self._choose.setDefault(True)
        self._choose.clicked.connect(self.choose_folder_requested)
        self._tip.setWordWrap(True)
        self._tip.setStyleSheet("color: palette(placeholder-text);")
        for label in (self._drives_title, self._recent_title):
            font = QFont(label.font())
            font.setBold(True)
            label.setFont(font)

        card = QWidget()
        card.setMinimumWidth(480)
        card.setMaximumWidth(680)
        column = QVBoxLayout(card)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)
        column.addWidget(self._title)
        column.addWidget(self._subtitle)
        column.addWidget(self._choose)
        column.addWidget(self.scan_all)
        column.addSpacing(8)
        column.addWidget(self._drives_title)
        column.addLayout(self._drives)
        column.addWidget(self._overview)
        column.addWidget(self._bins)
        column.addWidget(self.bin_refresh)
        column.addSpacing(8)
        column.addWidget(self._recent_title)
        column.addLayout(self._recent_box)
        column.addSpacing(8)
        column.addWidget(self._tip)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 32, 24, 24)
        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)

    def _fill_drives(self) -> None:
        _clear(self._drives)
        self._bin_labels = {}
        for row, volume in enumerate(self.drive_rows):
            used = volume.total - volume.available
            name = volume.name or volume.root
            root = volume.root
            button = QPushButton(f"{name}  ({root})" if name != root else root)
            button.setToolTip(tr("welcome_drive_tip", path=root))
            button.clicked.connect(lambda _checked=False, path=root: self.scan_requested.emit(path))
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(round(1000 * used / volume.total))
            bar.setTextVisible(False)
            bar.setMaximumHeight(10)
            free = QLabel(tr("welcome_drive_free", free=format_size(volume.available),
                             total=format_size(volume.total)))
            self._drives.addWidget(button, row * 2, 0)
            self._drives.addWidget(bar, row * 2, 1)
            self._drives.addWidget(free, row * 2, 2)
            bin_label = QLabel()
            bin_label.setWordWrap(True)
            bin_label.setTextFormat(Qt.TextFormat.PlainText)
            bin_label.setToolTip(tr("bin_labels_hint"))
            self._bin_labels[bin_key(root)] = (root, bin_label)
            self._drives.addWidget(bin_label, row * 2 + 1, 0, 1, 3)
        self._drives.setColumnStretch(1, 1)
        self._update_bin_labels()

    def _fill_recent(self) -> None:
        _clear(self._recent_box)
        self._recent_title.setVisible(bool(self._recent))
        for folder in self._recent:
            button = QPushButton(folder)
            button.setFlat(True)
            button.setStyleSheet("text-align: left;")
            button.setToolTip(tr("welcome_drive_tip", path=folder))
            button.clicked.connect(lambda _checked=False, path=folder: self.scan_requested.emit(path))
            self._recent_box.addWidget(button)


def _clear(layout: QGridLayout | QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            # Hidden and detached now: deleteLater alone would leave it drawn at
            # its old place until the event loop runs.
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
