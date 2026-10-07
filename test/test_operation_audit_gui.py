"""Approved moves are audited before acting; write failures stop remaining entries."""

from PySide6.QtWidgets import QFileDialog

from conftest import make_tree
from test_gui import _wait
from je_file_tree.core.operation_journal import JournalApproval, OperationJournal, OperationOutcome, OperationRecord
from je_file_tree.core.operations import MoveReceipt
from je_file_tree.core.scanner import scan
from je_file_tree.gui import file_actions
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.recent_actions import RecentActions
from je_file_tree.gui.scan_worker import wait_for
from je_file_tree.gui.trash_worker import TrashWorker


def _batch(qapp, root, journal, *, reasons=None):
    results = []
    worker = TrashWorker(root, list(root.children), [], {}, audit=JournalApproval(journal, reasons or {}))
    worker.done.connect(results.append)
    worker.start()
    _wait(qapp, lambda: bool(results))
    wait_for(worker)
    return results[0]


def test_partially_successful_batch_records_destinations_failures_and_reasons(qapp, tmp_path, monkeypatch) -> None:
    folder = tmp_path / "scan"
    folder.mkdir()
    make_tree(folder, {"one": b"data", "two": b"data"})
    root = scan(folder).root
    journal = OperationJournal(tmp_path / "journal")

    def move(path):
        assert len(journal.recent().records) == 2, "all approvals must be durable before the first move"
        return MoveReceipt(path.endswith("one"), str(tmp_path / "trash/file") if path.endswith("one") else None)

    monkeypatch.setattr(file_actions, "trash_receipt", move)
    result = _batch(qapp, root, journal, reasons={root.children[0]: "cleanup:temp"})
    assert len(result.moved) == len(result.failed) == 1 and not result.journal_errors
    rows = {record.source: record for record in journal.recent().records}
    assert rows[str(folder / "one")].outcome.status == "moved"
    assert rows[str(folder / "one")].outcome.destination == str(tmp_path / "trash/file")
    assert rows[str(folder / "two")].outcome.status == "failed"
    assert {record.reason for record in rows.values()} == {"manual", "cleanup:temp"}


def test_failed_approval_write_performs_no_moves(qapp, tmp_path, monkeypatch) -> None:
    (tmp_path / "file").write_bytes(b"data")
    root = scan(tmp_path).root
    journal = OperationJournal(tmp_path / "journal")
    moved = []

    def denied(records):
        raise OSError("journal unavailable")

    monkeypatch.setattr(journal, "append", denied)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    result = _batch(qapp, root, journal)
    assert moved == [] and result.skipped[0][1] == "journal"
    assert result.journal_errors and (tmp_path / "file").exists()


def test_failed_result_write_preserves_success_and_cancels_remaining_moves(qapp, tmp_path, monkeypatch) -> None:
    make_tree(tmp_path, {"one": b"data", "two": b"data"})
    root = scan(tmp_path).root
    journal = OperationJournal(tmp_path / "journal")
    original = journal.append
    calls, moved = [], []

    def fail_after_approvals(records):
        calls.append(len(records))
        if len(calls) > 1:
            raise OSError("disk full")
        original(records)

    monkeypatch.setattr(journal, "append", fail_after_approvals)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or MoveReceipt(True))
    result = _batch(qapp, root, journal)
    assert len(moved) == len(result.moved) == len(result.skipped) == 1
    assert result.skipped[0][1] == "cancelled" and result.journal_errors
    assert all(record.outcome.status == "approved" for record in journal.recent().records)


def test_skipped_snapshot_changes_are_recorded_without_mover_call(qapp, tmp_path, monkeypatch) -> None:
    (tmp_path / "file").write_bytes(b"data")
    root = scan(tmp_path).root
    (tmp_path / "file").write_bytes(b"changed")
    journal = OperationJournal(tmp_path / "journal")
    moved = []
    monkeypatch.setattr(file_actions, "trash_receipt", lambda path: moved.append(path) or True)
    result = _batch(qapp, root, journal)
    assert not moved and result.skipped
    record = journal.recent().records[0]
    assert record.outcome.status == "skipped" and record.outcome.detail == "changed"


def test_recent_actions_shows_unknown_outcomes_and_exports_redacted_metadata(qapp, tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "file").write_bytes(b"data")
    node = scan(home).root.children[0]
    journal = OperationJournal(tmp_path / "journal")
    approved = OperationRecord.approved("batch", node, "manual")
    journal.append([approved, approved.finished(OperationOutcome("moved", destination=str(home / ".Trash/file"))),
                    OperationRecord.approved("batch", node, "manual")])
    dialog = RecentActions(journal)
    try:
        _wait(qapp, lambda: dialog.model.rowCount() == 2)
        statuses = {dialog.model.index(row, 4).data() for row in range(dialog.model.rowCount())}
        assert statuses == {tr("journal_status_approved"), tr("journal_status_moved")}
        assert any(tr("journal_hint") == label.text()
                   for label in dialog.findChildren(type(dialog.status)))
        output = tmp_path / "export.csv"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(output), ""))
        monkeypatch.setattr("je_file_tree.core.operation_journal.os.path.expanduser", lambda value: str(home))
        dialog.export()
        _wait(qapp, lambda: output.exists() and not dialog._exports)
        text = output.read_text(encoding="utf-8-sig")
        assert str(home) not in text and "{HOME}" in text and "unknown" in text
    finally:
        dialog.shutdown()
        dialog.deleteLater()
