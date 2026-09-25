"""The main window: toolbar and menus around two pages (welcome, results; a scan fills the results live)."""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import QByteArray, QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QToolBar,
)

from file_tree import __version__
from file_tree.core import export
from file_tree.core.formatting import AUTO_UNIT, SIZE_UNITS, format_share, format_size
from file_tree.core.node import Node
from file_tree.core.scanner import ScanOptions
from file_tree.gui import elevation, file_actions
from file_tree.gui.help_dialog import HelpDialog
from file_tree.gui.i18n import LANGUAGES, current_language, set_language, tr
from file_tree.gui.qt_translation import apply_qt_translation
from file_tree.gui.results_view import ResultsView
from file_tree.core.analysis import Summary
from file_tree.gui.scan_worker import AnalyseWorker, ScanOutcome, ScanWorker
from file_tree.gui.welcome import WelcomePage

WELCOME_PAGE, RESULTS_PAGE = range(2)
# How often the tree of a running scan is refreshed.
LIVE_REFRESH_MS = 700
_MAX_RECENT = 10
_UNITS = (AUTO_UNIT, *SIZE_UNITS[1:5])
_STATUS_TIMEOUT_MS = 8000
ASK_ADMIN_KEY = "ask_admin_at_start"


def read_flag(settings: QSettings, key: str, default: bool) -> bool:
    """A yes/no setting (the registry keeps them as the strings \"true\" and \"false\")."""
    value = settings.value(key, default)
    return value if isinstance(value, bool) else str(value).lower() == "true"


class MainWindow(QMainWindow):
    """The FileTree window."""

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings if settings is not None else QSettings()
        self._worker: ScanWorker | None = None
        self._analyser: AnalyseWorker | None = None
        self._last_path = ""
        self._unit = str(self.settings.value("unit", AUTO_UNIT))
        if self._unit not in _UNITS:
            self._unit = AUTO_UNIT
        self.welcome = WelcomePage()
        self.results = ResultsView()
        self.pages = QStackedWidget()
        for page in (self.welcome, self.results):
            self.pages.addWidget(page)
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(LIVE_REFRESH_MS)
        self._live_timer.timeout.connect(self.results.refresh_live)
        self.setCentralWidget(self.pages)
        self.path_edit = QLineEdit()
        self._actions: dict[str, QAction] = {}
        self._menus: dict[str, QMenu] = {}
        self._unit_actions: dict[str, QAction] = {}
        self._language_actions: dict[str, QAction] = {}
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._connect()
        self.setAcceptDrops(True)
        self.resize(1100, 720)
        self._restore()
        self.retranslate()
        self._update_actions()

    # --- scanning ---------------------------------------------------------

    def start_scan(self, path: str) -> None:
        """Scan ``path`` (stopping a scan already running)."""
        path = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
        if not os.path.isdir(path):
            QMessageBox.warning(self, tr("scan_failed_title"), tr("not_a_folder", path=path))
            return
        self.stop_scan(wait=True)
        self._last_path = path
        self.path_edit.setText(path)
        include_hidden = self._actions["hidden"].isChecked()
        worker = ScanWorker(path, ScanOptions(include_hidden=include_hidden), self)
        # Signals of a worker that was replaced (a new scan started while it was
        # stopping) arrive late and must not touch the window any more.
        worker.started.connect(lambda root: self._is_current(worker) and self.results.show_live_root(root))
        worker.progressed.connect(
            lambda progress: self._is_current(worker) and self.results.show_progress(progress))
        worker.succeeded.connect(lambda outcome: self._is_current(worker) and self._scan_succeeded(outcome))
        worker.failed.connect(lambda reason: self._is_current(worker) and self._scan_failed(reason))
        worker.cancelled.connect(lambda outcome: self._is_current(worker) and self._scan_cancelled(outcome))
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self.results.begin_scan()
        self.pages.setCurrentIndex(RESULTS_PAGE)
        self._update_actions()
        self._live_timer.start()
        worker.start()

    def stop_scan(self, *, wait: bool = False) -> None:
        """Ask the running scan (if any) to stop; with ``wait``, until it has."""
        worker = self._worker
        if worker is None:
            return
        worker.cancel()
        self.results.scan_bar.stopping()
        if wait:
            worker.wait()
            self._worker = None
            self._live_timer.stop()

    def _is_current(self, worker: ScanWorker) -> bool:
        return worker is self._worker

    def rescan(self) -> None:
        """Scan the last folder again."""
        if self._last_path:
            self.start_scan(self._last_path)

    def _scan_succeeded(self, outcome: ScanOutcome) -> None:
        self._scan_ended()
        self.results.show_outcome(outcome)
        self.pages.setCurrentIndex(RESULTS_PAGE)
        self._remember(outcome.result.root.path)
        self._update_actions()

    def _scan_failed(self, reason: str) -> None:
        self._scan_ended()
        self._back_from_scan()
        QMessageBox.warning(self, tr("scan_failed_title"), tr("scan_failed", path=self._last_path, reason=reason))

    def _scan_cancelled(self, outcome: ScanOutcome | None) -> None:
        self._scan_ended()
        if outcome is None:
            self._back_from_scan()
            self.statusBar().showMessage(tr("scan_cancelled"), _STATUS_TIMEOUT_MS)
            return
        self.results.show_outcome(outcome)
        self._update_actions()
        self.statusBar().showMessage(tr("scan_stopped_partial"), _STATUS_TIMEOUT_MS)

    def _scan_ended(self) -> None:
        self._worker = None
        self._live_timer.stop()

    def _back_from_scan(self) -> None:
        self.results.end_scan()
        self.pages.setCurrentIndex(RESULTS_PAGE if self.results.outcome is not None else WELCOME_PAGE)
        self._update_actions()

    # --- entry actions ----------------------------------------------------

    def show_menu_for(self, node: Node, point: QPoint) -> None:
        """Pop up the menu of things to do with ``node``."""
        menu = QMenu(self)
        entries: list[tuple[str, Callable[[], object]]] = [
            ("menu_open_item", lambda: file_actions.open_path(node.path)),
            ("menu_reveal", lambda: file_actions.reveal_in_file_manager(node.path)),
            ("menu_copy_path", lambda: file_actions.copy_path(node.path)),
        ]
        if node.is_dir and not node.is_link:
            entries.append(("menu_show_treemap", lambda: self._show_in_treemap(node)))
            entries.append(("menu_rescan_here", lambda: self.rescan_folder(node)))
            entries.append(("menu_scan_here", lambda: self.start_scan(node.path)))
        for key, handler in entries:
            menu.addAction(tr(key)).triggered.connect(handler)
        if node.parent is not None:
            menu.addSeparator()
            menu.addAction(tr("action_trash")).triggered.connect(lambda: self.move_to_trash(node))
        menu.exec(point)

    def rescan_folder(self, node: Node) -> None:
        """Scan one folder again and swap it into the results (the whole scan when it is the root)."""
        if self._worker is not None or self.results.outcome is None:
            return
        if node.parent is None:
            self.rescan()
            return
        include_hidden = self._actions["hidden"].isChecked()
        worker = ScanWorker(node.path, ScanOptions(include_hidden=include_hidden), self)
        before = node.size
        worker.progressed.connect(
            lambda progress: self._is_current(worker) and self.results.scan_bar.show_progress(progress))
        worker.succeeded.connect(
            lambda outcome: self._is_current(worker) and self._branch_rescanned(node, outcome, before))
        worker.failed.connect(lambda reason: self._is_current(worker) and self._scan_failed(reason))
        worker.cancelled.connect(lambda _outcome: self._is_current(worker) and self._branch_cancelled())
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        self.results.scan_bar.start()
        self._update_actions()
        worker.start()

    def _branch_rescanned(self, old: Node, outcome: ScanOutcome, before: int) -> None:
        self._scan_ended()
        self.results.scan_bar.hide()
        new = self.results.replace_branch(old, outcome.result)
        self._update_actions()
        self.statusBar().showMessage(tr("rescan_done", name=new.name, before=format_size(before, self._unit),
                                        after=format_size(new.size, self._unit)), _STATUS_TIMEOUT_MS)
        analyser = AnalyseWorker(self.results.tree_model.root, self)
        analyser.done.connect(self._summary_ready)
        analyser.finished.connect(analyser.deleteLater)
        self._analyser = analyser
        analyser.start()

    def _summary_ready(self, summary: Summary) -> None:
        self.results.apply_summary(summary)

    def _branch_cancelled(self) -> None:
        self._scan_ended()
        self.results.scan_bar.hide()
        self._update_actions()
        self.statusBar().showMessage(tr("scan_cancelled"), _STATUS_TIMEOUT_MS)

    def move_to_trash(self, node: Node) -> None:
        """Ask, then move ``node`` to the Recycle Bin / Trash and take it out of the results."""
        if node.parent is None or self._worker is not None:
            return
        answer = QMessageBox.question(self, tr("trash_confirm_title"),
                                      tr("trash_confirm", name=node.name, size=format_size(node.size, self._unit)))
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not file_actions.move_to_trash(node.path):
            QMessageBox.warning(self, tr("trash_confirm_title"), tr("trash_failed", name=node.name))
            return
        size = node.size
        self.results.forget(node)
        self.statusBar().showMessage(tr("trash_done", name=node.name, size=format_size(size, self._unit)),
                                     _STATUS_TIMEOUT_MS)

    def _show_in_treemap(self, node: Node) -> None:
        self.results.treemap.set_view_root(node)
        self.results.tabs.setCurrentIndex(0)

    def _trash_selected(self) -> None:
        node = self.results.selected_node()
        if node is not None and self.pages.currentIndex() == RESULTS_PAGE:
            self.move_to_trash(node)

    def _selection_changed(self, node: Node | None) -> None:
        if node is None:
            self.statusBar().clearMessage()
            return
        size = format_size(node.size, self._unit)
        if node.parent is None:
            self.statusBar().showMessage(tr("status_selected_root", name=node.name, size=size))
            return
        self.statusBar().showMessage(tr("status_selected", name=node.name, size=size,
                                        share=format_share(node.share_of_parent())))

    # --- export -----------------------------------------------------------

    def export_results(self, kind: str) -> None:
        """Save the results: ``"folders"`` or ``"largest"`` as CSV, ``"json"`` as JSON."""
        outcome = self.results.outcome
        if outcome is None:
            return
        is_json = kind == "json"
        suggested = f"{_safe_name(outcome.result.root.name)}-{kind}.{'json' if is_json else 'csv'}"
        start = os.path.join(str(self.settings.value("export_dir", os.path.expanduser("~"))), suggested)
        target, _ = QFileDialog.getSaveFileName(self, tr("export_title"), start,
                                                tr("json_filter") if is_json else tr("csv_filter"))
        if not target:
            return
        try:
            if kind == "folders":
                count = export.export_folders_csv(outcome.result.root, target)
            elif kind == "largest":
                count = export.export_files_csv(self.results.largest_model.rows(), target)
            else:
                export.export_json(outcome.result.root, target)
                count = outcome.result.root.dir_count + 1
        except OSError as error:
            QMessageBox.warning(self, tr("export_title"), tr("export_failed", reason=error.strerror or str(error)))
            return
        self.settings.setValue("export_dir", os.path.dirname(target))
        self.statusBar().showMessage(tr("export_done", count=count, path=target), _STATUS_TIMEOUT_MS)

    # --- settings, language, units ----------------------------------------

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit`` and remember it."""
        self._unit = unit
        self.settings.setValue("unit", unit)
        self.results.set_unit(unit)
        self._unit_actions[unit].setChecked(True)

    def change_language(self, code: str) -> None:
        """Switch every text to another language and remember it."""
        set_language(code)
        apply_qt_translation(code)
        self.settings.setValue("language", code)
        self.retranslate()

    def retranslate(self) -> None:
        """Re-read every translated text."""
        self.setWindowTitle(tr("app_title_admin") if elevation.is_elevated() else tr("app_title"))
        for key, action in self._actions.items():
            action.setText(tr(f"action_{key}"))
            action.setToolTip(tr(f"action_{key}_tip"))
            action.setStatusTip(tr(f"action_{key}_tip"))
        for key, menu in self._menus.items():
            menu.setTitle(tr(key))
        for unit, action in self._unit_actions.items():
            action.setText(tr("unit_auto") if unit == AUTO_UNIT else unit)
        self.path_edit.setPlaceholderText(tr("path_placeholder"))
        self.path_edit.setToolTip(tr("path_placeholder"))
        self.welcome.retranslate()
        self.results.retranslate()
        self._language_actions[current_language()].setChecked(True)

    def _remember(self, path: str) -> None:
        recent = [path, *(folder for folder in self._recent() if os.path.normcase(folder) != os.path.normcase(path))]
        self.settings.setValue("recent", recent[:_MAX_RECENT])
        self.welcome.set_recent(recent)

    def _recent(self) -> list[str]:
        value = self.settings.value("recent", [])
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value] if isinstance(value, list) else []

    def _restore(self) -> None:
        geometry = self.settings.value("geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        splitter = self.settings.value("splitter")
        if isinstance(splitter, QByteArray):
            self.results.splitter.restoreState(splitter)
        self._actions["hidden"].setChecked(read_flag(self.settings, "include_hidden", True))
        self._actions["ask_admin"].setChecked(read_flag(self.settings, ASK_ADMIN_KEY, True))
        self._unit_actions[self._unit].setChecked(True)
        self.results.set_unit(self._unit)
        self.welcome.set_recent(self._recent())

    def closeEvent(self, event: QCloseEvent) -> None:
        """Qt: stop the scan and remember the window layout."""
        self.stop_scan(wait=True)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.results.splitter.saveState())
        self.settings.setValue("include_hidden", self._actions["hidden"].isChecked())
        super().closeEvent(event)

    # --- drag and drop ----------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Qt: accept a folder dragged from the file manager."""
        if _dropped_folder(event.mimeData().urls()) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Qt: scan the dropped folder."""
        folder = _dropped_folder(event.mimeData().urls())
        if folder is not None:
            event.acceptProposedAction()
            self.start_scan(folder)

    # --- building ---------------------------------------------------------

    def _build_actions(self) -> None:
        definitions: list[tuple[str, QKeySequence | str | None, Callable[[], object]]] = [
            ("open", QKeySequence.StandardKey.Open, self.choose_folder),
            ("rescan", QKeySequence.StandardKey.Refresh, self.rescan),
            ("stop", "Esc", self.stop_scan),
            ("export_folders", None, lambda: self.export_results("folders")),
            ("export_largest", None, lambda: self.export_results("largest")),
            ("export_json", None, lambda: self.export_results("json")),
            ("trash", QKeySequence.StandardKey.Delete, self._trash_selected),
            ("quit", "Ctrl+Q", self.close),  # Windows has no standard Quit key
            ("hidden", None, lambda: self.settings.setValue("include_hidden", self._actions["hidden"].isChecked())),
            ("elevate", None, self.restart_as_admin),
            ("ask_admin", None, lambda: self.settings.setValue(ASK_ADMIN_KEY, self._actions["ask_admin"].isChecked())),
            ("help", QKeySequence.StandardKey.HelpContents, self.show_help),
            ("about", None, self.show_about),
        ]
        for key, shortcut, handler in definitions:
            action = QAction(self)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda _checked=False, run=handler: run())
            self._actions[key] = action
        self._actions["hidden"].setCheckable(True)
        self._actions["ask_admin"].setCheckable(True)
        self._actions["elevate"].setVisible(elevation.can_elevate())
        self._actions["ask_admin"].setVisible(elevation.supported())

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("")
        for key in ("open", "rescan", "stop"):
            file_menu.addAction(self._actions[key])
        export_menu = file_menu.addMenu("")
        for key in ("export_folders", "export_largest", "export_json"):
            export_menu.addAction(self._actions[key])
        file_menu.addSeparator()
        file_menu.addAction(self._actions["trash"])
        file_menu.addAction(self._actions["elevate"])
        file_menu.addSeparator()
        file_menu.addAction(self._actions["quit"])
        view_menu = bar.addMenu("")
        unit_menu = view_menu.addMenu("")
        units = QActionGroup(self)
        for unit in _UNITS:
            action = unit_menu.addAction(unit)
            action.setCheckable(True)
            units.addAction(action)
            action.triggered.connect(lambda _checked=False, chosen=unit: self.set_unit(chosen))
            self._unit_actions[unit] = action
        language_menu = view_menu.addMenu("")
        languages = QActionGroup(self)
        for code, name in LANGUAGES.items():
            action = language_menu.addAction(name)
            action.setCheckable(True)
            languages.addAction(action)
            action.triggered.connect(lambda _checked=False, chosen=code: self.change_language(chosen))
            self._language_actions[code] = action
        view_menu.addSeparator()
        view_menu.addAction(self._actions["hidden"])
        view_menu.addAction(self._actions["ask_admin"])
        help_menu = bar.addMenu("")
        help_menu.addAction(self._actions["help"])
        help_menu.addAction(self._actions["about"])
        self._menus = {"menu_file": file_menu, "menu_export": export_menu, "menu_view": view_menu,
                       "menu_unit": unit_menu, "menu_language": language_menu, "menu_help": help_menu}

    def _build_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.addAction(self._actions["open"])
        toolbar.addAction(self._actions["rescan"])
        toolbar.addAction(self._actions["stop"])
        toolbar.addSeparator()
        self.path_edit.setClearButtonEnabled(True)
        self.path_edit.returnPressed.connect(lambda: self.start_scan(self.path_edit.text()))
        toolbar.addWidget(self.path_edit)
        toolbar.addSeparator()
        toolbar.addAction(self._actions["help"])
        self.addToolBar(toolbar)

    def _connect(self) -> None:
        self.welcome.choose_folder_requested.connect(self.choose_folder)
        self.welcome.scan_requested.connect(self.start_scan)
        self.results.scan_bar.stop_requested.connect(self.stop_scan)
        self.results.node_menu_requested.connect(self.show_menu_for)
        self.results.selection_changed.connect(self._selection_changed)
        self.results.elevate_requested.connect(self.restart_as_admin)

    def _update_actions(self) -> None:
        scanning = self._worker is not None
        has_results = self.results.outcome is not None
        self._actions["stop"].setEnabled(scanning)
        self._actions["rescan"].setEnabled(bool(self._last_path) and not scanning)
        for key in ("export_folders", "export_largest", "export_json", "trash"):
            self._actions[key].setEnabled(has_results and not scanning)

    # --- dialogs ----------------------------------------------------------

    def choose_folder(self) -> None:
        """Ask for a folder and scan it."""
        start = self._last_path or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, tr("choose_folder_title"), start)
        if folder:
            self.start_scan(folder)

    def restart_as_admin(self) -> None:
        """Start FileTree again as administrator (scanning the same folder) and close this copy.

        When the prompt is declined, this copy keeps running and says so.
        """
        arguments = [self._last_path] if self._last_path else []
        if elevation.relaunch_elevated(arguments):
            self.close()
            return
        self.statusBar().showMessage(tr("elevate_declined"), _STATUS_TIMEOUT_MS)

    def show_help(self) -> None:
        """Open the how-to-use window."""
        HelpDialog(self).exec()

    def show_about(self) -> None:
        """Show the version."""
        QMessageBox.about(self, tr("action_about"), tr("about_text", version=__version__))


def _dropped_folder(urls: list) -> str | None:
    for url in urls:
        if url.isLocalFile() and os.path.isdir(url.toLocalFile()):
            return os.path.normpath(url.toLocalFile())
    return None


def _safe_name(name: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "-_" else "_" for character in name)
    return cleaned.strip("_") or "scan"

