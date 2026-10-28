"""Independent concurrent scan windows embedded in owned, closable result tabs."""

from __future__ import annotations

import os

from PySide6.QtCore import QByteArray, QSettings, QThread, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMainWindow, QMessageBox, QTabWidget, QToolButton, QWidget

from je_file_tree.gui.i18n import current_language, tr
from je_file_tree.gui.locale_font import apply_language_font
from je_file_tree.gui.main_window import MainWindow
from je_file_tree.gui.operation_group import OperationGroup
from je_file_tree.gui.background_monitor import BackgroundMonitor
from je_file_tree.gui.worker_lifecycle import after_threads
from je_file_tree.gui.startup_state import MAX_TABS, WorkspaceState
from je_file_tree.gui.scan_preferences import ScanDefaults
from je_file_tree.core.scanner import ScanOptions
from je_file_tree.gui.workspace_templates import WorkspaceTemplate
from je_file_tree.gui.workspace_templates_dialog import WorkspaceTemplatesDialog


class ScanWorkspace(QMainWindow):
    """Keep each tab's tree, worker, filters and history separate; serialize source mutations."""

    def __init__(self, settings: QSettings, first: MainWindow) -> None:
        super().__init__()
        self.settings = settings
        self.operations = OperationGroup()
        self._scan_defaults: ScanDefaults | None = None
        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._activated)
        self.setCentralWidget(self.tabs)
        self._closing, self._services = False, False
        self._force_close = False
        self._close_ready = False
        self._replacement: WorkspaceState | None = None
        self._replacement_report: tuple[tuple[str, ...], ...] = ()
        self._templates_dialog: WorkspaceTemplatesDialog | None = None
        self.background = BackgroundMonitor(self)
        self.new_button = QToolButton(self)
        self.new_button.clicked.connect(lambda _checked=False: self.add_tab())
        self.templates_action = QAction(self)
        self.templates_action.triggered.connect(self.show_templates)
        self.templates_button = QToolButton(self)
        self.templates_button.setDefaultAction(self.templates_action)
        corner = QWidget(self)
        controls = QHBoxLayout(corner)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self.templates_button)
        controls.addWidget(self.new_button)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self.new_action = QAction(self)
        self.new_action.setShortcut(QKeySequence("Ctrl+T"))
        self.new_action.triggered.connect(lambda _checked=False: self.add_tab())
        self.addAction(self.new_action)
        self.close_action = QAction(self)
        self.close_action.setShortcut(QKeySequence("Ctrl+W"))
        self.close_action.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        self.addAction(self.close_action)
        self.resize(1100, 760)
        geometry = self.settings.value("workspace_geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        self._insert(first)
        self.retranslate()

    @property
    def current(self) -> MainWindow:
        """The active tab; an open workspace always retains at least one tab."""
        return self.tabs.currentWidget()

    def _insert(self, window: MainWindow) -> None:
        window._menus["menu_file"].addAction(self.templates_action)
        window._operations = self.operations
        window._scan_defaults = self._scan_defaults
        window._close_all = self.quit_application
        window._restart_arguments = self.restart_arguments
        window._background_settings = self.background.configure_dialog
        window._background_pause = self.background.quiesce
        window._recurring_show = self.background.show_proposals
        window._actions["background_monitor"].setEnabled(True)
        window._language_changed = self.retranslate
        window.setWindowFlags(Qt.WindowType.Widget)
        self.operations.windows.append(window)
        window.shutdown_finished.connect(lambda: QTimer.singleShot(0, self, lambda: self._remove_closed_tab(window)))
        window.path_edit.textChanged.connect(lambda: self._label(window))
        window.scan_scope_changed.connect(lambda: self._label(window))
        window.results.tree_model.modelReset.connect(lambda: self._label(window))
        self.tabs.setCurrentIndex(self.tabs.addTab(window, tr("workspace_empty")))
        self._label(window)
        self.new_button.setEnabled(self.tabs.count() < MAX_TABS)
        self.operations.refresh(window)

    def restore_scan_preferences(self, options: tuple[ScanOptions, ...]) -> None:
        """Share imported process defaults while retaining each tab's independent checked flags."""
        self._scan_defaults = ScanDefaults(options[0].workers, options[0].exclude)
        for index, preferences in enumerate(options):
            self.tabs.widget(index).restore_scan_preferences(preferences, self._scan_defaults)

    def restart_arguments(self) -> list[str]:
        """Capture live tabs in visual order; restart performs fresh scans of their explicit roots."""
        windows = [self.tabs.widget(index) for index in range(self.tabs.count())
                   if not self.tabs.widget(index)._closing]
        scopes = tuple(window.capture_restart_scope() for window in windows)
        active = windows.index(self.current) if self.current in windows else 0
        return WorkspaceState(scopes, active, tuple(window._scan_options() for window in windows)).arguments()

    def add_tab(self, folder: str | None = None) -> MainWindow | None:
        """Create a separate result/worker owner, bounded to sixteen simultaneous tabs."""
        if self._closing or self._replacement is not None or self.tabs.count() >= MAX_TABS:
            return None
        window = MainWindow(self.settings, operations=self.operations)
        self._insert(window)
        if folder:
            window.start_scan(folder)
        return window

    def _label(self, window: MainWindow) -> None:
        index = self.tabs.indexOf(window)
        if index < 0:
            return
        path = window.path_edit.text()
        title = os.path.basename(os.path.normpath(path)) or path if path else tr("workspace_empty")
        scope = window.capture_scan_scope()
        if isinstance(scope, tuple):
            title = tr("multi_roots")
        self.tabs.setTabText(index, title.replace("&", "&&"))
        self.tabs.setTabToolTip(index, "\n".join(scope) if isinstance(scope, tuple) else path)

    def _activated(self, _index: int) -> None:
        if self.tabs.count() and not self._closing and self._replacement is None:
            self.current._update_actions()

    def close_tab(self, index: int) -> None:
        """Cancel only this tab; keep its ownership until its asynchronous shutdown completes."""
        if self._closing or self._replacement is not None or not 0 <= index < self.tabs.count():
            return
        if self.tabs.count() == 1:
            self.close()
            return
        window = self.tabs.widget(index)
        window.close()

    def _remove_closed_tab(self, window: MainWindow) -> None:
        if self._closing:
            return
        index = self.tabs.indexOf(window)
        if index < 0 or not window._close_ready:
            return
        self.tabs.removeTab(index)
        self.operations.windows.remove(window)
        window.deleteLater()
        if self._replacement is not None:
            if not self.operations.windows:
                self._install_template()
            return
        self.new_button.setEnabled(True)
        self.operations.refresh(self.current)
        if self._services:
            self.current._updates.start()

    def capture_template_state(self) -> WorkspaceState:
        """Snapshot visual tab order, edited next inputs and transient scan choices."""
        windows = [self.tabs.widget(index) for index in range(self.tabs.count())]
        return WorkspaceState(tuple(window.capture_scan_scope() for window in windows),
                              self.tabs.currentIndex(), tuple(window._scan_options() for window in windows))

    def show_templates(self) -> None:
        """Preview metadata without changing current scans; replacement requires its explicit action."""
        if self._closing or self._replacement is not None or self.operations.busy or self._templates_dialog is not None:
            return
        try:
            dialog = WorkspaceTemplatesDialog(self.settings, self.capture_template_state(), self)
        except ValueError:
            QMessageBox.warning(self, tr("workspace_templates"), tr("templates_invalid"))
            return
        self._templates_dialog = dialog
        dialog.finished.connect(lambda result: self._templates_finished(dialog, result))
        dialog.open()

    def _templates_finished(self, dialog: WorkspaceTemplatesDialog, result: int) -> None:
        state, report = dialog.chosen, dialog.report
        self._templates_dialog = None
        dialog.deleteLater()
        if result == QDialog.DialogCode.Accepted and state is not None and report is not None:
            self.replace_template(state, report)

    def replace_template(self, state: WorkspaceState, report: tuple[tuple[str, ...], ...]) -> bool:
        """Retire owned tabs asynchronously before installing checked, idle next-scan inputs."""
        if self._closing or self._replacement is not None or self.operations.busy:
            return False
        WorkspaceTemplate("replacement", state)
        if len(report) != len(state.tabs):
            raise ValueError("Incomplete workspace validation")
        for scope, issues in zip(state.tabs, report, strict=True):
            count = len(scope) if isinstance(scope, tuple) else int(scope is not None)
            if len(issues) != count or not all(isinstance(issue, str) for issue in issues):
                raise ValueError("Incomplete root validation")
        self._replacement, self._replacement_report = state, report
        self.tabs.setEnabled(False)
        self.new_action.setEnabled(False)
        self.close_action.setEnabled(False)
        self.templates_action.setEnabled(False)
        self.background.quiesce(wait=False)
        for window in tuple(self.operations.windows):
            window.close()
        return True

    def _install_template(self) -> None:
        after_threads(tuple(self.background.findChildren(QThread)), self._finish_install_template, self)

    def _finish_install_template(self) -> None:
        state, report = self._replacement, self._replacement_report
        if state is None or self._closing:
            return
        for scope, issues in zip(state.tabs, report, strict=True):
            window = MainWindow(self.settings, operations=self.operations)
            self._insert(window)
            roots = scope if isinstance(scope, tuple) else (scope,) if scope else ()
            errors = tuple(f"{root}: {reason}" for root, reason in zip(roots, issues, strict=True) if reason)
            window.prepare_scan_scope(scope, errors)
            self._label(window)
        if state.options is not None:
            self.restore_scan_preferences(state.options)
        self.tabs.setCurrentIndex(state.active)
        self._replacement = None
        self._replacement_report = ()
        self.tabs.setEnabled(True)
        self.new_action.setEnabled(True)
        self.close_action.setEnabled(True)
        self.templates_action.setEnabled(True)
        self.current._update_actions()
        if self._services:
            self.current._updates.start()

    def start_services(self) -> None:
        """Schedule application services only after the actual application has shown the workspace."""
        self._services = True
        self.current._updates.start()
        self.background.start()

    def retranslate(self) -> None:
        """Language is application-wide; translate every result tab and the workspace controls."""
        apply_language_font(current_language())
        self.templates_action.setText(tr("workspace_templates"))
        self.new_action.setText(tr("workspace_new"))
        self.new_button.setText(tr("workspace_new"))
        self.new_button.setToolTip(tr("workspace_new_tip"))
        self.close_action.setText(tr("workspace_close"))
        for window in self.operations.windows:
            window.retranslate()
            self._label(window)
        if self.tabs.count():
            self.setWindowTitle(self.current.windowTitle())
        self.background.retranslate()

    def quit_application(self) -> None:
        """Explicit Quit always exits, independently of the opt-in close-to-tray preference."""
        self._force_close = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Keep Qt events running while all owned tabs and background services retire."""
        if self._close_ready:
            super().closeEvent(event)
            return
        if self._closing:
            event.ignore()
            return
        if not self._force_close and self.background.can_hide:
            self.hide()
            event.ignore()
            return
        self._closing = True
        self._replacement = None
        if self._templates_dialog is not None:
            self._templates_dialog.reject()
        self.setEnabled(False)
        self.statusBar().showMessage(tr("closing_workers"))
        self.background.shutdown(wait=False)
        for window in tuple(self.operations.windows):
            window.close()
        event.ignore()
        after_threads(tuple(self.findChildren(QThread)), lambda: QTimer.singleShot(0, self, self._finish_close), self)

    def _finish_close(self) -> None:
        if any(not window._close_ready for window in self.operations.windows):
            QTimer.singleShot(10, self, self._finish_close)
            return
        self.background.shutdown()
        self.settings.setValue("workspace_geometry", self.saveGeometry())
        self._close_ready = True
        self.close()
