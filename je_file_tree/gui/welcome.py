"""The first page: pick a folder or a drive to scan, in one click."""

from __future__ import annotations

from PySide6.QtCore import QStorageInfo, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from je_file_tree.core.formatting import format_size
from je_file_tree.gui.i18n import tr

_MAX_RECENT = 6


def drives() -> list[QStorageInfo]:
    """Mounted volumes that are ready and have a size, as shown on the welcome page."""
    return [volume for volume in QStorageInfo.mountedVolumes()
            if volume.isValid() and volume.isReady() and volume.bytesTotal() > 0]


class WelcomePage(QWidget):
    """A big "choose a folder" button, one button per drive, and the recently scanned folders."""

    choose_folder_requested = Signal()
    scan_requested = Signal(str)
    overview_requested = Signal()
    bins_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recent: list[str] = []
        self._title = QLabel()
        self._subtitle = QLabel()
        self._choose = QPushButton()
        self._drives_title = QLabel()
        self._overview = QPushButton()
        self._overview.clicked.connect(self.overview_requested)
        self._bins = QPushButton()
        self._bins.clicked.connect(self.bins_requested)
        self._drives = QGridLayout()
        self._recent_title = QLabel()
        self._recent_box = QVBoxLayout()
        self._tip = QLabel()
        self._build()
        self.retranslate()

    def set_recent(self, folders: list[str]) -> None:
        """Show these recently scanned folders (most recent first)."""
        self._recent = folders[:_MAX_RECENT]
        self._fill_recent()

    def refresh_drives(self) -> None:
        """Re-read the list of drives and how full they are."""
        self._fill_drives()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self._title.setText(tr("welcome_title"))
        self._subtitle.setText(tr("welcome_subtitle"))
        self._choose.setText(tr("welcome_choose"))
        self._choose.setToolTip(tr("action_open_tip"))
        self._drives_title.setText(tr("welcome_drives"))
        self._overview.setText(tr("action_volumes"))
        self._overview.setToolTip(tr("action_volumes_tip"))
        self._bins.setText(tr("action_bins"))
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
        column.addSpacing(8)
        column.addWidget(self._drives_title)
        column.addLayout(self._drives)
        column.addWidget(self._overview)
        column.addWidget(self._bins)
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
        for row, volume in enumerate(drives()):
            used = volume.bytesTotal() - volume.bytesAvailable()
            name = volume.displayName() or volume.rootPath()
            root = volume.rootPath()
            button = QPushButton(f"{name}  ({root})" if name != root else root)
            button.setToolTip(tr("welcome_drive_tip", path=root))
            button.clicked.connect(lambda _checked=False, path=root: self.scan_requested.emit(path))
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(round(1000 * used / volume.bytesTotal()))
            bar.setTextVisible(False)
            bar.setMaximumHeight(10)
            free = QLabel(tr("welcome_drive_free", free=format_size(volume.bytesAvailable()),
                             total=format_size(volume.bytesTotal())))
            self._drives.addWidget(button, row, 0)
            self._drives.addWidget(bar, row, 1)
            self._drives.addWidget(free, row, 2)
        self._drives.setColumnStretch(1, 1)

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
