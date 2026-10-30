"""Bounded result guidance using captured worker statistics, without filesystem queries."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from je_file_tree.core.coverage import Coverage
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_size
from je_file_tree.core.node import Node
from je_file_tree.gui.i18n import tr


class ResultHighlights(QWidget):
    """Collapsible next steps; retained node references never grant source-operation authority."""

    folder_requested = Signal(object)
    cleanup_requested = Signal()
    problems_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.unit = AUTO_UNIT
        self._folders: tuple[Node, ...] | None = None
        self._coverage: Coverage | None = None
        self._state = "empty"
        self._cleanup: tuple[int, int] | None = None
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setChecked(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.body = QWidget()
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        self.folders = [QPushButton() for _ in range(3)]
        for index, button in enumerate(self.folders):
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, row=index: self._choose(row))
        self.cleanup = QPushButton()
        self.cleanup.clicked.connect(self.cleanup_requested)
        self.problems = QPushButton()
        self.problems.clicked.connect(self.problems_requested)
        self.problems.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        grid = QGridLayout(self.body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self.message, 0, 0, 1, 3)
        for index, button in enumerate(self.folders):
            grid.addWidget(button, 1, index)
        grid.addWidget(self.cleanup, 2, 0)
        grid.addWidget(self.problems, 2, 1, 1, 2)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self.toggle.toggled.connect(self._expand)
        self._expand(True)

    def show_scan(self, folders: tuple[Node, ...] | None, state: str, coverage: Coverage | None) -> None:
        """Render at most three direct folders and already captured coverage counters."""
        self._folders, self._state, self._coverage = folders, state, coverage
        self.retranslate()

    def show_cleanup(self, summary: tuple[int, int] | None) -> None:
        """None means pending; an empty completed result is explicitly distinct."""
        self._cleanup = summary
        self.retranslate()

    def _expand(self, expanded: bool) -> None:
        self.body.setVisible(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def _choose(self, row: int) -> None:
        if self._folders is not None and row < len(self._folders):
            self.folder_requested.emit(self._folders[row])

    def retranslate(self) -> None:
        """Update text without changing expansion, tree selection or list position."""
        self.toggle.setText(tr("highlights_title"))
        self.toggle.setAccessibleDescription(tr("highlights_title"))
        key = "highlights_waiting" if self._folders is None else (
            "highlights_partial" if self._state == "partial" else "highlights_folders")
        self.message.setText(tr(key))
        for index, button in enumerate(self.folders):
            node = self._folders[index] if self._folders and index < len(self._folders) else None
            button.setVisible(node is not None)
            if node is not None:
                text = tr("highlights_folder", name=node.name, size=format_size(node.size, self.unit))
                button.setText(text.replace("&", "&&"))
                button.setAccessibleName(text)
                button.setToolTip(node.path or node.name)
        ready = self._state in ("complete", "partial")
        self.cleanup.setEnabled(ready)
        self.cleanup.setText(tr("highlights_cleanup_waiting") if self._cleanup is None else tr(
            "highlights_cleanup", count=format_count(self._cleanup[0]), size=format_size(self._cleanup[1], self.unit)))
        self.cleanup.setToolTip(tr("highlights_cleanup_hint"))
        coverage = self._coverage
        self.problems.setEnabled(ready)
        text = tr("highlights_coverage_unknown") if coverage is None else tr(
            "highlights_coverage", skipped=format_count(coverage.skipped_folders),
            denied=format_count(coverage.inaccessible_folders), pending=format_count(coverage.pending_folders))
        self.problems.setText(text)
        self.problems.setToolTip(text)
        self.problems.setAccessibleName(text)
