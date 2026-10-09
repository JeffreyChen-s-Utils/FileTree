"""Explicit approvals, audit failures and dialog lifetimes use only fresh owned duplicate fixtures."""

import os
import threading
from types import SimpleNamespace
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from test_duplicate_links import _fixture, open_bytes
from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core.duplicate_link_ops import LinkOutcome, LinkResult
from je_file_tree.core.duplicate_links import prepare_links
from je_file_tree.core.duplicates import find_duplicates
from je_file_tree.core import duplicate_links
from je_file_tree.core.operation_journal import OperationJournal
from je_file_tree.core.scanner import scan
from je_file_tree.core.protected import Protection, PROGRAMS
from je_file_tree.gui import duplicate_link_worker, main_window
from je_file_tree.gui.duplicate_link_dialog import DuplicateLinksDialog
from je_file_tree.gui.duplicate_link_worker import LinkOperationWorker
from je_file_tree.gui.scan_worker import analyse


def _dialog(window, qapp, tmp_path):
    root, group = _fixture(tmp_path)
    journal = OperationJournal(tmp_path / "owned-journal")
    dialog = DuplicateLinksDialog(root, [group], journal, window)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    return dialog, journal


def test_plain_complete_preview_default_no_keeps_independent_sources(window, qapp, tmp_path, monkeypatch):
    dialog, journal = _dialog(window, qapp, tmp_path)
    pair = dialog.plan.pairs[0]
    questions = []

    def decline(question):
        questions.append(question)
        assert question.textFormat() == Qt.TextFormat.PlainText
        assert question.defaultButton() is question.button(QMessageBox.StandardButton.No)
        assert pair.copy_path in question.detailedText() and pair.keeper_path in question.detailedText()
        assert "not kept in Trash" in question.text() and "permission" in question.text()
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "exec", decline)
    dialog._apply()
    assert questions and dialog.operation is None and not dialog.changed
    assert not journal.recent().records and os.stat(pair.copy_path).st_nlink == 1
    assert dialog.model.rowCount() == 1
    assert not dialog.model.flags(dialog.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)


def test_native_review_persists_approval_before_link_and_records_original_identity(
        window, qapp, tmp_path, monkeypatch):
    dialog, journal = _dialog(window, qapp, tmp_path)
    plan, native = dialog.plan, duplicate_link_worker.execute_links
    original_identity = os.stat(plan.pairs[0].copy_path).st_ino

    def approved(plan, **kwargs):
        records = journal.recent().records
        assert len(records) == 1 and records[0].outcome.status == "approved"
        assert records[0].reason == "duplicate_links" and records[0].source == plan.pairs[0].copy_path
        return native(plan, **kwargs)

    monkeypatch.setattr(duplicate_link_worker, "execute_links", approved)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog._apply()
    _wait(qapp, lambda: not dialog.operation.isRunning() and dialog._reported)
    item = dialog.operation.result.outcomes[0]
    record = journal.recent().records[0]
    assert item.linked and not item.error and not item.retained
    assert record.outcome.status == "linked" and record.identity[1] == original_identity
    assert record.outcome.destination == item.pair.keeper_path
    assert os.stat(item.pair.copy_path).st_ino == os.stat(item.pair.keeper_path).st_ino
    assert open_bytes(item.pair.copy_path) == open_bytes(item.pair.keeper_path)
    assert item.pair.copy_path in dialog.output.toPlainText() and not dialog.apply_button.isEnabled()
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)


def test_approval_audit_failure_prevents_native_execution(window, tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    journal = OperationJournal(tmp_path / "owned-journal")

    def fail(_records):
        raise OSError("<audit denied>&")

    monkeypatch.setattr(journal, "append", fail)
    monkeypatch.setattr(duplicate_link_worker, "execute_links", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(AssertionError("No mutation without durable approval")))
    worker = LinkOperationWorker(prepare_links(root, [group]), journal, window)
    worker.run()
    assert worker.journal_errors == ["<audit denied>&"] and not worker.result.outcomes[0].linked
    assert all(os.stat(node.path).st_nlink == 1 for node in group.files)


def test_outcome_audit_failure_preserves_success_and_stops_remaining_group(window, tmp_path, monkeypatch):
    root, group = _fixture(tmp_path, copies=3)
    journal = OperationJournal(tmp_path / "owned-journal")
    native = journal.append
    count = 0

    def fail_after_approval(records):
        nonlocal count
        count += 1
        if count > 1:
            raise OSError("outcome audit denied")
        native(records)

    monkeypatch.setattr(journal, "append", fail_after_approval)
    worker = LinkOperationWorker(prepare_links(root, [group]), journal, window)
    worker.run()
    first, second = worker.result.outcomes
    assert worker.result.canceled and first.linked and not second.linked
    assert worker.journal_errors == ["outcome audit denied"] and count == 2
    assert os.stat(first.pair.copy_path).st_ino == os.stat(first.pair.keeper_path).st_ino
    assert os.stat(second.pair.copy_path).st_nlink == 1
    assert all(record.outcome.status == "approved" for record in journal.recent().records)


def test_preview_stop_close_joins_and_drops_late_authority(window, qapp, tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    entered = threading.Event()

    def wait(_root, _groups, *, cancel):
        entered.set()
        assert cancel.wait(10)
        return prepare_links(root, [group])

    monkeypatch.setattr(duplicate_link_worker, "prepare_links", wait)
    dialog = DuplicateLinksDialog(root, [group], OperationJournal(tmp_path / "owned-journal"), window)
    _wait(qapp, entered.is_set)
    dialog.stop()
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    dialog._show(prepare_links(root, [group]))
    assert not dialog.worker.isRunning() and dialog.plan is None and dialog._closed
    assert not dialog.apply_button.isEnabled() and all(os.stat(node.path).st_nlink == 1 for node in group.files)


def test_close_joins_and_reports_late_partial_retained_paths_in_plain_text(window, qapp, tmp_path, monkeypatch):
    dialog, _journal = _dialog(window, qapp, tmp_path)
    entered, messages = threading.Event(), []

    def wait(plan, *, cancel, progress, completed):
        progress(plan.pairs[0])
        entered.set()
        assert cancel.wait(10)
        observed = LinkOutcome(plan.pairs[0], True, "<partial>&", ("<retained>&",))
        completed(observed)
        return LinkResult([observed], canceled=True)

    def answer(question):
        messages.append((question.textFormat(), question.detailedText()))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(duplicate_link_worker, "execute_links", wait)
    monkeypatch.setattr(QMessageBox, "exec", answer)
    dialog._apply()
    _wait(qapp, entered.is_set)
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    assert not dialog.operation.isRunning() and dialog.operation.result.outcomes[0].linked
    assert len(messages) == 2 and messages[1][0] == Qt.TextFormat.PlainText
    assert "<retained>&" in messages[1][1] and "<partial>&" in messages[1][1]
    before = dialog.status.text()
    dialog._completed(LinkResult())
    assert dialog.status.text() == before


def test_main_routes_exact_groups_joins_serializes_and_rescans_current_root(window, tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    outcome = analyse(scan(root.path))
    window.results.show_outcome(outcome)
    # Groups must belong to the current scan, with current handle proofs.
    root = outcome.result.root
    group = find_duplicates(root, min_size=1).groups[0]
    group = replace(group, kept=group.files[0])
    panel = window.results.duplicates
    panel._found = SimpleNamespace()
    panel._groups = [group]
    events = []

    class Dialog:
        changed = True
        def __init__(self, scope, groups, _journal, _parent):
            events.append((scope, tuple(groups)))
        def exec(self):
            assert window.operation_busy
            window.start_scan(root.path)
            assert window._worker is None
            return 0
        def shutdown(self):
            events.append("joined")
        def deleteLater(self):  # noqa: N802 - Qt API
            events.append("deleted")

    monkeypatch.setattr(main_window, "DuplicateLinksDialog", Dialog)
    monkeypatch.setattr(window, "rescan_folder", lambda scope: events.append(("rescan", scope)))
    monkeypatch.setattr(window._bin_labels, "refresh", lambda: None)
    window.show_duplicate_links([group])
    assert events == [(root, (group,)), "joined", "deleted", ("rescan", root)]
    assert not window.operation_busy
    panel.kind.setCurrentIndex(panel.kind.findData("photos"))
    panel._groups, panel._found = [group], SimpleNamespace()
    assert not panel.link_groups and not panel.link_extra.isEnabled()
    window.show_duplicate_links([group])
    assert len(events) == 4


def test_protected_decision_is_visible_and_cannot_open_approval(window, qapp, tmp_path, monkeypatch):
    root, group = _fixture(tmp_path)
    monkeypatch.setattr(duplicate_links, "protected_places", lambda: [Protection(root.path, PROGRAMS)])
    dialog = DuplicateLinksDialog(root, [group], OperationJournal(tmp_path / "owned-journal"), window)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    assert all(pair.reason for pair in dialog.plan.pairs) and dialog.model.rowCount() == 1
    assert not dialog.apply_button.isEnabled()
    dialog._apply()
    assert dialog.operation is None and not dialog.changed
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)


def test_replaced_root_after_dialog_never_receives_old_root_refresh(window, tmp_path, monkeypatch):
    root, _group = _fixture(tmp_path)
    window.results.show_outcome(analyse(scan(root.path)))
    root = window.results.outcome.result.root
    group = find_duplicates(root, min_size=1).groups[0]
    group = replace(group, kept=group.files[0])
    panel = window.results.duplicates
    panel._found, panel._groups = SimpleNamespace(), [group]

    class Dialog:
        changed = True
        def __init__(self, *_args):
            pass
        def exec(self):
            window.results.show_outcome(analyse(scan(root.path)))
            return 0
        def shutdown(self):
            pass
        def deleteLater(self):  # noqa: N802 - Qt API
            pass

    monkeypatch.setattr(main_window, "DuplicateLinksDialog", Dialog)
    monkeypatch.setattr(window, "rescan_folder", lambda _root:
                        (_ for _ in ()).throw(AssertionError("Old tree must not refresh a new result")))
    window.show_duplicate_links([group])
    assert window.results.outcome.result.root is not root and not window.operation_busy


def test_native_main_workflow_refreshes_keeper_and_extra_scan_identities(window, qapp, tmp_path, monkeypatch):
    old, _group = _fixture(tmp_path, copies=3)
    window.results.show_outcome(analyse(scan(old.path)))
    old = window.results.outcome.result.root
    found = find_duplicates(old, min_size=1)
    group = replace(found.groups[0], kept=found.groups[0].files[0])
    panel = window.results.duplicates
    panel._found, panel._groups = found, [group]
    journal = OperationJournal(tmp_path / "owned-journal")
    window._journal = journal

    def review(dialog):
        _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
        dialog._apply()
        _wait(qapp, lambda: not dialog.operation.isRunning() and dialog._reported)
        assert all(row.linked and not row.error for row in dialog.operation.result.outcomes)
        dialog.reject()
        _wait(qapp, lambda: not dialog._finish_waiting)
        return 0

    monkeypatch.setattr(DuplicateLinksDialog, "exec", review)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    window.show_duplicate_links([group])
    _wait(qapp, lambda: window._worker is None and window.results.outcome.result.root is not old)
    root = window.results.outcome.result.root
    assert root.path == old.path and root.file_count == 3 and root.size == old.size
    assert len({node.snapshot for node in root.iter_files()}) == 1
    assert all(os.stat(node.path).st_nlink == 3 for node in root.iter_files())
    records = journal.recent().records
    assert len(records) == 2 and all(record.outcome.status == "linked" for record in records)
    assert not window.results.duplicates.groups
