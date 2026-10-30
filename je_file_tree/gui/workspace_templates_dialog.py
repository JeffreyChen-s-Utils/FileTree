"""Preview and check named workspaces before explicitly replacing their result tabs."""

from dataclasses import replace
from html import escape
import os
import stat

from PySide6.QtCore import QSettings, QSignalBlocker, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_preferences import SCAN_FLAGS
from je_file_tree.gui.startup_state import WorkspaceState
from je_file_tree.gui.worker_lifecycle import WorkerDialog, after_threads, queue_worker
from je_file_tree.gui.workspace_templates import ReplacementImpact, WorkspaceTemplate, read_templates, write_templates


_PATH_COLUMN = 2


class ScopeCheckWorker(QThread):
    """Check every retained root off the GUI thread without discarding inaccessible inputs."""

    checked = Signal(object)

    def __init__(self, state: WorkspaceState, parent: QWidget) -> None:
        super().__init__(parent)
        self.state = state

    def run(self) -> None:
        """Return one ordered status per root, preserving all tabs and combined scopes."""
        report = []
        for scope in self.state.tabs:
            issues = []
            roots = scope if isinstance(scope, tuple) else (scope,) if scope else ()
            for root in roots:
                if self.isInterruptionRequested():
                    return
                try:
                    reason = "" if stat.S_ISDIR(os.stat(root).st_mode) else tr("templates_not_folder")
                except OSError as error:
                    reason = str(error)
                if self.isInterruptionRequested():
                    return
                issues.append(reason)
            report.append(tuple(issues))
        self.checked.emit(tuple(report))


class WorkspaceTemplatesDialog(WorkerDialog):
    """Manage persisted metadata and stage an explicitly checked replacement without scanning."""

    replacement_requested = Signal()

    def __init__(self, settings: QSettings, current: WorkspaceState, parent: QWidget | None = None) -> None:
        items = read_templates(settings)
        super().__init__(parent)
        self.settings, self.current = settings, current
        self.items = list(items)
        self.chosen: WorkspaceState | None = None
        self.report: tuple[tuple[str, ...], ...] | None = None
        self._worker: ScopeCheckWorker | None = None
        self._draft = current
        self._rows: list[tuple[int, int]] = []
        self._impact = ReplacementImpact()
        self.setWindowTitle(tr("workspace_templates"))
        self.resize(940, 680)
        self.list, self.name = QComboBox(), QLineEdit()
        self.list.setPlaceholderText(tr("templates_select"))
        self.table = QTableWidget(0, 4)
        self.table.setTabKeyNavigation(False)
        self.table.setHorizontalHeaderLabels([tr("templates_tab"), tr("templates_kind"),
                                             tr("column_path"), tr("templates_status")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 160)
        self.table.setMinimumHeight(100)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(50)
        self.details.setTabChangesFocus(True)
        self.impact_summary = QLabel()
        self.impact_summary.setWordWrap(True)
        self.impact_details = QPlainTextEdit()
        self.impact_details.setReadOnly(True)
        self.impact_details.setTabChangesFocus(True)
        self.impact_details.setMaximumHeight(76)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.check = QPushButton(tr("templates_check"))
        self.load = QPushButton(tr("templates_replace"))
        self.load.setEnabled(False)
        self._build()
        self._fill()
        self.list.currentIndexChanged.connect(self._selected)
        self.table.itemChanged.connect(self._edited)
        self.check.clicked.connect(self._check)
        self.load.clicked.connect(self._load)
        self._preview(current)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        saved = QGroupBox(tr("templates_save_section"))
        save_layout = QVBoxLayout(saved)
        source = QLabel(tr("templates_save_source"))
        source.setWordWrap(True)
        save_layout.addWidget(source)
        form = QFormLayout()
        form.addRow(tr("templates_saved"), self.list)
        form.addRow(tr("presets_name"), self.name)
        save_layout.addLayout(form)
        actions = QHBoxLayout()
        self.saved_buttons = {}
        for action, key in (("add", "templates_add_current"), ("update", "templates_update_current"),
                            ("rename", "presets_rename"), ("remove", "templates_remove")):
            button = QPushButton(tr(key))
            button.clicked.connect(lambda _checked=False, action=action: self._edit_saved(action))
            self.saved_buttons[action] = button
            actions.addWidget(button)
        save_layout.addLayout(actions)
        layout.addWidget(saved)
        self.preview_hint = QLabel(tr("templates_preview_hint"))
        self.preview_hint.setWordWrap(True)
        layout.addWidget(self.preview_hint)
        layout.addWidget(self.table)
        layout.addWidget(self.details)
        layout.addWidget(self.status)
        layout.addWidget(self.check)
        layout.addWidget(self.impact_summary)
        layout.addWidget(self.impact_details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        buttons.addButton(self.load, QDialogButtonBox.ButtonRole.AcceptRole)
        layout.addWidget(buttons)
        order = (self.list, self.name, *self.saved_buttons.values(), self.table, self.details,
                 self.check, self.impact_details, self.load, self.cancel)
        for before, after in zip(order, order[1:], strict=False):
            QWidget.setTabOrder(before, after)
        self.set_replacement_impact(self._impact)

    def set_replacement_impact(self, impact: ReplacementImpact) -> None:
        """Render the workspace's live snapshot without changing saved or staged inputs."""
        self._impact = impact
        unavailable = sum(bool(reason) for issues in self.report or () for reason in issues)
        self.impact_summary.setText(tr("templates_impact", tabs=len(impact.tabs),
            scans=sum(tab.scanning for tab in impact.tabs), results=sum(tab.has_result for tab in impact.tabs),
            unavailable=unavailable if self.report is not None else tr("templates_unchecked")))
        lines = []
        for index, tab in enumerate(impact.tabs):
            state = tr("templates_active") if tab.active else ""
            if tab.scanning:
                state += " " + tr("templates_scanning")
            scope = tab.scope if isinstance(tab.scope, tuple) else (tab.scope or tr("workspace_empty"),)
            lines.append(f"{index + 1}. {tab.title} {state}\n" + "\n".join(scope))
        self.impact_details.setPlainText("\n".join(lines))

    def _fill(self, index: int = -1) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems([item.name for item in self.items])
        self.list.setCurrentIndex(index)
        self.list.blockSignals(False)
        self._saved_actions(index)

    def _saved_actions(self, index: int) -> None:
        for action in ("update", "rename", "remove"):
            self.saved_buttons[action].setEnabled(0 <= index < len(self.items))

    def _invalidate(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
            self._worker = None
        self.report = None
        self.load.setEnabled(False)
        with QSignalBlocker(self.table):
            for row in range(self.table.rowCount()):
                self.table.item(row, 3).setText(tr("templates_unchecked"))
                self.table.item(row, 3).setToolTip(f"<p>{escape(tr('templates_unchecked'))}</p>")
        self.set_replacement_impact(self._impact)

    def _selected(self, index: int) -> None:
        self._saved_actions(index)
        if 0 <= index < len(self.items):
            self.name.setText(self.items[index].name)
            self._preview(self.items[index].state)

    def _preview(self, state: WorkspaceState) -> None:
        self._invalidate()
        self._draft = state
        self.preview_hint.setText(tr("templates_preview_hint"))
        self.status.setText(tr("templates_unchecked"))
        self._rows = []
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for tab, scope in enumerate(state.tabs):
            roots = scope if isinstance(scope, tuple) else (scope or "",)
            kind = (tr("multi_roots") if isinstance(scope, tuple)
                    else tr("templates_single") if scope else tr("workspace_empty"))
            for root_index, root in enumerate(roots):
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._rows.append((tab, root_index))
                label = f"{tab + 1} ({tr('templates_active')})" if tab == state.active else str(tab + 1)
                for column, text in enumerate((label, kind, root, tr("templates_unchecked"))):
                    item = QTableWidgetItem(text)
                    item.setToolTip(f"<p>{escape(text)}</p>")
                    if column != _PATH_COLUMN:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        descriptions = []
        for index, options in enumerate(state.options or ()):
            flags = "; ".join(tr(f"action_{action}") for action, field in SCAN_FLAGS if getattr(options, field))
            descriptions.append(f"{index + 1}: " + tr("presets_options", workers=options.workers,
                                exclusions=len(options.exclude), flags=flags or tr("presets_no_flags")))
        self.details.setPlainText("\n".join(descriptions))

    def _edited(self, item: QTableWidgetItem) -> None:
        if item.column() != _PATH_COLUMN:
            return
        with QSignalBlocker(self.table):
            item.setToolTip(f"<p>{escape(item.text())}</p>")
        self._invalidate()
        self.preview_hint.setText(tr("templates_preview_modified"))
        self.status.setText(tr("templates_unchecked"))

    def _table_state(self) -> WorkspaceState:
        tabs = list(self._draft.tabs)
        for row, (tab, root) in enumerate(self._rows):
            text = self.table.item(row, _PATH_COLUMN).text()
            scope = tabs[tab]
            if isinstance(scope, tuple):
                roots = list(scope)
                roots[root] = text
                tabs[tab] = tuple(roots)
            else:
                tabs[tab] = text or None
        return replace(self._draft, tabs=tuple(tabs))

    def _edit_saved(self, action: str) -> None:
        index = self.list.currentIndex()
        if action != "add" and not 0 <= index < len(self.items):
            return
        items = self.items.copy()
        try:
            if action == "remove":
                items.pop(index)
            elif action == "rename":
                items[index] = replace(items[index], name=self.name.text().strip())
            elif action == "update":
                items[index] = WorkspaceTemplate(self.name.text().strip(), self.current)
            else:
                items.append(WorkspaceTemplate(self.name.text().strip(), self.current))
                index = len(items) - 1
            write_templates(self.settings, tuple(items))
        except ValueError:
            self.status.setText(tr("templates_invalid"))
            self.name.setFocus()
            return
        self.items = items
        self._fill(min(index, len(items) - 1))
        self._selected(self.list.currentIndex())

    def _check(self) -> None:
        self._invalidate()
        try:
            draft = self._table_state()
            WorkspaceTemplate("preview", draft)
            self._draft = draft
        except ValueError:
            self.status.setText(tr("templates_invalid"))
            self.table.setFocus()
            return
        worker = ScopeCheckWorker(self._draft, self)
        self._worker = worker
        worker.checked.connect(lambda report: self._checked(worker, report))
        worker.finished.connect(lambda: self._release_worker(worker))
        queue_worker(worker, lambda: self._worker is worker and not self._finish_waiting, self,
                     discarded=worker.deleteLater)
        self.status.setText(tr("templates_checking"))

    def _release_worker(self, worker: ScopeCheckWorker) -> None:
        if self._worker is worker:
            self._worker = None
        after_threads((worker,), worker.deleteLater, self)

    def _checked(self, worker: ScopeCheckWorker, report: tuple[tuple[str, ...], ...]) -> None:
        if worker is not self._worker or self._finish_waiting:
            return
        self.report = report
        self.table.blockSignals(True)
        for row, (tab, root) in enumerate(self._rows):
            reason = report[tab][root] if report[tab] else tr("workspace_empty")
            self.table.item(row, 3).setText(reason or tr("templates_ready"))
            self.table.item(row, 3).setToolTip(f"<p>{escape(reason or tr('templates_ready'))}</p>")
        self.table.blockSignals(False)
        self.status.setText(tr("templates_checked"))
        self.load.setEnabled(True)
        self.set_replacement_impact(self._impact)

    def _load(self) -> None:
        if self.report is not None:
            self.replacement_requested.emit()
            self.chosen = self._draft
            self.accept()

    def done(self, result: int) -> None:
        """Retain the dialog until availability workers have joined."""
        if not self.defer_done(result):
            super().done(result)

    def shutdown(self, *, wait: bool = True) -> None:
        """Invalidate replies; cancellation never mutates tabs or dispatches scans."""
        self._worker = None
        for worker in self.findChildren(QThread):
            worker.requestInterruption()
