"""The main window: toolbar and menus around two pages (welcome, results; a scan fills the results live)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Sequence

from PySide6.QtCore import QByteArray, QPoint, QSettings, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtPrintSupport import QPrintDialog
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QInputDialog,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QToolBar,
)

from je_file_tree import __version__
from je_file_tree.core import export
from je_file_tree.core.analysis import Summary
from je_file_tree.core.duplicates import DuplicateGroup
from je_file_tree.core.cleanup import DETAILS, CleanupGroup
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting, load_policy
from je_file_tree.core.formatting import AUTO_UNIT, SIZE_UNITS, format_count, format_share, format_size
from je_file_tree.core.node import Node, outermost
from je_file_tree.core.operations import MoveResult
from je_file_tree.core.operation_journal import JournalApproval, OperationJournal
from je_file_tree.core.protected import protected_places, protection_of
from je_file_tree.core.scanner import DEFAULT_WORKERS, ScanOptions
from je_file_tree.core.system_files import system_file
from je_file_tree.core.trash_size import TrashUsage
from je_file_tree.gui import elevation, file_actions, shell_integration
from je_file_tree.gui.shell_dialog import ShellIntegrationDialog
from je_file_tree.gui.special_files import SpecialFilesDialog
from je_file_tree.gui.live_compare import LiveCompareDialog
from je_file_tree.gui.git_history import GitHistoryDialog
from je_file_tree.gui.history import HistoryDialog, HistorySettings, configured_history, history_folder, history_limit
from je_file_tree.core.history import ScanHistory
from je_file_tree.gui.projects import ProjectsDialog
from je_file_tree.gui.programs import ProgramsDialog
from je_file_tree.gui.virtual_disks import VirtualDisksDialog
from je_file_tree.gui.file_times import FileTimesDialog
from je_file_tree.gui.bin_labels import BinLabels, bin_key
from je_file_tree.gui.compression import CompressionDialog
from je_file_tree.gui.namespace_dialog import NamespaceDialog
from je_file_tree.gui.copy_dialog import CopyDialog
from je_file_tree.gui.duplicate_link_dialog import DuplicateLinksDialog
from je_file_tree.core.copy_approval import CopyApproval
from je_file_tree.gui.report_dialog import ReportDialog
from je_file_tree.gui.volumes import VolumesDialog
from je_file_tree.gui.bin_dialog import BinDialog
from je_file_tree.gui.exclusions_dialog import ExclusionsDialog
from je_file_tree.gui.cleanup_review import CleanupReview
from je_file_tree.gui.cleanup_policy_dialog import CleanupPolicyDialog
from je_file_tree.gui.help_dialog import HelpDialog
from je_file_tree.gui.i18n import LANGUAGES, current_language, set_language, tr
from je_file_tree.gui.qt_translation import apply_qt_translation
from je_file_tree.gui.results_view import CHART_TAB, ResultsView
from je_file_tree.gui.graphics_export import SVG_MODES, capture_svg, save_graphic
from je_file_tree.gui.printing import print_view, save_view_pdf, view_printer
from je_file_tree.gui.list_transfer import ListCapture, ListStream
from je_file_tree.gui.scan_worker import AnalyseWorker, ExportWorker, ScanOutcome, ScanWorker, wait_for
from je_file_tree.gui.trash_worker import TrashWorker
from je_file_tree.gui.trash_undo import TrashUndo
from je_file_tree.gui.recent_actions import RecentActions, journal_folder
from je_file_tree.gui.welcome import WelcomePage, drives
from je_file_tree.gui.multi_scan import MultiScanDialog
from je_file_tree.gui.themes import ThemeMenu
from je_file_tree.gui.updates import UpdateNotice

WELCOME_PAGE, RESULTS_PAGE = range(2)
# How often the tree of a running scan is refreshed.
LIVE_REFRESH_MS = 700
_MAX_RECENT = 10
_UNITS = (AUTO_UNIT, *SIZE_UNITS[1:5])
_LISTED_NAMES = 8  # entries named in a Recycle Bin question; the rest are counted
_STATUS_TIMEOUT_MS = 8000
ASK_ADMIN_KEY = "ask_admin_at_start"
EXCLUSIONS_KEY = "exclusions"
SEARCHES_KEY = "saved_searches"
CLEANUP_POLICY_KEY = "cleanup_policy"
SCAN_WORKERS_KEY = "scan_workers"
_MAX_SCAN_WORKERS = 32
_CHART_SETTINGS = ("chart_mode", "treemap_levels", "treemap_colours", "tree_orientation")


def read_flag(settings: QSettings, key: str, default: bool) -> bool:
    """A yes/no setting (the registry keeps them as the strings \"true\" and \"false\")."""
    value = settings.value(key, default)
    return value if isinstance(value, bool) else str(value).lower() == "true"


def read_workers(settings: QSettings) -> int:
    """Validated user-selected concurrency; invalid persisted values retain the existing CPU-bounded default."""
    raw = settings.value(SCAN_WORKERS_KEY, DEFAULT_WORKERS)
    if not isinstance(raw, (int, str)) or isinstance(raw, bool):
        return DEFAULT_WORKERS
    try:
        value = int(raw)
    except (ValueError, TypeError):
        return DEFAULT_WORKERS
    return value if 1 <= value <= _MAX_SCAN_WORKERS else DEFAULT_WORKERS


class MainWindow(QMainWindow):
    """The FileTree window."""

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings if settings is not None else QSettings()
        self._journal = OperationJournal(journal_folder())
        self._worker: ScanWorker | None = None
        self._trash_worker: TrashWorker | None = None
        self._path_dialogs: set[NamespaceDialog | DuplicateLinksDialog | VirtualDisksDialog] = set()
        self._trash_rescans: list[Node] = []
        self._closing = False
        self._analyser: AnalyseWorker | None = None
        self._analysers: set[AnalyseWorker] = set()
        self._exports: set[ExportWorker] = set()
        self._protected = protected_places()  # system and program folders: ask twice before moving them
        self._last_path, self._last_roots = "", ()
        self._unit = str(self.settings.value("unit", AUTO_UNIT))
        if self._unit not in _UNITS:
            self._unit = AUTO_UNIT
        self.welcome = WelcomePage()
        self.results = ResultsView(settings=self.settings)
        self._undo = TrashUndo(self)
        self._bin_labels = BinLabels(self)
        self._bin_labels.ready.connect(self._bin_metadata_ready)
        self._bin_labels.busy_changed.connect(lambda _busy: self._update_bin_buttons())
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
        self._cleanup_policy = CleanupPolicy()
        if self.settings.contains(CLEANUP_POLICY_KEY):
            try:
                self._cleanup_policy = load_policy(self.settings.value(CLEANUP_POLICY_KEY))
            except (ValueError, RecursionError):
                self._cleanup_policy = CleanupPolicy(tuple(RuleSetting(key, False, int(details.minimum_age))
                                                           for key, details in DETAILS.items()))
                self.statusBar().showMessage(tr("policy_saved_invalid"))
        self.results.cleanup.set_policy(self._cleanup_policy)

    @property
    def operation_busy(self) -> bool:
        """Serialize source mutations across Trash, restoration and owned path-operation dialogs."""
        return self._trash_worker is not None or self._undo.busy or bool(self._path_dialogs)

    # --- scanning ---------------------------------------------------------

    def start_scan(self, path: str, *, exact_allocation: bool = False) -> None:
        """Scan ``path`` (stopping a scan already running)."""
        if self.operation_busy or self._path_dialogs:
            return
        self._undo.expire()
        self._trash_rescans.clear()
        path = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
        if not os.path.isdir(path):
            QMessageBox.warning(self, tr("scan_failed_title"), tr("not_a_folder", path=path))
            return
        self._begin_scan(path, exact_allocation=exact_allocation)

    def start_scan_roots(self, paths: tuple[str, ...], *, exact_allocation: bool = False) -> None:
        """Scan an immutable explicit root list; the virtual root never acquires source authority."""
        if self.operation_busy or self._closing or not paths:
            return
        self._begin_scan(tuple(paths), exact_allocation=exact_allocation)

    def scan_all_drives(self) -> None:
        """Capture the currently ready mounted roots once; discovery does not grant mutation authority."""
        self.start_scan_roots(tuple(volume.rootPath() for volume in drives()))

    def choose_roots(self) -> None:
        """Start a combined scan only after accepting an owned explicit-folder list."""
        if self.operation_busy or self._closing:
            return
        dialog = MultiScanDialog(self)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.start_scan_roots(dialog.roots)
        finally:
            dialog.deleteLater()

    def _begin_scan(self, path: str | tuple[str, ...], *, exact_allocation: bool = False) -> None:
        self._undo.expire()
        self._trash_rescans.clear()
        self.stop_scan(wait=True)
        self._bin_labels.stop()
        self._analyser = None
        self._last_roots = path if isinstance(path, tuple) else ()
        self._last_path = path if isinstance(path, str) else ""
        self.path_edit.setText(self._last_path)
        self.path_edit.setToolTip("\n".join(self._last_roots) if self._last_roots else self._last_path)
        worker = ScanWorker(path, self._scan_options(exact_allocation=exact_allocation), self,
                            history=configured_history(self.settings))
        # Signals of a worker that was replaced (a new scan started while it was
        # stopping) arrive late and must not touch the window any more.
        worker.started.connect(lambda root: self._is_current(worker) and self.results.show_live_root(root))
        worker.progressed.connect(
            lambda progress: self._is_current(worker) and self.results.show_progress(progress))
        worker.succeeded.connect(lambda outcome: self._is_current(worker) and self._scan_succeeded(outcome))
        worker.failed.connect(lambda reason: self._is_current(worker) and self._scan_failed(reason))
        worker.cancelled.connect(lambda outcome: self._is_current(worker) and self._scan_cancelled(outcome))
        worker.analysing.connect(lambda: self._is_current(worker) and self.results.scan_bar.analysing())
        worker.history_failed.connect(lambda reason: self._is_current(worker) and not self._closing
                                      and self.statusBar().showMessage(tr("history_save_failed", reason=reason)))
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
            if self._undo.busy:
                self._undo.worker.cancel()
            elif self._trash_worker is not None:
                self._trash_worker.cancel()
            return
        worker.cancel()
        self.results.scan_bar.stopping()
        if wait:
            wait_for(worker)
            self._worker = None
            self._live_timer.stop()

    def _is_current(self, worker: ScanWorker) -> bool:
        return worker is self._worker

    def pause_scan(self, paused: bool) -> None:
        """Pause or resume the current folder scan while live refreshes keep running."""
        if self._worker is not None and not self._worker.set_paused(paused):
            self.results.scan_bar.analysing()

    def rescan(self) -> None:
        """Scan the last folder again."""
        if self._last_roots:
            self.start_scan_roots(self._last_roots)
        elif self._last_path:
            self.start_scan(self._last_path)

    def _scan_succeeded(self, outcome: ScanOutcome) -> None:
        self._scan_ended()
        self.results.show_outcome(outcome)
        self.pages.setCurrentIndex(RESULTS_PAGE)
        root = outcome.result.root
        for source in root.children if root.path is None else (root,):
            if source.snapshot is not None:
                self._remember(source.path)
        self._update_actions()

        if outcome.result.warnings:
            self.statusBar().showMessage(tr("scan_priority_warning", reason="; ".join(outcome.result.warnings)))

    def _scan_failed(self, reason: str) -> None:
        self._scan_ended()
        self._back_from_scan()
        path = tr("multi_roots") if self._last_roots else self._last_path
        QMessageBox.warning(self, tr("scan_failed_title"), tr("scan_failed", path=path, reason=reason))

    def _scan_cancelled(self, outcome: ScanOutcome | None) -> None:
        self._scan_ended()
        if outcome is None:
            self._back_from_scan()
            self.statusBar().showMessage(tr("scan_cancelled"), _STATUS_TIMEOUT_MS)
            return
        self.results.show_outcome(outcome)
        self._update_actions()
        self.statusBar().showMessage(tr("scan_stopped_partial"), _STATUS_TIMEOUT_MS)
        if outcome.result.warnings:
            self.statusBar().showMessage(tr("scan_priority_warning", reason="; ".join(outcome.result.warnings)))

    def _scan_ended(self) -> None:
        self._worker = None
        self._live_timer.stop()
        if self._trash_rescans:
            QTimer.singleShot(0, self._rescan_after_trash)

    def _back_from_scan(self) -> None:
        self.results.end_scan()
        self.pages.setCurrentIndex(RESULTS_PAGE if self.results.outcome is not None else WELCOME_PAGE)
        self._update_actions()

    # --- entry actions ----------------------------------------------------

    def show_menu_for(self, node: Node, picked: Sequence[Node], point: QPoint, *, chart: bool = False) -> None:
        """Pop up the menu of things to do with ``node``; its *Move to Recycle Bin* takes all of ``picked``."""
        if node.path is None:
            self._show_in_chart(node)
            return
        menu = QMenu(self)
        entries: list[tuple[str, Callable[[], object]]] = [
            ("menu_open_item", lambda: file_actions.open_path(node.path)),
            ("menu_reveal", lambda: file_actions.reveal_in_file_manager(node.path)),
            ("menu_copy_path", lambda: file_actions.copy_path(node.path)),
        ]
        if shell_integration.supported():
            entries.append(("menu_properties", lambda: self.show_properties(node)))
        if self.results.archives.busy(node):
            entries.append(("archive_stop", lambda: self.results.archives.stop(node)))
        if node.is_dir and not node.is_link:
            entries.append(("menu_show_chart", lambda: self._show_in_chart(node)))
            entries.append(("menu_rescan_here", lambda: self.rescan_folder(node)))
            entries.append(("menu_scan_here", lambda: self.start_scan(node.path)))
            if (elevation.supported() and self._worker is None and not self.operation_busy
                    and self.results.outcome is not None and self.results.outcome.result.root.path is not None):
                entries.append(("menu_compression", lambda: self.show_compression(node)))
        for key, handler in entries:
            menu.addAction(tr(key)).triggered.connect(handler)
        virtual = self.results.outcome is not None and self.results.outcome.result.root.path is None
        movable = [] if virtual else [entry for entry in _movable(picked) if system_file(entry.path) is None]
        if movable:
            menu.addSeparator()
            if self._worker is None and not self.operation_busy:
                menu.addAction(tr("menu_move_folder")).triggered.connect(lambda: self.show_namespace(picked))
                menu.addAction(tr("menu_rename")).triggered.connect(lambda: self.show_namespace(picked, rename=True))
                if any(entry.is_dir and not entry.is_link for entry in movable):
                    menu.addAction(tr("menu_move_drive")).triggered.connect(lambda: self.show_copy(picked))
            text = tr("action_trash") if len(movable) == 1 else tr("action_trash_many",
                                                                    count=format_count(len(movable)))
            menu.addAction(text).triggered.connect(lambda: self.move_to_trash(movable))
        if chart:
            menu.addSeparator()
            for key in ("export_chart_png", "export_chart_svg"):
                menu.addAction(self._actions[key])
        menu.exec(point)

    def show_properties(self, node: Node) -> None:
        """Open the selected entry's Windows Properties, reporting shell failures."""
        if not shell_integration.show_properties(node.path, int(self.winId())):
            QMessageBox.warning(self, tr("menu_properties"), tr("properties_failed", path=node.path))

    def show_namespace(self, nodes: Sequence[Node], *, rename: bool = False) -> None:
        """Review real selected entries; join operations and refresh the current affected scan scope."""
        outcome = self.results.outcome
        if (outcome is None or self._path_dialogs or self._worker is not None or self.operation_busy
                or not nodes
                or any(node.parent is None or not node.is_in(outcome.result.root) for node in nodes)):
            return
        root = outcome.result.root
        if root.path is None:
            return
        dialog = NamespaceDialog(root, nodes, self._unit, self, rename=rename)
        self._undo.expire()
        self._path_dialogs.add(dialog)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            self._path_dialogs.discard(dialog)
            dialog.deleteLater()
            QTimer.singleShot(0, self._rescan_after_trash)
        if not self._closing and dialog.changed and self.results.outcome is outcome:
            self._analyser = None
            self.results.clear_capacity()
            self._bin_labels.refresh()
            self.rescan_folder(root)

    def show_copy(self, nodes: Sequence[Node]) -> None:
        """Review copied folders, join the copy worker, then use ordinary protected-folder Trash approval."""
        outcome = self.results.outcome
        if (outcome is None or self._path_dialogs or self._worker is not None or self.operation_busy
                or not nodes
                or any(node.parent is None or not node.is_in(outcome.result.root) for node in nodes)):
            return
        root = outcome.result.root
        if root.path is None:
            return
        dialog = CopyDialog(root, nodes, self._unit, self)
        self._undo.expire()
        self._path_dialogs.add(dialog)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            self._path_dialogs.discard(dialog)
            dialog.deleteLater()
            QTimer.singleShot(0, self._rescan_after_trash)
        if self._closing or not dialog.changed or self.results.outcome is not outcome:
            return
        self._analyser = None
        self.results.clear_capacity()
        self._bin_labels.refresh()
        if dialog.finish_requested and dialog.approval is not None:
            self.move_to_trash([proof.item.node for proof in dialog.approval.proofs], copies=dialog.approval)
        if not self.operation_busy:
            self.rescan_folder(root)

    def show_duplicate_links(self, groups: Sequence[DuplicateGroup]) -> None:
        """Serialize reviewed exact-file linking and rebuild the full root after any attempted operation."""
        outcome = self.results.outcome
        panel = self.results.duplicates
        if (outcome is None or self._worker is not None or self.operation_busy or not groups
                or any(group not in panel.link_groups for group in groups)):
            return
        root = outcome.result.root
        if root.path is None:
            return
        if any(group.kept is None or any(not node.is_in(root) for node in group.files) for group in groups):
            return
        panel.stop(wait=True)
        self._undo.expire()
        dialog = DuplicateLinksDialog(root, groups, self._journal, self)
        self._path_dialogs.add(dialog)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            self._path_dialogs.discard(dialog)
            dialog.deleteLater()
            QTimer.singleShot(0, self._rescan_after_trash)
        if not self._closing and dialog.changed and self.results.outcome is outcome:
            self._analyser = None
            self.results.clear_capacity()
            self._bin_labels.refresh()
            self.rescan_folder(root)

    def show_compression(self, node: Node) -> None:
        """Review/confirm scoped native operations, then rescan with per-file allocation if attempted."""
        outcome = self.results.outcome
        if (not elevation.supported() or self._worker is not None or self.operation_busy
                or outcome is None or outcome.result.root.path is None or not node.is_dir or node.is_link
                or not node.is_in(outcome.result.root)):
            return
        dialog = CompressionDialog(node, self._unit, self, partial=outcome.partial)
        dialog.selected.connect(self.results.select_node)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()
        if dialog.changed:
            self.rescan_folder(node, exact_allocation=True)

    def rescan_folder(self, node: Node, *, exact_allocation: bool = False) -> None:
        """Scan one folder again and swap it into the results (the whole scan when it is the root)."""
        if self._worker is not None or self.operation_busy or self.results.outcome is None:
            return
        self._undo.expire()
        if self.results.outcome.result.root.path is None:
            roots = tuple(child.path for child in self.results.outcome.result.root.children)
            self.start_scan_roots(roots, exact_allocation=exact_allocation)
            return
        if self.results.outcome.result.hard_links is not None or self._actions["count_hard_links"].isChecked():
            root = self.results.outcome.result.root
            self._trash_rescans.clear()
            self.start_scan(root.path, exact_allocation=exact_allocation)
            return
        if node.parent is None:
            self.start_scan(node.path, exact_allocation=exact_allocation)
            return
        self._analyser = None
        worker = ScanWorker(node.path, self._scan_options(exact_allocation=exact_allocation), self)
        before = node.size
        worker.progressed.connect(
            lambda progress: self._is_current(worker) and self.results.scan_bar.show_progress(progress))
        worker.succeeded.connect(
            lambda outcome: self._is_current(worker) and self._branch_rescanned(node, outcome, before))
        worker.failed.connect(lambda reason: self._is_current(worker) and self._scan_failed(reason))
        worker.cancelled.connect(lambda _outcome: self._is_current(worker) and self._branch_cancelled())
        worker.analysing.connect(lambda: self._is_current(worker) and self.results.scan_bar.analysing())
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
        root = self.results.tree_model.root
        analyser = AnalyseWorker(root, self, partial=self.results.outcome.partial, with_capacity=True)
        analyser.capacity_ready.connect(lambda ledger: not self._closing and self.results.tree_model.root is root
                                         and self._analyser is analyser and self.results.set_capacity(ledger))
        analyser.done.connect(lambda summary: not self._closing and self._analyser is analyser
                              and self._summary_ready(summary))
        analyser.finished.connect(lambda: self._analysers.discard(analyser))
        analyser.finished.connect(analyser.deleteLater)
        self._analyser = analyser
        self._analysers.add(analyser)
        analyser.start()
        if outcome.result.warnings:
            self.statusBar().showMessage(tr("scan_priority_warning", reason="; ".join(outcome.result.warnings)))

    def _without_managed(self, nodes: list[Node]) -> list[Node]:
        blocked = [node for node in nodes if system_file(node.path) is not None]
        if blocked:
            lines = '\n'.join(f"{node.path}: {tr('trash_skip_system_managed')}" for node in blocked)
            QMessageBox.warning(self, tr('trash_confirm_title'), tr('trash_skipped', names=lines))
        return [node for node in nodes if node not in blocked]

    def _summary_ready(self, summary: Summary) -> None:
        self.results.apply_summary(summary)

    def _branch_cancelled(self) -> None:
        self._scan_ended()
        self.results.scan_bar.hide()
        self._update_actions()
        self.statusBar().showMessage(tr("scan_cancelled"), _STATUS_TIMEOUT_MS)

    def move_to_trash(self, nodes: Sequence[Node], *, copies: CopyApproval | None = None) -> None:
        """Ask once, then move ``nodes`` to the Recycle Bin / Trash and take them out of the results.

        An entry inside another of ``nodes`` goes along with its folder; the scanned folder itself is
        never moved. Entries the system refuses to move stay, and are named in a warning.
        """
        chosen = _movable(nodes)
        root = self.results.tree_model.root
        if (not chosen or root is None or root.path is None or self._worker is not None or self.operation_busy
                or copies is not None and not copies.matches(root, chosen)):
            return
        chosen = self._without_managed(chosen)
        if not chosen:
            return
        reasons = self.results.cleanup.reasons_for(chosen)
        if reasons:
            chosen = self._review_cleanup(chosen, reasons, root)
            if not chosen:
                return
        approvals = {node: protection_of(node.path, self._protected) for node in chosen}
        if not self._confirm_protected(chosen):
            return
        answer = self._confirm_copy_trash(chosen, copies) if copies is not None else QMessageBox.question(
            self, tr("trash_confirm_title"), self._trash_question(chosen))
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self._worker is not None or self.operation_busy or self.results.tree_model.root is not root:
            lines = "\n".join(f"{node.path}: {tr('trash_skip_outside')}" for node in chosen)
            QMessageBox.warning(self, tr("trash_confirm_title"), tr("trash_skipped", names=lines))
            return
        if self.results.duplicates.running:
            self.results.duplicates.stop(wait=True)
        decisions = self.results.duplicates.decisions_for(chosen)
        explanations = {node: f"cleanup:{group.key}" for node, group in reasons.items()}
        explanations.update((node, "duplicates") for group in decisions for node in group.files if node in chosen)
        audit = JournalApproval(self._journal, explanations)
        worker = TrashWorker(root, chosen, self._protected, approvals, self, decisions=decisions, audit=audit)
        if copies is not None:
            worker.copy_approval = CopyApproval(tuple(proof for proof in copies.proofs if proof.item.node in chosen),
                                                copies.redirect)
        self._undo.expire()
        worker.allow_undo = True
        worker.done.connect(self._trash_finished)
        worker.finished.connect(worker.deleteLater)
        self._trash_worker = worker
        self.results.setEnabled(False)
        self._update_actions()
        self.statusBar().showMessage(tr("trash_running"))
        worker.start()

    def _confirm_copy_trash(self, nodes: list[Node], copies: CopyApproval) -> QMessageBox.StandardButton:
        question = QMessageBox(QMessageBox.Icon.Question, tr("trash_confirm_title"), "",
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        question.setTextFormat(Qt.TextFormat.PlainText)
        question.setText(self._trash_question(nodes) + "\n\n" + tr("copy_trash_confirm")
                         + ("\n\n" + tr("copy_redirect") if copies.redirect else ""))
        question.setDetailedText("\n\n".join(f"{proof.item.source}\n→ {proof.item.destination}"
                                            for proof in copies.proofs if proof.item.node in nodes))
        question.setDefaultButton(QMessageBox.StandardButton.No)
        return question.exec()

    def _review_cleanup(self, nodes: list[Node], reasons: dict[Node, CleanupGroup], root: Node) -> list[Node]:
        dialog = CleanupReview(nodes, reasons, self._protected, self._unit, root, self)
        try:
            return dialog.selected_nodes() if dialog.exec() == QDialog.DialogCode.Accepted else []
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def _trash_finished(self, result: MoveResult) -> None:
        worker = self._trash_worker
        if worker is not None:
            wait_for(worker)
        self._trash_worker = None
        self.refresh_bin_labels()
        if self._closing:
            return
        self.results.setEnabled(True)
        self._update_actions()
        moved, failed = result.moved, result.failed
        moved_size = format_size(sum(node.size for node in moved), self._unit)
        if moved:
            self._analyser = None
            if self.results.outcome is None or self.results.outcome.result.hard_links is None:
                self.results.forget(moved)
        if failed:
            message = (tr("trash_failed", name=failed[0].name) if len(failed) == 1 else
                       tr("trash_failed_many", count=format_count(len(failed)), names=self._name_lines(failed)))
            QMessageBox.warning(self, tr("trash_confirm_title"), message + self._holder_lines(result))
        if result.skipped:
            lines = [f"{node.path}: {tr(f'trash_skip_{reason}')}" for node, reason in result.skipped]
            QMessageBox.warning(self, tr("trash_confirm_title"), tr("trash_skipped", names="\n".join(lines)))
        if result.journal_errors:
            QMessageBox.warning(self, tr("action_recent_actions"),
                                tr("journal_write_failed", reason="\n".join(result.journal_errors)))
        self._report_copy_errors(result)
        done = tr("trash_batch_done", moved=format_count(len(moved)), skipped=format_count(len(result.skipped)),
                  failed=format_count(len(failed)), size=moved_size)
        unavailable = self._undo.offer(worker)
        self.statusBar().showMessage(done + ("\n" + unavailable if unavailable else ""), _STATUS_TIMEOUT_MS)
        self._trash_rescans = outermost(result.parents)
        QTimer.singleShot(0, self._rescan_after_trash)

    def _report_copy_errors(self, result: MoveResult | None) -> None:
        if result is not None and result.copy_errors:
            report = QMessageBox(QMessageBox.Icon.Warning, tr("menu_move_drive"), "",
                                 QMessageBox.StandardButton.Ok, self)
            report.setTextFormat(Qt.TextFormat.PlainText)
            report.setText(tr("copy_errors"))
            report.setDetailedText("\n\n".join(
                tr("copy_" + phase + "_failed", source=source, destination=destination, reason=reason)
                for source, destination, phase, reason in result.copy_errors))
            report.exec()

    def _holder_lines(self, result: MoveResult) -> str:
        lines = []
        for node, report in result.holders.items():
            if report.holders:
                names = ", ".join(tr("trash_holder", name=holder.name, pid=str(holder.pid))
                                  for holder in report.holders[:_LISTED_NAMES])
                lines.append(tr("trash_holders", path=node.path, programs=names))
            if report.incomplete or report.error:
                lines.append(tr("trash_holders_limited", path=node.path))
        return "\n\n" + "\n".join(lines) if lines else ""

    def _rescan_after_trash(self) -> None:
        if (self._closing or self.operation_busy or self._worker is not None
                or self._undo.available or not self._trash_rescans):
            return
        node = self._trash_rescans.pop(0)
        root = self.results.tree_model.root
        if root is not None and node.is_in(root):
            self.rescan_folder(node)
        if self._worker is None and self._trash_rescans:
            QTimer.singleShot(0, self._rescan_after_trash)

    def _confirm_protected(self, nodes: list[Node]) -> bool:
        """The first of two questions when system or program folders are among ``nodes``: True to go on."""
        guarded = [(node, found) for node in nodes if (found := protection_of(node.path, self._protected)) is not None]
        if not guarded:
            return True
        lines = [f"• {node.path} — {tr(f'protected_{found.reason}')}" for node, found in guarded[:_LISTED_NAMES]]
        if len(guarded) > _LISTED_NAMES:
            lines.append(tr("trash_more", count=format_count(len(guarded) - _LISTED_NAMES)))
        question = tr("protected_question", count=format_count(len(guarded)), names="\n".join(lines))
        answer = QMessageBox.warning(self, tr("protected_title"), question,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _trash_question(self, nodes: list[Node]) -> str:
        size = format_size(sum(node.size for node in nodes), self._unit)
        if len(nodes) == 1:
            return tr("trash_confirm", name=nodes[0].name, size=size)
        return tr("trash_confirm_many", count=format_count(len(nodes)), size=size, names=self._name_lines(nodes))

    def _name_lines(self, nodes: list[Node]) -> str:
        """The biggest of ``nodes`` one per line with their sizes, then how many more there are."""
        ordered = sorted(nodes, key=lambda node: node.size, reverse=True)
        lines = [f"• {node.name} ({format_size(node.size, self._unit)})" for node in ordered[:_LISTED_NAMES]]
        if len(ordered) > _LISTED_NAMES:
            lines.append(tr("trash_more", count=format_count(len(ordered) - _LISTED_NAMES)))
        return "\n".join(lines)

    def _show_in_chart(self, node: Node) -> None:
        self.results.charts.set_view_root(node)
        self.results.tabs.setCurrentIndex(CHART_TAB)

    def _find(self) -> None:
        if self.pages.currentIndex() == RESULTS_PAGE and self.results.outcome is not None:
            self.results.show_search()

    def _trash_selected(self) -> None:
        if self.pages.currentIndex() == RESULTS_PAGE:
            self.move_to_trash(self.results.focused_selection())

    def _selection_changed(self, node: Node | None) -> None:
        picked = self.results.selected_nodes()
        if len(picked) > 1:
            size = format_size(sum(entry.size for entry in outermost(picked)), self._unit)
            self.statusBar().showMessage(tr("status_selected_many", count=format_count(len(picked)), size=size))
            return
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

    def export_report(self, kind: str) -> None:
        """Export a bounded whole-scan HTML or Excel report through an owned cancellable modal worker."""
        outcome = self.results.outcome
        if outcome is None or self._worker is not None or self.operation_busy or self._analysers:
            return
        target, _ = QFileDialog.getSaveFileName(self, tr("action_export_report_" + kind),
                                                f"report.{kind}", tr(kind + "_filter"))
        if not target:
            return
        try:
            dialog = ReportDialog(outcome, kind, target, self._unit, self.results.charts, self)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, tr("export_title"), tr("export_failed", reason=str(error)))
            return
        try:
            dialog.exec()
            if dialog.saved:
                self.settings.setValue("export_dir", os.path.dirname(target))
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def export_list(self) -> None:
        """Stream the active list in displayed order to CSV using bounded GUI capture and ExportWorker."""
        view = self.results.current_list()
        if view is None or self.results.outcome is None:
            return
        target, _ = QFileDialog.getSaveFileName(self, tr('action_export_list'), 'list.csv', tr('csv_filter'))
        if not target:
            return
        stream = ListStream()
        capture = ListCapture(view, self, stream=stream)
        self._captures.add(capture)
        capture.finished.connect(lambda: self._captures.discard(capture))
        capture.finished.connect(capture.deleteLater)
        worker = ExportWorker(lambda: export.export_table_csv(capture.header, stream.rows(), target), self)
        worker.done.connect(lambda count: self._export_done(target, count))
        worker.failed.connect(lambda reason: self._list_export_failed(capture, reason))
        worker.finished.connect(capture.cancel)
        worker.finished.connect(lambda: self._exports.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._exports.add(worker)
        self.statusBar().showMessage(tr('export_running', path=target))
        worker.start()
        capture.start()

    def _list_export_failed(self, capture: ListCapture, reason: str) -> None:
        capture.cancel()
        if not self._closing:
            QMessageBox.warning(self, tr('export_title'), tr('export_failed', reason=reason))

    def print_current_view(self) -> None:
        """Offer the system print dialog for one page containing the visible results."""
        if self.results.outcome is None or self._worker is not None or self.operation_busy:
            return
        image = self.results.grab().toImage()
        printer = view_printer(image)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            print_view(image, printer)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, tr("action_print_view"), tr("print_failed", reason=str(error)))
            return
        self.statusBar().showMessage(tr("print_submitted"), _STATUS_TIMEOUT_MS)

    def export_view_pdf(self) -> None:
        """Export captured results through Qt's PDF engine on an atomic-writing worker."""
        if self.results.outcome is None or self._worker is not None or self.operation_busy:
            return
        target, _ = QFileDialog.getSaveFileName(self, tr("action_export_view_pdf"), "view.pdf", tr("pdf_filter"))
        if not target:
            return
        image = self.results.grab().toImage()
        worker = ExportWorker(lambda: save_view_pdf(image, target), self)
        worker.done.connect(lambda _count: self.statusBar().showMessage(tr("view_pdf_exported", path=target)))
        worker.failed.connect(lambda reason: QMessageBox.warning(self, tr("export_title"),
                                                                 tr("export_failed", reason=reason)))
        worker.finished.connect(lambda: self._exports.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._exports.add(worker)
        worker.start()

    def export_chart(self, kind: str) -> None:
        """Capture the visible chart as PNG, or full bounded bars/rings as vector SVG."""
        if self.results.outcome is None or self._worker is not None or self.operation_busy:
            return
        charts = self.results.charts
        if kind == "svg" and charts.mode not in SVG_MODES:
            return
        target, _ = QFileDialog.getSaveFileName(self, tr("action_export_chart_" + kind),
                                                f"chart.{kind}", tr(kind + "_filter"))
        if not target:
            return
        try:
            graphic = capture_svg(charts) if kind == "svg" else charts.currentWidget().grab().toImage()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, tr("export_title"), tr("export_failed", reason=str(error)))
            return
        worker = ExportWorker(lambda: save_graphic(target, graphic), self)
        worker.done.connect(lambda _count: self.statusBar().showMessage(tr("graphic_exported", path=target)))
        worker.failed.connect(lambda reason: QMessageBox.warning(self, tr("export_title"),
                                                                 tr("export_failed", reason=reason)))
        worker.finished.connect(lambda: self._exports.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._exports.add(worker)
        worker.start()

    def export_results(self, kind: str) -> None:
        """Save the results: ``"folders"`` or ``"largest"`` as CSV, ``"json"`` as JSON."""
        outcome = self.results.outcome
        if outcome is None:
            return
        is_json = kind == "json"
        name = outcome.result.root.name or tr("multi_roots")
        suggested = f"{_safe_name(name)}-{kind}.{'json' if is_json else 'csv'}"
        start = os.path.join(str(self.settings.value("export_dir", os.path.expanduser("~"))), suggested)
        target, _ = QFileDialog.getSaveFileName(self, tr("export_title"), start,
                                                tr("json_filter") if is_json else tr("csv_filter"))
        if not target:
            return
        root = outcome.result.root
        largest = self.results.largest_model.rows()
        writers: dict[str, Callable[[], int]] = {
            "folders": lambda: export.export_folders_csv(root, target),
            "largest": lambda: export.export_files_csv(largest, target),
            "json": lambda: _write_json(root, target),
        }
        worker = ExportWorker(writers[kind], self)
        worker.done.connect(lambda count: self._export_done(target, count))
        worker.failed.connect(lambda reason: QMessageBox.warning(self, tr("export_title"),
                                                                 tr("export_failed", reason=reason)))
        worker.finished.connect(lambda: self._exports.discard(worker))
        worker.finished.connect(worker.deleteLater)
        self._exports.add(worker)
        self.statusBar().showMessage(tr("export_running", path=target))
        worker.start()

    def _export_done(self, target: str, count: int) -> None:
        self.settings.setValue("export_dir", os.path.dirname(target))
        self.statusBar().showMessage(tr("export_done", count=count, path=target), _STATUS_TIMEOUT_MS)

    # --- settings, language, units ----------------------------------------

    def set_unit(self, unit: str) -> None:
        """Show sizes in ``unit`` and remember it."""
        self._unit = unit
        self.settings.setValue("unit", unit)
        self.results.set_unit(unit)
        self.welcome.set_unit(unit)
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
        self.theme_menu.retranslate()
        self._undo.retranslate()
        self._updates.retranslate()
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
        self._actions["gentle"].setChecked(read_flag(self.settings, "gentle_scan", False))
        with QSignalBlocker(self._actions["check_updates"]):
            self._actions["check_updates"].setChecked(self._updates.enabled())
        self._actions["capture_file_times"].setChecked(read_flag(self.settings, "capture_file_times", False))
        self._actions["capture_owners"].setChecked(read_flag(self.settings, "capture_owners", False))
        self._actions["exact_allocation"].setChecked(read_flag(self.settings, "exact_allocation", False))
        self._actions["count_hard_links"].setChecked(read_flag(self.settings, "count_hard_links", False))
        self._unit_actions[self._unit].setChecked(True)
        self.results.set_unit(self._unit)
        self.welcome.set_unit(self._unit)
        self.welcome.set_recent(self._recent())

    def closeEvent(self, event: QCloseEvent) -> None:
        """Qt: stop the scan and remember the window layout."""
        self._trash_rescans.clear()
        self._closing = True
        self._updates.shutdown()
        self._undo.shutdown()
        for dialog in self._path_dialogs.copy():
            dialog.reject()
        self._bin_labels.shutdown()
        if self._trash_worker is not None:
            worker = self._trash_worker
            worker.cancel()
            wait_for(worker)
            self._trash_worker = None
            self._report_copy_errors(worker.result)
        self.stop_scan(wait=True)
        self.results.search.stop(wait=True)
        self.results.duplicates.stop(wait=True)
        self.results.cleanup.stop(wait=True)
        self.results.users.stop(wait=True)
        self.results.changes.stop(wait=True)
        self.results.details.stop(wait=True)
        self.results.wait_for_lists()
        for capture in self._captures.copy():
            capture.cancel()
        for worker in self._analysers.copy():
            wait_for(worker)
        for worker in self._exports.copy():  # a file being written is finished, never left half-written
            wait_for(worker)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.results.splitter.saveState())
        self.settings.setValue("include_hidden", self._actions["hidden"].isChecked())
        super().closeEvent(event)

    # --- drag and drop ----------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Qt: accept a folder reference as Copy so the source must keep its files."""
        if event.possibleActions() & Qt.DropAction.CopyAction and _dropped_folder(event.mimeData().urls()) is not None:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Qt: scan a copied folder reference, never acknowledge a source-removing Move."""
        folder = _dropped_folder(event.mimeData().urls())
        if folder is not None and event.possibleActions() & Qt.DropAction.CopyAction:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self.start_scan(folder)
        else:
            event.ignore()

    # --- building ---------------------------------------------------------

    def _build_actions(self) -> None:
        self._updates = UpdateNotice(self.settings, self)
        self._captures: set[ListCapture] = set()
        definitions: list[tuple[str, QKeySequence | str | None, Callable[[], object]]] = [
            ("open", QKeySequence.StandardKey.Open, self.choose_folder),
            ("multi_scan", None, self.choose_roots),
            ("rescan", QKeySequence.StandardKey.Refresh, self.rescan),
            ("stop", "Esc", self.stop_scan),
            ("export_folders", None, lambda: self.export_results("folders")),
            ("export_largest", None, lambda: self.export_results("largest")),
            ("export_list", None, self.export_list),
            ("export_json", None, lambda: self.export_results("json")),
            ("export_chart_png", None, lambda: self.export_chart("png")),
            ("export_chart_svg", None, lambda: self.export_chart("svg")),
            ("print_view", QKeySequence.StandardKey.Print, self.print_current_view),
            ("export_view_pdf", None, self.export_view_pdf),
            ("export_report_html", None, lambda: self.export_report("html")),
            ("export_report_xlsx", None, lambda: self.export_report("xlsx")),
            ("trash", QKeySequence.StandardKey.Delete, self._trash_selected),
            ("find", QKeySequence.StandardKey.Find, self._find),
            ("compare", None, self.choose_saved_scan),
            ("recent_actions", None, self.show_recent_actions),
            ("special_files", None, self.show_special_files),
            ("live_compare", None, self.compare_live_folders),
            ("git_history", None, self.show_git_history),
            ("history", None, self.show_history),
            ("history_settings", None, self.configure_history),
            ("projects", None, self.show_projects),
            ("programs", None, self.show_programs),
            ("virtual_disks", None, self.show_virtual_disks),
            ("file_times", None, self.show_file_times),
            ("capture_file_times", None, lambda: None),
            ("capture_owners", None, lambda: None),
            ("exact_allocation", None, lambda: None),
            ("count_hard_links", None, lambda: None),
            ("volumes", None, self.show_volumes),
            ("bins", None, self.show_bins),
            ("quit", "Ctrl+Q", self.close),  # Windows has no standard Quit key
            ("hidden", None, lambda: self.settings.setValue("include_hidden", self._actions["hidden"].isChecked())),
            ("elevate", None, self.restart_as_admin),
            ("exclusions", None, self.edit_exclusions),
            ("cleanup_policy", None, self.edit_cleanup_policy),
            ("shell_integration", None, self.edit_shell_integration),
            ("gentle", None, lambda: self.settings.setValue("gentle_scan", self._actions["gentle"].isChecked())),
            ("scan_workers", None, self.configure_workers),
            ("ask_admin", None, lambda: self.settings.setValue(ASK_ADMIN_KEY, self._actions["ask_admin"].isChecked())),
            ("help", QKeySequence.StandardKey.HelpContents, self.show_help),
            ("about", None, self.show_about),
            ("check_updates", None, lambda: None),
        ]
        for key, shortcut, handler in definitions:
            action = QAction(self)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda _checked=False, run=handler: run())
            self._actions[key] = action
        self._actions["check_updates"].setCheckable(True)
        self._actions["check_updates"].toggled.connect(self._updates.configure)
        self._actions["hidden"].setCheckable(True)
        self._actions["ask_admin"].setCheckable(True)
        self._actions["gentle"].setCheckable(True)
        self._actions["capture_file_times"].setCheckable(True)
        self._actions["capture_file_times"].toggled.connect(
            lambda checked: self.settings.setValue("capture_file_times", checked))
        self._actions["capture_owners"].setCheckable(True)
        self._actions["capture_owners"].setVisible(elevation.supported())
        self._actions["capture_owners"].toggled.connect(
            lambda checked: self.settings.setValue("capture_owners", checked))
        self._actions["exact_allocation"].setCheckable(True)
        self._actions["exact_allocation"].setVisible(elevation.supported())
        self._actions["exact_allocation"].toggled.connect(
            lambda checked: self.settings.setValue("exact_allocation", checked))
        self._actions["count_hard_links"].setCheckable(True)
        self._actions["count_hard_links"].toggled.connect(
            lambda checked: self.settings.setValue("count_hard_links", checked))
        self._actions["elevate"].setVisible(elevation.can_elevate())
        self._actions["ask_admin"].setVisible(elevation.supported())
        self._actions["shell_integration"].setVisible(shell_integration.supported())
        self._actions["programs"].setVisible(elevation.supported())

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("")
        for key in ("open", "multi_scan", "rescan", "stop", "find"):
            file_menu.addAction(self._actions[key])
        export_menu = file_menu.addMenu("")
        for key in ("export_folders", "export_largest", "export_json", "export_chart_png", "export_chart_svg"):
            export_menu.addAction(self._actions[key])
        export_menu.addAction(self._actions["export_view_pdf"])
        export_menu.addAction(self._actions["export_list"])
        for key in ("export_report_html", "export_report_xlsx"):
            export_menu.addAction(self._actions[key])
        file_menu.addAction(self._actions["print_view"])
        file_menu.addAction(self._actions["compare"])
        for key in ("recent_actions", "special_files", "live_compare", "git_history", "projects", "history",
                    "programs", "virtual_disks", "file_times"):
            file_menu.addAction(self._actions[key])
        file_menu.addSeparator()
        file_menu.addAction(self._actions["trash"])
        file_menu.addAction(self._actions["elevate"])
        file_menu.addSeparator()
        file_menu.addAction(self._actions["quit"])
        view_menu = bar.addMenu("")
        view_menu.addAction(self._actions["volumes"])
        view_menu.addAction(self._actions["bins"])
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
        self.theme_menu = ThemeMenu(view_menu, self.settings)
        view_menu.addAction(self._actions["hidden"])
        view_menu.addAction(self._actions["exclusions"])
        view_menu.addAction(self._actions["ask_admin"])
        options_menu = bar.addMenu("")
        options_menu.addAction(self._actions["cleanup_policy"])
        options_menu.addAction(self._actions["gentle"])
        options_menu.addAction(self._actions["scan_workers"])
        options_menu.addAction(self._actions["history_settings"])
        options_menu.addAction(self._actions["check_updates"])
        for key in ("capture_file_times", "capture_owners", "exact_allocation", "count_hard_links"):
            options_menu.addAction(self._actions[key])
        options_menu.addAction(self._actions["shell_integration"])
        help_menu = bar.addMenu("")
        help_menu.addAction(self._actions["help"])
        help_menu.addAction(self._actions["about"])
        self._menus = {"menu_file": file_menu, "menu_export": export_menu, "menu_view": view_menu,
                       "menu_unit": unit_menu, "menu_language": language_menu, "menu_help": help_menu,
                       "menu_options": options_menu}

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
        self.results.duplicates.link_requested.connect(self.show_duplicate_links)
        self.results.cleanup.review_requested.connect(self.move_to_trash)
        self.welcome.choose_folder_requested.connect(self.choose_folder)
        self.welcome.scan_requested.connect(self.start_scan)
        self.welcome.scan_all_requested.connect(self.scan_all_drives)
        self.welcome.overview_requested.connect(self.show_volumes)
        self.welcome.bins_requested.connect(self.show_bins)
        self.welcome.bin_refresh_requested.connect(self.refresh_bin_labels)
        self.results.cleanup.bin_refresh_requested.connect(self.refresh_bin_labels)
        self.results.cleanup.bins_requested.connect(self.show_bins)
        self.results.scan_bar.stop_requested.connect(self.stop_scan)
        self.results.scan_bar.pause_requested.connect(self.pause_scan)
        self.results.node_menu_requested.connect(self.show_menu_for)
        self.results.chart_menu_requested.connect(lambda node, picked, point:
                                                  self.show_menu_for(node, picked, point, chart=True))
        self.results.apply_chart_settings({key: self.settings.value(key) for key in _CHART_SETTINGS
                                           if self.settings.contains(key)})
        self.results.chart_setting_changed.connect(self.settings.setValue)
        self.results.search.set_saved(_saved_searches(self.settings))
        self.results.search.saved_changed.connect(
            lambda searches: self.settings.setValue(SEARCHES_KEY, json.dumps(searches, ensure_ascii=False)))
        self.results.compare_failed.connect(
            lambda reason: QMessageBox.warning(self, tr("compare_title"), tr("compare_failed", reason=reason)))
        self.results.selection_changed.connect(self._selection_changed)
        self.results.charts.mode_changed.connect(lambda _mode: self._update_actions())
        self.results.tabs.currentChanged.connect(lambda _tab: self._update_actions())
        self.results.elevate_requested.connect(self.restart_as_admin)

    def _update_actions(self) -> None:
        scanning = self._worker is not None or self.operation_busy
        has_results = self.results.outcome is not None
        self._actions["stop"].setEnabled(scanning)
        self._actions["open"].setEnabled(not self.operation_busy)
        self._actions["cleanup_policy"].setEnabled(not scanning)
        self._actions["live_compare"].setEnabled(not scanning)
        self._actions["volumes"].setEnabled(not scanning)
        self._actions["bins"].setEnabled(not scanning)
        self._actions["rescan"].setEnabled(bool(self._last_path or self._last_roots) and not scanning)
        for key in ("export_folders", "export_largest", "export_json", "export_chart_png", "trash", "find", "compare"):
            self._actions[key].setEnabled(has_results and not scanning)
        self._actions["export_chart_svg"].setEnabled(has_results and not scanning
                                                    and self.results.charts.mode in SVG_MODES)
        for key in ("print_view", "export_view_pdf", "special_files", "git_history", "projects", "history",
                    "programs", "virtual_disks", "file_times"):
            self._actions[key].setEnabled(has_results and not scanning)
        for key in ("export_report_html", "export_report_xlsx"):
            self._actions[key].setEnabled(has_results and not scanning and not self.operation_busy
                                          and not self._analysers)
        self._actions['export_list'].setEnabled(has_results and not scanning
                                              and self.results.current_list() is not None)
        virtual = has_results and self.results.outcome.result.root.path is None
        for key in ("trash", "history", "git_history"):
            self._actions[key].setEnabled(has_results and not scanning and not virtual)
        self._actions["multi_scan"].setEnabled(not self.operation_busy)
        self.welcome.scan_all.setEnabled(not scanning and bool(drives()))
        self._update_bin_buttons()

    def _update_bin_buttons(self) -> None:
        idle = (not self._closing and not self._bin_labels.busy
                and self._worker is None and not self.operation_busy)
        self.welcome.bin_refresh.setEnabled(idle)
        self.results.cleanup.bin_refresh.setEnabled(idle and self.results.outcome is not None)

    def refresh_bin_labels(self) -> None:
        """Refresh read-only drive totals off the GUI thread, retaining the current scan's scope."""
        if self._closing or self._worker is not None or self.operation_busy:
            return
        outcome = self.results.outcome
        self._bin_labels.refresh((outcome.result.root.path or "") if outcome is not None else "")

    def _bin_metadata_ready(self, rows: dict[str, TrashUsage], root: str) -> None:
        self.welcome.set_bin_metadata(rows)
        if self.results.outcome is not None:
            self.results.cleanup.set_bin_metadata(root, rows.get(bin_key(root)) if root else None)

    # --- dialogs ----------------------------------------------------------

    def show_virtual_disks(self) -> None:
        """Own virtual-disk reviews and rebuild the full captured root after attempted compaction."""
        if self._worker is not None or self.operation_busy or self.results.outcome is None:
            return
        outcome = self.results.outcome
        dialog = VirtualDisksDialog(outcome.result.root, self._unit, self, partial=outcome.partial,
                                    journal=self._journal if outcome.result.root.path is not None else None)
        dialog.selected.connect(self.results.select_node)
        dialog.execution_requested.connect(self._undo.expire)
        self._path_dialogs.add(dialog)
        self._update_actions()
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            self._path_dialogs.discard(dialog)
            dialog.deleteLater()
            self._update_actions()
        if not self._closing and dialog.changed and self.results.outcome is outcome:
            self._analyser = None
            self.results.clear_capacity()
            self._bin_labels.refresh()
            self.rescan_folder(outcome.result.root)
        elif self._trash_rescans:
            self._process_trash_rescans()

    def show_programs(self) -> None:
        """Review Windows registrations/game names against the current recorded tree on an owned worker."""
        if (not elevation.supported() or self._worker is not None or self.operation_busy
                or self.results.outcome is None):
            return
        outcome = self.results.outcome
        dialog = ProgramsDialog(outcome.result.root, self._unit, self, partial=outcome.partial)
        dialog.selected.connect(self.results.select_node)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def configure_history(self) -> None:
        """Persist enable/cap changes only after OK; the running scan retains its captured configuration."""
        dialog = HistorySettings(self.settings, self)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.settings.setValue("history_enabled", dialog.enabled.isChecked())
                self.settings.setValue("history_limit_mib", dialog.limit.value())
        finally:
            dialog.deleteLater()

    def show_file_times(self) -> None:
        """Query optional recorded file dates on an owned worker, without opening scanned payloads."""
        if self._worker is not None or self.operation_busy or self.results.outcome is None:
            return
        outcome = self.results.outcome
        dialog = FileTimesDialog(outcome.result.root, self._unit, partial=outcome.partial, parent=self)
        dialog.selected.connect(self.results.select_node)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def show_history(self) -> None:
        """Review local history for the full current root and reuse the Changes worker for comparison."""
        if self._worker is not None or self.operation_busy or self.results.outcome is None:
            return
        root = self.results.outcome.result.root
        if root.path is None:
            return
        store = ScanHistory(history_folder(), max_bytes=history_limit(self.settings) * 1024 * 1024)
        dialog = HistoryDialog(store, root.path, self._unit, self)
        dialog.compare_requested.connect(self.results.compare_saved)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def show_bins(self) -> None:
        """Review OS bin metadata and exact-scope emptying after two explicit questions."""
        if self._worker is not None or self.operation_busy:
            return
        dialog = BinDialog(self._unit, self)
        dialog.scan_requested.connect(self.start_scan)
        dialog.emptied.connect(self._bin_emptied)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()
            self.refresh_bin_labels()

    def _bin_emptied(self, _root: str) -> None:
        self._analyser = None
        self.results.clear_capacity()

    def show_volumes(self) -> None:
        """Show mounted volumes and scan an explicitly activated root."""
        if self._worker is not None or self.operation_busy:
            return
        dialog = VolumesDialog(self._unit, self)
        dialog.scan_requested.connect(self.start_scan)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

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

    def edit_exclusions(self) -> None:
        """Edit the folders to skip while scanning; they apply from the next scan."""
        dialog = ExclusionsDialog(self.exclusions(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.settings.setValue(EXCLUSIONS_KEY, dialog.patterns())
        self.statusBar().showMessage(tr("exclusions_saved", count=format_count(len(dialog.patterns()))),
                                     _STATUS_TIMEOUT_MS)

    def edit_cleanup_policy(self) -> None:
        """Preview and save clean-up settings independently of scan exclusions."""
        if self._worker is not None or self.operation_busy:
            return
        dialog = CleanupPolicyDialog(self._cleanup_policy, self.results.tree_model.root, self._unit, self)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._cleanup_policy = dialog.policy()
                self.settings.setValue(CLEANUP_POLICY_KEY, self._cleanup_policy.dumps())
                self.results.cleanup.set_policy(self._cleanup_policy)
                self.statusBar().showMessage(tr("policy_saved"), _STATUS_TIMEOUT_MS)
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def edit_shell_integration(self) -> None:
        """Open explicit Explorer settings; cancel leaves the registry untouched."""
        if shell_integration.supported():
            dialog = ShellIntegrationDialog(self)
            dialog.exec()
            dialog.deleteLater()

    def show_special_files(self) -> None:
        """Explain cloud and special file metadata without reading or downloading any contents."""
        outcome = self.results.outcome
        if outcome is None or self._worker is not None or self.operation_busy:
            return
        dialog = SpecialFilesDialog(outcome.result.root, self._unit,
                                    partial=outcome.partial or bool(outcome.result.errors), parent=self)
        dialog.selected.connect(self.results.select_node)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def compare_live_folders(self) -> None:
        """Choose two existing folders for an independent read-only comparison."""
        if self._worker is not None or self.operation_busy:
            return
        left = QFileDialog.getExistingDirectory(self, tr("compare_choose_left"), self._last_path or "")
        if not left:
            return
        right = QFileDialog.getExistingDirectory(self, tr("compare_choose_right"), left)
        if not right:
            return
        dialog = LiveCompareDialog((left, right), self._unit, self)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def show_git_history(self) -> None:
        """Inspect the selected working folder's largest reachable Git history objects."""
        outcome = self.results.outcome
        if outcome is None or self._worker is not None or self.operation_busy:
            return
        node = self.results.selected_node() or outcome.result.root
        folder = node if node.is_dir else node.parent
        if folder is None or folder.path is None or folder.is_link:
            return
        if folder.name == ".git" and folder.parent is not None:
            folder = folder.parent
        dialog = GitHistoryDialog(folder.path, self._unit, self)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def show_projects(self) -> None:
        """Explain recorded project/generated bytes and review only current-policy eligible entries."""
        outcome = self.results.outcome
        if outcome is None or self._worker is not None or self.operation_busy:
            return
        dialog = ProjectsDialog(outcome.result.root, self._unit, self._cleanup_policy,
                                partial=outcome.partial, parent=self)
        dialog.selected.connect(self.results.select_node)
        dialog.review_requested.connect(self.move_to_trash)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def exclusions(self) -> list[str]:
        """The folder name patterns and folder paths that scans skip (the ``exclusions`` setting)."""
        value = self.settings.value(EXCLUSIONS_KEY, [])
        if isinstance(value, str):  # an INI file keeps a one-item list as a plain string
            return [value] if value else []
        return [str(pattern) for pattern in value or []]

    def _scan_options(self, *, exact_allocation: bool = False) -> ScanOptions:
        return ScanOptions(include_hidden=self._actions["hidden"].isChecked(), exclude=tuple(self.exclusions()),
                           gentle=self._actions["gentle"].isChecked(), workers=read_workers(self.settings),
                           file_times=self._actions["capture_file_times"].isChecked(),
                           windows_owners=self._actions["capture_owners"].isChecked(),
                           exact_windows_allocation=exact_allocation or self._actions["exact_allocation"].isChecked(),
                           count_hard_links=self._actions["count_hard_links"].isChecked())

    def configure_workers(self) -> None:
        """Persist bounded concurrency for new scans and branch rescans, leaving running workers alone."""
        value, accepted = QInputDialog.getInt(self, tr("action_scan_workers"),
                                             tr("workers_prompt", default=DEFAULT_WORKERS),
                                             read_workers(self.settings), 1, _MAX_SCAN_WORKERS, 1)
        if accepted:
            self.settings.setValue(SCAN_WORKERS_KEY, value)

    def choose_saved_scan(self) -> None:
        """Ask for a saved scan (a Folder tree JSON export) and compare the scan on screen with it."""
        if self.results.outcome is None or self._worker is not None:
            return
        start = str(self.settings.value("export_dir", os.path.expanduser("~")))
        file, _ = QFileDialog.getOpenFileName(self, tr("compare_title"), start, tr("json_filter"))
        if file:
            self.results.compare_with(file)

    def show_help(self) -> None:
        """Open the how-to-use window."""
        HelpDialog(self).exec()

    def show_recent_actions(self) -> None:
        """Open the retained metadata trail, without proposing or restoring any entry."""
        dialog = RecentActions(self._journal, self)
        try:
            dialog.exec()
        finally:
            dialog.shutdown()
            dialog.deleteLater()

    def show_about(self) -> None:
        """Show the version."""
        QMessageBox.about(self, tr("action_about"), tr("about_text", version=__version__))


def _dropped_folder(urls: list) -> str | None:
    for url in urls:
        if url.isLocalFile() and os.path.isdir(url.toLocalFile()):
            return os.path.normpath(url.toLocalFile())
    return None


def _write_json(root: Node, target: str) -> int:
    """Write the folder tree as JSON; returns the number of folders written."""
    export.export_json(root, target)
    return root.dir_count + 1


def _saved_searches(settings: QSettings) -> dict[str, object]:
    """The saved searches kept in the settings as JSON; anything unreadable counts as none."""
    try:
        searches = json.loads(str(settings.value(SEARCHES_KEY, "{}")))
    except ValueError:
        return {}
    return searches if isinstance(searches, dict) else {}


def _movable(nodes: Sequence[Node]) -> list[Node]:
    """What moving ``nodes`` to the Recycle Bin really moves: the outermost entries, never the scanned folder."""
    return outermost(node for node in nodes if node.parent is not None)


def _safe_name(name: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "-_" else "_" for character in name)
    return cleaned.strip("_") or "scan"
