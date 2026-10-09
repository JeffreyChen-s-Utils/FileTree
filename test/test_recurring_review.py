"""Explicit fresh rescans reuse the manual queue; changed or canceled proposals never move fixtures."""

from dataclasses import replace
import hashlib
import os
import threading
import uuid

import pytest
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtWidgets import QDialog, QMessageBox

from test_background_gui import _enable, monitored as _monitored
from test_gui import _wait
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting
from je_file_tree.core.operations import validate_tree
from je_file_tree.core.scanner import ScanCancelledError, scan
from je_file_tree.gui import file_actions, scan_worker, trash_worker
from je_file_tree.gui.cleanup_review import CleanupReview
from je_file_tree.gui.recurring_dialog import RecurringDialog
from je_file_tree.gui.recurring_review import RecurringFlow, ReviewWorker, ValidationDialog
from je_file_tree.gui.recurring_settings import ProposalSettings
from je_file_tree.gui.scan_worker import wait_for

monitored = _monitored


@pytest.fixture
def report(monitored, qapp, tmp_path):
    source = tmp_path / "review-source"
    source.mkdir()
    (source / "one.dmp").write_bytes(b"owned one")
    (source / "two.dmp").write_bytes(b"owned two")
    (source / "other.bin").write_bytes(b"kept other")
    policy = CleanupPolicy((RuleSetting("crash_dumps", True, 0),))
    monitored.settings.setValue("cleanup_policy", policy.dumps())
    monitor = _enable(monitored, (str(source),))
    monitor.tick()
    _wait(qapp, lambda: monitor.scan is None)
    monitor.timer.stop()
    current = next(iter(monitor.reports.values()))
    assert len(current.baseline.candidates) == 2
    return monitor, source, current


def _proof(source):
    return {path.name: (path.stat().st_dev, path.stat().st_ino, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in source.iterdir()}


def test_fresh_foreground_scan_enters_same_queue_and_cancel_preserves_sources(report, monitored, qapp, monkeypatch):
    monitor, source, current = report
    proof, reviewed, moved = _proof(source), [], []

    def request(dialog):
        dialog._request_review()
        return QDialog.DialogCode.Accepted

    def cancel(dialog):
        assert monitored.operations.busy and dialog.parent() is monitored.current
        assert dialog.model.rowCount() == 2 and not dialog.model.checked
        reviewed.extend(dialog.model.nodes)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(RecurringDialog, "exec", request)
    monkeypatch.setattr(CleanupReview, "exec", cancel)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    monitor.show_proposals()
    assert monitored.tabs.count() == 2
    _wait(qapp, lambda: bool(reviewed))
    assert monitored.current.results.outcome is not None and not monitored.operations.busy
    assert {node.path for node in reviewed} == {str(source / "one.dmp"), str(source / "two.dmp")}
    assert all(node.is_in(monitored.current.results.outcome.result.root) for node in reviewed)
    assert not moved and _proof(source) == proof and monitor.report_status(current) is None


def test_queue_unchecking_keeps_selection_bounded_then_ordinary_confirmation(report, monitored, qapp, monkeypatch):
    monitor, source, current = report
    proof, reviewed, moved, questions = _proof(source), [], [], []

    def accept(dialog):
        assert not dialog.model.checked
        dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        reviewed.append(dialog.model.nodes[0].path)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(CleanupReview, "exec", accept)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *_args: questions.append(True) or QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: None)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    owner = monitored.add_tab()
    RecurringFlow(monitor, owner, current).start()
    _wait(qapp, lambda: bool(moved) and owner._trash_worker is None)
    assert moved == reviewed and len(moved) == 1 and questions
    assert _proof(source) == proof, "modeled mover boundary must not remove real sources"


def test_rule_change_during_queue_blocks_confirmation_and_native_dispatch(report, monitored, qapp, monkeypatch):
    monitor, source, current = report
    proof, reviewed, moved, warnings, questions = _proof(source), [], [], [], []

    def change(dialog):
        dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        monitored.settings.setValue("cleanup_policy", CleanupPolicy((RuleSetting("crash_dumps", False, 0),)).dumps())
        reviewed.append(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(CleanupReview, "exec", change)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: questions.append(True))
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, text: warnings.append(text))
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    owner = monitored.add_tab()
    RecurringFlow(monitor, owner, current).start()
    _wait(qapp, lambda: bool(reviewed))
    assert warnings and "rules changed" in warnings[0] and not questions and not moved
    assert owner._trash_worker is None and _proof(source) == proof and not monitored.operations.busy


def test_validation_rejects_changed_native_paths_after_captured_foreground_scan(report, monitored):
    monitor, source, current = report
    root = scan(source).root
    assert validate_tree(root) is None
    (source / "other.bin").write_bytes(b"changed outside selected proposals")
    dialog = QDialog(monitored)
    worker = ReviewWorker(current, root, monitor.review_binding(current), dialog)
    worker.start()
    wait_for(worker)
    assert worker.status == "paths_changed" and not worker.reasons
    worker.deleteLater()
    dialog.deleteLater()


def test_whole_source_change_after_queue_skips_all_before_modeled_mover(report, monitored, qapp, monkeypatch):
    monitor, source, current = report
    moved, reviewed, workers = [], [], []

    def change(dialog):
        dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        (source / "other.bin").write_bytes(b"changed during review")
        reviewed.append(True)
        return QDialog.DialogCode.Accepted

    original = trash_worker.TrashWorker.run

    def run(worker):
        workers.append(worker)
        original(worker)

    monkeypatch.setattr(CleanupReview, "exec", change)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: None)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    monkeypatch.setattr(trash_worker.TrashWorker, "run", run)
    owner = monitored.add_tab()
    RecurringFlow(monitor, owner, current).start()
    _wait(qapp, lambda: bool(workers) and owner._trash_worker is None)
    assert reviewed and not moved and workers[0].result.skipped[0][1] == "proposal_changed"
    assert (source / "one.dmp").read_bytes() == b"owned one" and (source / "two.dmp").read_bytes() == b"owned two"


def test_expiry_is_checked_per_item_inside_trash_worker(report, monitored, monkeypatch):
    _monitor, source, current = report
    root = scan(source).root
    nodes = [node for node in root.children if node.name.endswith(".dmp")]
    worker = trash_worker.TrashWorker(root, nodes, [], {node: None for node in nodes}, monitored)
    worker.proposal_context = current.context
    moved = []
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    monkeypatch.setattr(trash_worker.time, "time", lambda: current.context.expires_at)
    worker.start()
    wait_for(worker)
    assert not moved and [reason for _node, reason in worker.result.skipped] == ["proposal_expired"] * 2
    worker.deleteLater()


def test_early_validation_cancel_never_starts_queued_worker(report, monitored, qapp):
    monitor, source, current = report
    dialog = ValidationDialog(current, scan(source).root, monitor.review_binding(current), monitored.current)
    dialog.reject()
    qapp.processEvents()
    assert not dialog.worker.isRunning() and dialog.worker.cancel.is_set() and not dialog.worker.reasons
    dialog.deleteLater()


def test_expired_or_canceled_request_never_creates_a_scan_tab(report, monitored, monkeypatch):
    monitor, source, current = report
    expired = replace(current, context=replace(current.context,
                                               attempt=replace(current.context.attempt, claimed_at=0), prepared_at=0))
    dialog = RecurringDialog((expired,), monitor.report_status, monitored.current)
    assert not dialog.review.isEnabled()
    dialog._request_review()
    assert dialog.requested is None
    dialog.shutdown()
    dialog.deleteLater()
    monkeypatch.setattr(RecurringDialog, "exec", lambda _dialog: QDialog.DialogCode.Rejected)
    monitor.show_proposals()
    assert monitored.tabs.count() == 1 and monitored.current._worker is None and source.is_dir()


@pytest.mark.parametrize("close", [False, True])
def test_cancel_or_close_during_fresh_scan_discards_review_intent(report, monitored, qapp, monkeypatch, close):
    monitor, source, current = report
    proof, entered, ended, reviewed = _proof(source), threading.Event(), threading.Event(), []
    release = threading.Event()

    def blocking(root, **kwargs):
        entered.set()
        kwargs["cancel"].wait()
        if close:
            assert release.wait(5), "closing blocked the GUI release timer"
        ended.set()
        raise ScanCancelledError(scan(root))

    monkeypatch.setattr(scan_worker, "scan", blocking)
    monkeypatch.setattr(CleanupReview, "exec", lambda _dialog: reviewed.append(True))
    owner = monitored.add_tab()
    RecurringFlow(monitor, owner, current).start()
    assert entered.wait(5)
    try:
        if close:
            monitored.close_tab(monitored.tabs.indexOf(owner))
            assert owner._closing and not ended.is_set()
            QTimer.singleShot(0, release.set)
            _wait(qapp, lambda: monitored.tabs.count() == 1)
        else:
            owner.stop_scan(wait=True)
        assert ended.is_set()
        qapp.processEvents()
        assert not reviewed and _proof(source) == proof and not monitored.operations.busy
    finally:
        release.set()


def test_rule_change_between_items_is_checked_on_the_operation_thread(report, monitored, monkeypatch):
    _monitor, source, current = report
    root = scan(source).root
    nodes = [node for node in root.children if node.name.endswith(".dmp")]
    settings_source = ProposalSettings.capture(monitored.settings)
    worker = trash_worker.TrashWorker(root, nodes, [], {node: None for node in nodes}, monitored)
    worker.proposal_context = current.context
    worker.proposal_check = lambda: settings_source.status(current)
    moved = []

    def move(path):
        moved.append(path)
        writer = QSettings(settings_source.file_name, settings_source.format)
        writer.setValue("cleanup_policy", CleanupPolicy((RuleSetting("crash_dumps", False, 0),)).dumps())
        writer.sync()
        return True

    monkeypatch.setattr(file_actions, "trash_receipt", move)
    worker.start()
    wait_for(worker)
    assert len(moved) == 1 and len(worker.result.moved) == 1
    assert worker.result.skipped[0][1] == "proposal_changed"
    assert all((source / name).is_file() for name in ("one.dmp", "two.dmp"))
    worker.deleteLater()


def test_reentrant_settings_keep_the_exact_integration_group(report, monitored, tmp_path):
    _monitor, _source, current = report
    settings = QSettings(str(tmp_path / "grouped.ini"), QSettings.Format.IniFormat)
    settings.beginGroup("embedded")
    settings.setFallbacksEnabled(False)
    for key in ("background_config", "background_attempts", "cleanup_policy"):
        settings.setValue(key, monitored.settings.value(key))
    settings.sync()
    source = ProposalSettings.capture(settings)
    assert source.status(current) is None and source.group == "embedded" and not source.fallbacks
    settings.setValue("background_attempts", "invalid")
    settings.sync()
    assert source.status(current) == "unavailable"


@pytest.mark.skipif(os.name != "nt", reason="Native private HKCU settings backend")
def test_reentrant_native_registry_settings_only_use_fresh_owned_uuid_metadata(report, monitored):
    import winreg

    _monitor, _source, current = report
    owner = uuid.uuid4().hex
    path = "Software\\FileTree.Recurring.Test." + owner
    settings = QSettings("HKEY_CURRENT_USER\\" + path, QSettings.Format.NativeFormat)
    assert not settings.allKeys(), "Refuse a pre-existing native fixture"
    keys = {"owner", "background_config", "background_attempts", "cleanup_policy"}
    settings.setValue("owner", owner)
    try:
        for key in keys - {"owner"}:
            settings.setValue(key, monitored.settings.value(key))
        settings.sync()
        source = ProposalSettings.capture(settings)
        assert source.namespace is None and source.status(current) is None
        settings.setValue("cleanup_policy", CleanupPolicy((RuleSetting("crash_dumps", False, 0),)).dumps())
        settings.sync()
        assert source.status(current) == "rule_changed"
    finally:
        assert settings.value("owner") == owner and set(settings.allKeys()) == keys
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as handle:
            assert winreg.QueryInfoKey(handle)[0] == 0
        settings.clear()
        settings.sync()
        assert not settings.allKeys()
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
