"""Persistent scalar cleanup results and explicitly dated free-space observations."""

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QHideEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from je_file_tree.core.capacity import CapacityLedger
from je_file_tree.core.formatting import AUTO_UNIT, format_count, format_size, format_time
from je_file_tree.core.node import Node
from je_file_tree.core.operations import MoveSummary
from je_file_tree.core.snapshot import unpack_snapshot
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.strings import EN

_MAX_REASONS = 5
_DETAIL_WIDTH, _DETAIL_HEIGHT = 680, 280


class _DetailsPopup(QFrame):
    hidden = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self.hidden.emit()


class CleanupCompletion(QWidget):
    """Keep one batch's scalar outcome across rescans without retaining an obsolete scan tree."""

    records_requested = Signal()
    undo_requested = Signal()
    rescan_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.unit = AUTO_UNIT
        self._summary: MoveSummary | None = None
        self._source = ""
        self._identity: tuple[int, int] | None = None
        self._before: int | None = None
        self._before_at = 0.0
        self._after_at = 0.0
        self._delta: int | None = None
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.body = QWidget()
        self.source, self.counts, self.space, self.reasons = (QLabel() for _ in range(4))
        for label in (self.source, self.counts, self.space, self.reasons):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._build()
        self.set_actions(undo=False, rescan=False)
        self.retranslate()
        self.hide()

    def _build(self) -> None:
        self.records, self.undo, self.rescan, self.dismiss = (QPushButton() for _ in range(4))
        self.records.clicked.connect(lambda: self._request(self.records_requested.emit))
        self.undo.clicked.connect(lambda: self._request(self.undo_requested.emit))
        self.rescan.clicked.connect(lambda: self._request(lambda: self.rescan_requested.emit(self._source)))
        self.dismiss.clicked.connect(self.clear)
        self.toggle.toggled.connect(self._expand)
        buttons = QHBoxLayout()
        for button in (self.records, self.undo, self.rescan, self.dismiss):
            buttons.addWidget(button)
        content = QVBoxLayout(self.body)
        content.setContentsMargins(0, 0, 0, 0)
        for label in (self.source, self.counts, self.space, self.reasons):
            content.addWidget(label)
        content.addLayout(buttons)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.body)
        self.popup = _DetailsPopup(self)
        popup_layout = QVBoxLayout(self.popup)
        popup_layout.addWidget(self.scroll)
        self.popup.hidden.connect(lambda: self.toggle.setChecked(False))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toggle)
        self._expand(False)

    def _expand(self, expanded: bool) -> None:
        self.body.setVisible(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        if not expanded:
            self.popup.hide()
            return
        self.popup.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,
                                self.window().testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen))
        screen = self.screen().availableGeometry()
        self.popup.resize(min(_DETAIL_WIDTH, screen.width()), min(_DETAIL_HEIGHT, screen.height()))
        anchor = self.toggle.mapToGlobal(QPoint(0, self.toggle.height()))
        self.popup.move(max(screen.left(), min(anchor.x(), screen.right() - self.popup.width() + 1)),
                        max(screen.top(), min(anchor.y(), screen.bottom() - self.popup.height() + 1)))
        self.popup.show()

    def hideEvent(self, event: QHideEvent) -> None:
        """Close the transient details whenever the owning result page is hidden."""
        self.popup.hide()
        super().hideEvent(event)

    def _request(self, callback: Callable[[], None]) -> None:
        self.toggle.setChecked(False)
        callback()

    def show_summary(self, summary: MoveSummary, root: Node | None, baseline: CapacityLedger | None) -> None:
        """Capture scalar scope/measurement data only; a previous scan is the labeled baseline."""
        self._summary = summary
        self._source = (root.path or "") if root is not None else ""
        self._identity = unpack_snapshot(root.snapshot).identity if root is not None and root.snapshot else None
        self._before = baseline.free if baseline is not None else None
        self._before_at = baseline.measured_at if baseline is not None else 0.0
        self._after_at, self._delta = 0.0, None
        self.show()
        self.retranslate()

    def observe(self, root: Node, ledger: CapacityLedger | None) -> None:
        """Compare only later observations of the same recorded root, including unrelated activity."""
        if (self._summary is None or ledger is None or self._before is None or ledger.free is None
                or self._identity is None or root.snapshot is None or root.path != self._source
                or unpack_snapshot(root.snapshot).identity != self._identity
                or ledger.measured_at <= max(self._before_at, self._after_at)):
            return
        self._delta = ledger.free - self._before
        self._after_at = ledger.measured_at
        self.retranslate()

    def set_actions(self, *, undo: bool, rescan: bool) -> None:
        """Reflect the existing owner's guards; a button never extends undo authority."""
        self.undo.setEnabled(undo)
        self.rescan.setEnabled(rescan and bool(self._source))

    def clear(self) -> None:
        """Dismiss retained metadata without changing any operation or undo state."""
        self._summary = None
        self._source, self._identity, self._before = "", None, None
        self.set_actions(undo=False, rescan=False)
        self.hide()

    def retranslate(self) -> None:
        """Format retained counts, refusal reasons and separately observed free space."""
        self.toggle.setText(tr("completion_title"))
        self.toggle.setAccessibleDescription(tr("completion_title"))
        self.records.setText(tr("action_recent_actions"))
        self.undo.setText(tr("completion_undo"))
        self.rescan.setText(tr("completion_rescan"))
        self.dismiss.setText(tr("completion_dismiss"))
        summary = self._summary
        if summary is None:
            return
        self.source.setText(tr("completion_source", path=self._source or tr("multi_roots")))
        self.counts.setText(tr("completion_counts", moved=format_count(summary.moved),
                               skipped=format_count(summary.skipped), failed=format_count(summary.failed),
                               size=format_size(summary.moved_bytes, self.unit)))
        self.toggle.setText(tr("completion_title") + " — " + self.counts.text())
        self.toggle.setToolTip(self.toggle.text())
        change = tr("size_unknown") if self._delta is None else (
            ("+" if self._delta >= 0 else "−") + format_size(abs(self._delta), self.unit))
        self.space.setText(tr("completion_space", change=change))
        self.space.setToolTip(tr("completion_measurements", before=format_time(self._before_at),
                                 after=format_time(self._after_at)) if self._delta is not None else
                              tr("completion_space_pending"))
        self.reasons.setText(self._reason_text(summary))

    def _reason_text(self, summary: MoveSummary) -> str:
        reasons = []
        for reason, count in summary.skip_reasons[:_MAX_REASONS]:
            key = f"trash_skip_{reason}"
            reasons.append(tr("completion_reason", reason=tr(key) if key in EN else reason,
                              count=format_count(count)))
        detail = "; ".join(reasons)
        if len(summary.skip_reasons) > _MAX_REASONS:
            detail += " " + tr("completion_more")
        if summary.journal_errors or summary.copy_errors:
            detail += " " + tr("completion_errors", journal=format_count(summary.journal_errors),
                               copies=format_count(summary.copy_errors))
        return (detail + "\n" if detail else "") + tr("completion_hint")
