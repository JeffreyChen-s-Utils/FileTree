"""Named workspace templates preserve exact inputs and retire active owners without blocking Qt."""

from dataclasses import replace
import json
import os
import threading

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QMessageBox
import pytest

from test_gui import _wait
from je_file_tree.gui.app import create_workspace
from je_file_tree.core.scanner import ScanOptions
from je_file_tree.gui import scan_worker
from je_file_tree.gui.startup_state import WorkspaceState
from je_file_tree.gui.workspace_templates import (
    TEMPLATES_KEY, WorkspaceTemplate, absolute_root, read_templates, write_templates,
)
from je_file_tree.gui.workspace_templates_dialog import WorkspaceTemplatesDialog


@pytest.fixture
def workspace(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "workspace.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    settings.setValue("scan_workers", 1)
    window = create_workspace(settings)
    yield window
    window.close()
    _wait(qapp, lambda: window._close_ready)
    window.deleteLater()


def _state(*scopes, active=0):
    return WorkspaceState(tuple(scopes), active, tuple(ScanOptions(workers=2) for _ in scopes))


def test_settings_reopen_preserves_blank_single_combined_and_options(tmp_path):
    path = str(tmp_path)
    options = ScanOptions(workers=3, exclude=("cache",), include_hidden=False, file_times=True,
                          windows_owners=True, exact_windows_allocation=True, count_hard_links=True)
    state = WorkspaceState((None, path, (path,), (path, str(tmp_path / "other"))), 2, (options,) * 4)
    file = str(tmp_path / "templates.ini")
    settings = QSettings(file, QSettings.Format.IniFormat)
    write_templates(settings, (WorkspaceTemplate("Work", state),))
    settings.sync()
    reopened = QSettings(file, QSettings.Format.IniFormat)
    assert read_templates(reopened) == (WorkspaceTemplate("Work", state),)


@pytest.mark.parametrize("raw", [
    '{"version":1,"version":1,"templates":[]}',
    '{"version":1,"templates":[],"approval":true}',
    '{"version":true,"templates":[]}',
    '{broken',
])
def test_malformed_settings_rejected_without_rewrite(tmp_path, raw):
    settings = QSettings(str(tmp_path / "bad.ini"), QSettings.Format.IniFormat)
    settings.setValue(TEMPLATES_KEY, raw)
    with pytest.raises(ValueError):
        read_templates(settings)
    assert settings.value(TEMPLATES_KEY) == raw


def test_strict_template_bounds_and_private_fields(tmp_path):
    settings = QSettings(str(tmp_path / "strict.ini"), QSettings.Format.IniFormat)
    item = WorkspaceTemplate("Work", _state(str(tmp_path)))
    write_templates(settings, (item,))
    raw = settings.value(TEMPLATES_KEY)
    with pytest.raises(ValueError):
        write_templates(settings, (item, replace(item, name="work")))
    assert settings.value(TEMPLATES_KEY) == raw
    for scopes in ((None,) * 17, ((str(tmp_path),) * 257,)):
        with pytest.raises(ValueError):
            _state(*scopes)
    document = json.loads(raw)
    document["templates"][0]["state"]["options"][0]["experimental_mft"] = True
    settings.setValue(TEMPLATES_KEY, json.dumps(document))
    with pytest.raises(ValueError):
        read_templates(settings)


@pytest.mark.parametrize("path", ["relative", "C:relative", "\\root", "", "C:\\bad\0root"])
def test_ambiguous_paths_rejected(path):
    assert not absolute_root(path)


@pytest.mark.skipif(os.name != "nt", reason="Windows fully qualified path semantics")
def test_windows_bare_roots_and_foreign_posix_rejected():
    for path in ("/foreign-root", "\\folder", "C:", "\\\\?\\C:\\folder", "\\\\.\\C:\\folder"):
        assert not absolute_root(path)
    for path in ("C:\\", "C:/folder", "\\\\server\\share", "\\\\server\\share\\folder"):
        assert absolute_root(path)


def test_capture_reordered_pending_inputs_and_exact_start_source(workspace, tmp_path, monkeypatch):
    first = workspace.current
    second = workspace.add_tab()
    first._last_path = str(tmp_path / "old-result")
    first.path_edit.setText(str(tmp_path / "edited"))
    second.prepare_scan_scope((str(tmp_path),))
    workspace.tabs.tabBar().moveTab(1, 0)
    workspace.tabs.setCurrentIndex(0)
    state = workspace.capture_template_state()
    assert state.tabs == ((str(tmp_path),), str(tmp_path / "edited"))
    assert state.active == 0
    assert workspace.tabs.tabText(0) == "Multiple roots"
    calls = []
    monkeypatch.setattr(second, "start_scan_roots", calls.append)
    monkeypatch.setattr(second, "start_scan", calls.append)
    second._scan_path.click()
    second.path_edit.setText(str(tmp_path / "typed"))
    second._scan_path.click()
    second.prepare_scan_scope(None)
    second._scan_path.click()
    assert calls == [(str(tmp_path),), str(tmp_path / "typed")]
    assert not second._scan_path.isEnabled()


def test_replace_idle_no_scan_shared_defaults_and_flags(workspace, qapp, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(scan_worker.ScanWorker, "start", lambda: calls.append("started"))
    workspace.settings.setValue("scan_workers", 7)
    options = (ScanOptions(workers=3, exclude=("cache",), file_times=True),
               ScanOptions(workers=3, exclude=("cache",), include_hidden=False))
    state = WorkspaceState(((str(tmp_path),), None), 1, options)
    assert workspace.replace_template(state, (("",), ()))
    _wait(qapp, lambda: workspace._replacement is None)
    assert workspace.capture_template_state() == state
    assert not calls and workspace.settings.value("scan_workers") == 7
    assert all(page.results.outcome is None for page in workspace.operations.windows)
    assert workspace.tabs.widget(0)._scan_defaults is workspace.tabs.widget(1)._scan_defaults


def test_cancel_preview_keeps_existing_results(workspace, tmp_path, qapp):
    page = workspace.current
    page.start_scan(str(tmp_path))
    _wait(qapp, lambda: page._worker is None)
    outcome = page.results.outcome
    dialog = WorkspaceTemplatesDialog(workspace.settings, workspace.capture_template_state(), workspace)
    assert dialog.table.model().rowCount() == 1
    dialog.reject()
    assert workspace.current is page and page.results.outcome is outcome
    assert not page._closing
    dialog.deleteLater()


def test_missing_root_retained_repaired_and_rechecked(workspace, tmp_path, qapp):
    missing = str(tmp_path / "missing")
    state = _state((str(tmp_path), missing))
    dialog = WorkspaceTemplatesDialog(workspace.settings, state, workspace)
    dialog._check()
    _wait(qapp, lambda: dialog.report is not None)
    assert dialog.report[0][0] == "" and dialog.report[0][1]
    assert workspace.replace_template(dialog._draft, dialog.report)
    _wait(qapp, lambda: workspace._replacement is None)
    assert workspace.current.capture_scan_scope() == state.tabs[0]
    assert not workspace.current._scan_path.isEnabled()
    dialog.table.item(1, 2).setText("")
    dialog._check()
    assert dialog.report is None and not dialog.load.isEnabled()
    dialog.table.item(1, 2).setText(str(tmp_path))
    dialog._check()
    _wait(qapp, lambda: dialog.report is not None)
    assert dialog.report == (("", ""),)
    assert dialog._draft.tabs == ((str(tmp_path), str(tmp_path)),)
    dialog.reject()
    dialog.deleteLater()


@pytest.mark.parametrize("paused", [False, True])
def test_replace_held_scan_keeps_gui_alive(workspace, tmp_path, qapp, monkeypatch, paused):
    entered, release = threading.Event(), threading.Event()
    original = scan_worker.scan

    def held(path, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(path, **kwargs)

    monkeypatch.setattr(scan_worker, "scan", held)
    old = workspace.current
    old.start_scan(str(tmp_path))
    _wait(qapp, entered.is_set)
    old._worker.set_paused(paused)
    assert workspace.replace_template(_state(str(tmp_path)), (("",),))
    ticks = []
    QTimer.singleShot(10, lambda: ticks.append(True))
    _wait(qapp, lambda: bool(ticks))
    assert workspace.current is old and not old._close_ready
    assert workspace.add_tab() is None
    release.set()
    _wait(qapp, lambda: workspace._replacement is None)
    assert workspace.current is not old and workspace.current._worker is None


def test_close_during_retirement_never_installs(workspace, tmp_path, qapp, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = scan_worker.scan

    def held(path, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(path, **kwargs)

    monkeypatch.setattr(scan_worker, "scan", held)
    old = workspace.current
    old.start_scan(str(tmp_path))
    _wait(qapp, entered.is_set)
    workspace.replace_template(_state(None), ((),))
    workspace.close()
    release.set()
    _wait(qapp, lambda: workspace._close_ready)
    assert workspace._replacement is None and workspace.operations.windows == [old]


def test_review_guard_rejects_replacement(workspace):
    guard = object()
    workspace.current._path_dialogs.add(guard)
    try:
        assert not workspace.replace_template(_state(None), ((),))
        assert not workspace.current._closing
    finally:
        workspace.current._path_dialogs.remove(guard)


def test_close_during_validation_cancels_stale_replacement(workspace, tmp_path, qapp, monkeypatch):
    from je_file_tree.gui import workspace_templates_dialog

    entered, release = threading.Event(), threading.Event()
    original = workspace_templates_dialog.os.stat
    root = str(tmp_path / "held-root")

    def held(path, *args, **kwargs):
        if path == root:
            entered.set()
            assert release.wait(5)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(workspace_templates_dialog.os, "stat", held)
    workspace.current.prepare_scan_scope(root)
    dialog = WorkspaceTemplatesDialog(workspace.settings, workspace.capture_template_state(), workspace)
    workspace._templates_dialog = dialog
    dialog.finished.connect(lambda result: workspace._templates_finished(dialog, result))
    dialog._check()
    _wait(qapp, entered.is_set)
    old = workspace.current
    workspace.close()
    assert workspace._closing and not workspace._close_ready
    release.set()
    _wait(qapp, lambda: workspace._close_ready)
    assert workspace.operations.windows == [old] and workspace._replacement is None


def test_repeated_checks_coalesce_behind_blocked_native_check(workspace, tmp_path, qapp, monkeypatch):
    from je_file_tree.gui import workspace_templates_dialog

    entered, release = threading.Event(), threading.Event()
    original = workspace_templates_dialog.os.stat
    root = str(tmp_path / "slow-root")
    calls = []

    def held(path, *args, **kwargs):
        if path == root:
            calls.append(path)
            entered.set()
            assert release.wait(5)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(workspace_templates_dialog.os, "stat", held)
    dialog = WorkspaceTemplatesDialog(workspace.settings, _state(root), workspace)
    dialog._check()
    _wait(qapp, entered.is_set)
    for _ in range(8):
        dialog._check()
        qapp.processEvents()
    assert calls == [root]
    release.set()
    _wait(qapp, lambda: dialog.report is not None)
    assert calls == [root, root]
    dialog.reject()
    dialog.deleteLater()


def test_saved_template_actions_preserve_current_capture(workspace, tmp_path, qapp):
    page = workspace.current
    page.prepare_scan_scope((str(tmp_path),))
    state = workspace.capture_template_state()
    dialog = WorkspaceTemplatesDialog(workspace.settings, state, workspace)
    dialog.name.setText("Saved")
    dialog._edit_saved("add")
    assert read_templates(workspace.settings) == (WorkspaceTemplate("Saved", state),)
    dialog.name.setText("Renamed")
    dialog._edit_saved("rename")
    assert read_templates(workspace.settings) == (WorkspaceTemplate("Renamed", state),)
    dialog._check()
    _wait(qapp, lambda: dialog.report is not None)
    dialog._load()
    assert dialog.chosen == state
    assert workspace.current is page and page._worker is None and not page._closing
    dialog.deleteLater()


def _open_templates(workspace, monkeypatch):
    original = WorkspaceTemplatesDialog.open

    def hidden(dialog):
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        original(dialog)

    monkeypatch.setattr(WorkspaceTemplatesDialog, "open", hidden)
    workspace.show_templates()
    return workspace._templates_dialog


def test_preview_edit_never_changes_saved_opening_snapshot(workspace, tmp_path, qapp, monkeypatch):
    page = workspace.current
    page.prepare_scan_scope(str(tmp_path))
    dialog = _open_templates(workspace, monkeypatch)
    opening = dialog.current
    dialog.name.setText("Opening")
    dialog.saved_buttons["add"].click()
    dialog.table.item(0, 2).setText(str(tmp_path / "missing"))
    dialog.check.click()
    _wait(qapp, lambda: dialog.report is not None)
    assert "1" in dialog.impact_summary.text()
    assert dialog._draft != opening
    page.prepare_scan_scope(str(tmp_path / "later-workspace-input"))
    dialog.saved_buttons["update"].click()
    assert read_templates(workspace.settings)[0].state == opening
    assert dialog.current == opening and dialog.report is None
    dialog.name.setText("")
    dialog.saved_buttons["update"].click()
    assert dialog.name.text() == "" and dialog.focusWidget() is dialog.name
    assert read_templates(workspace.settings)[0].state == opening
    dialog.reject()


def test_live_impact_tracks_queued_owner_and_tab_changes(workspace, tmp_path, qapp, monkeypatch):
    dialog = _open_templates(workspace, monkeypatch)
    first = workspace.current
    monkeypatch.setattr(first, "_dispatch_scan", lambda _worker: None)
    first.start_scan(str(tmp_path))
    assert dialog._impact.tabs[0].scanning and not first._worker.isRunning()
    second = workspace.add_tab()
    second.prepare_scan_scope((str(tmp_path), str(tmp_path / "other")))
    assert len(dialog._impact.tabs) == 2 and dialog._impact.tabs[1].active
    assert str(tmp_path / "other") in dialog.impact_details.toPlainText()
    workspace.tabs.tabBar().moveTab(1, 0)
    assert dialog._impact.tabs[0].scope == second.capture_scan_scope()
    first.stop_scan()
    assert not any(tab.scanning for tab in dialog._impact.tabs)
    workspace.close_tab(1)
    _wait(qapp, lambda: workspace.tabs.count() == 1)
    assert len(dialog._impact.tabs) == 1
    dialog.reject()


@pytest.mark.parametrize("terminal", ["success", "failure", "cancel"])
def test_live_impact_updates_during_open_dialog(workspace, tmp_path, qapp, monkeypatch, terminal):
    entered, release = threading.Event(), threading.Event()
    original = scan_worker.scan

    def held(path, **kwargs):
        entered.set()
        assert release.wait(5)
        if terminal == "failure":
            raise OSError("fixture failure")
        return original(path, **kwargs)

    monkeypatch.setattr(scan_worker, "scan", held)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: None)
    page = workspace.current
    page.start_scan(str(tmp_path))
    _wait(qapp, entered.is_set)
    dialog = _open_templates(workspace, monkeypatch)
    assert dialog._impact.tabs[0].scanning
    if terminal == "cancel":
        page.stop_scan()
        assert dialog._impact.tabs[0].scanning
    release.set()
    _wait(qapp, lambda: page._worker is None)
    assert not dialog._impact.tabs[0].scanning
    assert dialog._impact.tabs[0].has_result == (page.results.outcome is not None)
    assert (page.results.outcome is not None) == (terminal != "failure")
    old = page.results.outcome
    dialog.reject()
    assert workspace.current is page and page.results.outcome is old


def test_literal_tooltips_and_stale_check_reply(workspace, tmp_path):
    dialog = WorkspaceTemplatesDialog(workspace.settings, _state(str(tmp_path)), workspace)
    path = str(tmp_path / '<folder>&literal')
    dialog.table.item(0, 2).setText(path)
    document = QTextDocument()
    document.setHtml(dialog.table.item(0, 2).toolTip())
    assert document.toPlainText() == path
    worker = object()
    dialog._worker = worker
    reason = '<missing>&unavailable'
    dialog._checked(worker, ((reason,),))
    document.setHtml(dialog.table.item(0, 3).toolTip())
    assert document.toPlainText() == reason
    dialog._worker = None
    dialog.table.item(0, 2).setText(str(tmp_path))
    dialog._checked(worker, ((reason,),))
    assert dialog.report is None and not dialog.load.isEnabled()
    dialog.reject()
    dialog.deleteLater()


def test_branch_owner_and_late_terminal_do_not_restore_impact(workspace, tmp_path, qapp, monkeypatch):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "data.bin").write_bytes(b"data")
    page = workspace.current
    page.start_scan(str(tmp_path))
    _wait(qapp, lambda: page._worker is None)
    outcome = page.results.outcome
    node = next(child for child in outcome.result.root.children if child.path == str(nested))
    entered, release = threading.Event(), threading.Event()
    original = scan_worker.scan

    def held(path, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(path, **kwargs)

    monkeypatch.setattr(scan_worker, "scan", held)
    dialog = _open_templates(workspace, monkeypatch)
    page.rescan_folder(node)
    _wait(qapp, entered.is_set)
    worker = page._worker
    assert dialog._impact.tabs[0].scanning and dialog._impact.tabs[0].has_result
    page.stop_scan()
    worker.cancelled.emit(None)
    assert not dialog._impact.tabs[0].scanning
    worker.succeeded.emit(outcome)
    assert not dialog._impact.tabs[0].scanning and page.results.outcome is outcome
    release.set()
    _wait(qapp, lambda: worker not in page._scan_workers)
    dialog.reject()
