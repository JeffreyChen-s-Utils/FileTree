"""Independent concurrent scan windows embedded in owned, closable result tabs."""

from __future__ import annotations

import os

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import QMainWindow, QTabWidget, QToolButton

from je_file_tree.gui.i18n import current_language, tr
from je_file_tree.gui.locale_font import language_font
from je_file_tree.gui.main_window import MainWindow
from je_file_tree.gui.operation_group import OperationGroup
from je_file_tree.gui.background_monitor import BackgroundMonitor

MAX_TABS = 16


class ScanWorkspace(QMainWindow):
    """Keep each tab's tree, worker, filters and history separate; serialize source mutations."""

    def __init__(self, settings: QSettings, first: MainWindow) -> None:
        super().__init__()
        self._language_base_font = self.font()
        self.settings = settings
        self.operations = OperationGroup()
        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._activated)
        self.setCentralWidget(self.tabs)
        self._closing, self._services = False, False
        self._force_close = False
        self.background = BackgroundMonitor(self)
        self.new_button = QToolButton(self)
        self.new_button.clicked.connect(lambda _checked=False: self.add_tab())
        self.tabs.setCornerWidget(self.new_button, Qt.Corner.TopRightCorner)
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
        window._operations = self.operations
        window._close_all = self.quit_application
        window._background_settings = self.background.configure_dialog
        window._background_pause = self.background.quiesce
        window._recurring_show = self.background.show_proposals
        window._actions["background_monitor"].setEnabled(True)
        window._language_changed = self.retranslate
        window.setWindowFlags(Qt.WindowType.Widget)
        self.operations.windows.append(window)
        window.path_edit.textChanged.connect(lambda: self._label(window))
        window.results.tree_model.modelReset.connect(lambda: self._label(window))
        self.tabs.setCurrentIndex(self.tabs.addTab(window, tr("workspace_empty")))
        self._label(window)
        self.new_button.setEnabled(self.tabs.count() < MAX_TABS)
        self.operations.refresh(window)

    def add_tab(self, folder: str | None = None) -> MainWindow | None:
        """Create a separate result/worker owner, bounded to sixteen simultaneous tabs."""
        if self._closing or self.tabs.count() >= MAX_TABS:
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
        if window._last_roots:
            title = tr("multi_roots")
        self.tabs.setTabText(index, title.replace("&", "&&"))
        self.tabs.setTabToolTip(index, "\n".join(window._last_roots) or path)

    def _activated(self, _index: int) -> None:
        if self.tabs.count() and not self._closing:
            self.current._update_actions()

    def close_tab(self, index: int) -> None:
        """Cancel and join only the closed tab's workers before destroying its result objects."""
        if self._closing or not 0 <= index < self.tabs.count():
            return
        if self.tabs.count() == 1:
            self.close()
            return
        window = self.tabs.widget(index)
        window.close()
        self.tabs.removeTab(index)
        self.operations.windows.remove(window)
        window.deleteLater()
        self.new_button.setEnabled(True)
        self.operations.refresh(self.current)
        if self._services:
            self.current._updates.start()

    def start_services(self) -> None:
        """Schedule application services only after the actual application has shown the workspace."""
        self._services = True
        self.current._updates.start()
        self.background.start()

    def retranslate(self) -> None:
        """Language is application-wide; translate every result tab and the workspace controls."""
        self.setFont(language_font(current_language(), self._language_base_font))
        self.new_action.setText(tr("workspace_new"))
        self.new_button.setText(tr("workspace_new"))
        self.new_button.setToolTip(tr("workspace_new_tip"))
        self.close_action.setText(tr("workspace_close"))
        for window in self.operations.windows:
            window.retranslate()
            self._label(window)
        self.setWindowTitle(self.current.windowTitle())
        self.background.retranslate()

    def quit_application(self) -> None:
        """Explicit Quit always exits, independently of the opt-in close-to-tray preference."""
        self._force_close = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Join every owned tab before closing the application; never leave a scan thread behind."""
        if not self._force_close and self.background.can_hide:
            self.hide()
            event.ignore()
            return
        self._closing = True
        self.background.shutdown()
        for window in tuple(self.operations.windows):
            window.close()
        self.settings.setValue("workspace_geometry", self.saveGeometry())
        super().closeEvent(event)
