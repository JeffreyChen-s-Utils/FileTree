"""Default-No compaction review, durable audit barriers and truthful joined partial outcomes."""

import threading
import time
from types import SimpleNamespace
import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
import pytest

from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core.operation_journal import OperationJournal
from je_file_tree.core.scanner import scan
from je_file_tree.core.virtual_disk_compaction import CompactionOutcome, CompactionPlan
from je_file_tree.core.virtual_disk_info import VirtualDiskInfo
from je_file_tree.core.virtual_disk_runtime import DiskRuntime
from je_file_tree.core.virtual_disks import find_virtual_disks, VirtualDisks
from je_file_tree.gui import virtual_disk_compaction as gui
from je_file_tree.gui import virtual_disks as inventory
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_worker import analyse


def _wait(qapp, predicate):
    deadline = time.monotonic() + 10
    while not predicate():
        assert time.monotonic() < deadline
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()


def _fixture(tmp_path, monkeypatch):
    source = tmp_path / "scan"
    source.mkdir()
    (source / "owned 機器.vhdx").write_bytes(b"Owned review fixture; native calls are isolated")
    root = scan(source).root
    disk = find_virtual_disks(root, registrations=[]).rows[0]
    info = VirtualDiskInfo(disk, (), 67108864, 4194304, 3, False, uuid.uuid4().bytes_le)
    plan = CompactionPlan(info, DiskRuntime(()))
    journal = OperationJournal(tmp_path / "journal")
    def prepare(candidate, **_kwargs):
        assert candidate is disk
        return plan
    monkeypatch.setattr(gui, "prepare_compaction", prepare)
    return root, disk, plan, journal


def test_literal_frozen_review_defaults_to_no_and_never_audits_or_executes(window, qapp, tmp_path, monkeypatch):
    _root, disk, plan, journal = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(gui, "execute_compaction", lambda *_args, **_kwargs: pytest.fail("No approval"))
    questions = []
    def no(question):
        questions.append(question.text())
        assert question.defaultButton() == question.button(QMessageBox.StandardButton.No)
        assert question.textFormat() == Qt.TextFormat.PlainText
        assert disk.path in question.text() and disk.path in question.detailedText()
        assert str(uuid.UUID(bytes_le=plan.info.identifier)) in question.detailedText()
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, "exec", no)
    dialog = gui.VirtualDiskCompactionDialog(disk, journal, "auto", window)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    assert dialog.details.isReadOnly() and dialog.apply_button.isEnabled()
    dialog.apply()
    assert len(questions) == 1 and dialog.operation is None and not dialog.changed
    assert not journal.recent().records
    dialog.reject()


def test_durable_approval_precedes_execution_and_post_success_error_keeps_completed_audit(
        window, qapp, tmp_path, monkeypatch):
    _root, disk, plan, journal = _fixture(tmp_path, monkeypatch)
    def execute(captured, *, machine_stopped, cancel):
        assert captured is plan and machine_stopped and not cancel.is_set()
        prior = journal.recent().records
        assert len(prior) == 1 and prior[0].outcome.status == "approved" and prior[0].source == disk.path
        return CompactionOutcome(True, True, 4194304, None, "<b>late query refused</b>")
    monkeypatch.setattr(gui, "execute_compaction", execute)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog = gui.VirtualDiskCompactionDialog(disk, journal, "auto", window)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    requested = []
    dialog.execution_requested.connect(lambda: requested.append(True))
    dialog.apply()
    _wait(qapp, lambda: dialog.operation is not None and not dialog.operation.isRunning() and dialog._reported)
    assert requested == [True] and dialog.changed and not dialog.apply_button.isEnabled()
    assert tr("journal_status_compacted") in dialog.status.text() and tr("size_unknown") in dialog.status.text()
    assert "<b>late query refused</b>" in dialog.status.text() and dialog.status.textFormat() == Qt.TextFormat.PlainText
    records = journal.recent().records
    assert len(records) == 1 and records[0].outcome.status == "compacted" and not records[0].outcome.destination
    assert records[0].identity == dialog.operation.record.identity and records[0].reason == "virtual_disk_compaction"
    dialog.reject()


@pytest.mark.parametrize("fail_after_success", [False, True])
def test_approval_write_failure_blocks_execution_and_result_write_failure_retains_completion(
        window, qapp, tmp_path, monkeypatch, fail_after_success):
    _root, disk, _plan, journal = _fixture(tmp_path, monkeypatch)
    appends, operations = [], []
    append = journal.append
    def unreliable(records):
        appends.append(records[0].outcome.status)
        if not fail_after_success or records[0].outcome.status != "approved":
            raise OSError("owned audit refused")
        append(records)
    monkeypatch.setattr(journal, "append", unreliable)
    def execute(*_args, **_kwargs):
        operations.append(True)
        return CompactionOutcome(True, True, 8192, 8192)
    monkeypatch.setattr(gui, "execute_compaction", execute)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog = gui.VirtualDiskCompactionDialog(disk, journal, "auto", window)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    dialog.apply()
    _wait(qapp, lambda: not dialog.operation.isRunning() and dialog._reported)
    assert operations == ([True] if fail_after_success else [])
    assert dialog.changed == fail_after_success and dialog.operation.result.compacted == fail_after_success
    assert "owned audit refused" in dialog.status.text()
    assert appends == (["approved", "compacted"] if fail_after_success else ["approved"])
    dialog.reject()


def test_close_cancels_preview_joins_and_ignores_late_review(window, qapp, tmp_path, monkeypatch):
    _root, disk, plan, journal = _fixture(tmp_path, monkeypatch)
    entered = threading.Event()
    def prepare(_disk, *, cancel):
        entered.set()
        assert cancel.wait(10)
        return plan
    monkeypatch.setattr(gui, "prepare_compaction", prepare)
    dialog = gui.VirtualDiskCompactionDialog(disk, journal, "auto", window)
    _wait(qapp, entered.is_set)
    dialog.reject()
    dialog._show(plan)
    assert not dialog.worker.isRunning() and dialog.plan is None and not dialog.apply_button.isEnabled()


def test_close_joins_active_operation_reports_real_result_and_audits_it(window, qapp, tmp_path, monkeypatch):
    _root, disk, _plan, journal = _fixture(tmp_path, monkeypatch)
    entered, reports = threading.Event(), []
    def execute(_plan, *, cancel, **_kwargs):
        entered.set()
        assert cancel.wait(10)
        return CompactionOutcome(True, True, 8192, 8192)
    monkeypatch.setattr(gui, "execute_compaction", execute)
    def question(box):
        reports.append(box.text())
        return QMessageBox.StandardButton.Yes if box.standardButtons() & QMessageBox.StandardButton.Yes else (
            QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "exec", question)
    dialog = gui.VirtualDiskCompactionDialog(disk, journal, "auto", window)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    dialog.apply()
    _wait(qapp, entered.is_set)
    dialog.reject()
    assert dialog.changed and dialog._reported and not dialog.operation.isRunning()
    assert len(reports) == 2 and tr("journal_status_compacted") in reports[-1]
    assert journal.recent().records[0].outcome.status == "compacted"


def test_inventory_disables_stale_authority_and_main_window_rescans_complete_root(
        window, qapp, tmp_path, monkeypatch):
    root, disk, _plan, journal = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(inventory, "sys", SimpleNamespace(platform="win32"))
    found = VirtualDisks((disk,), 1, 0, False)
    monkeypatch.setattr(inventory, "find_virtual_disks", lambda *_args, **_kwargs: found)
    monkeypatch.setattr(gui, "execute_compaction", lambda *_args, **_kwargs: CompactionOutcome(True, False,
                                                                                        error="partial refusal"))
    monkeypatch.setattr(QMessageBox, "exec", lambda _box: QMessageBox.StandardButton.Yes)
    def review(dialog):
        _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
        dialog.apply()
        _wait(qapp, lambda: not dialog.operation.isRunning() and dialog._reported)
        dialog.reject()
        return 0
    monkeypatch.setattr(gui.VirtualDiskCompactionDialog, "exec", review)
    outer = inventory.VirtualDisksDialog(root, "auto", window, journal=journal)
    _wait(qapp, lambda: outer.model.rowCount() == 1 and not outer.worker.isRunning())
    outer.view.setCurrentIndex(outer.proxy.index(0, 0))
    assert outer.compact_button.isEnabled()
    outer.compact_selected()
    assert outer.changed and outer.compaction is None and tr("vc_stale") in outer.status.text()
    assert all(row.info is None for row in outer.model.rows())
    assert not outer.compact_button.isEnabled() and not outer.info_button.isEnabled()
    outer.reject()
    window.results.show_outcome(analyse(scan(root.path)))
    captured = window.results.outcome.result.root
    rescans = []
    monkeypatch.setattr(window, "rescan_folder", rescans.append)
    def inventory_review(dialog):
        assert dialog in window._path_dialogs and dialog.journal is window._journal
        dialog.changed = True
        dialog.reject()
        return 0
    monkeypatch.setattr(inventory.VirtualDisksDialog, "exec", inventory_review)
    window.show_virtual_disks()
    assert rescans == [captured] and not window._path_dialogs
