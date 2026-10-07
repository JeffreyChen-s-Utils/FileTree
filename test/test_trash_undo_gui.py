"""Ephemeral GUI Undo uses only newly created mocked bin fixtures and owned inverse workers."""

from contextlib import contextmanager
import os
import sys
import threading
import time
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core import windows_restore
from je_file_tree.core.operation_journal import OperationJournal
from je_file_tree.core.node import Node
from je_file_tree.core.operations import MoveReceipt
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import stat_snapshot
from je_file_tree.core.trash_restore import RestoreResult, capture_origin
from je_file_tree.gui import file_actions, trash_worker, undo_worker
from je_file_tree.gui.scan_worker import analyse, wait_for


def _fixture(window, qapp, tmp_path, monkeypatch):
    source = tmp_path.resolve() / "scan" / "original"
    (source / "empty").mkdir(parents=True)
    (source / "file").write_bytes(b"owned original payload")
    parent = tmp_path.resolve() / "$Recycle.Bin" / "S-1-owned-fixture"
    parent.mkdir(parents=True)
    payload, receipt = parent / "$Rpayload", parent / "$Ipayload"
    window.results.show_outcome(analyse(scan(source.parent)))
    node = window.results.tree_model.root.children[0]
    window._journal = OperationJournal(tmp_path / "journal")
    calls, questions = [], []

    def move(path):
        assert path == str(source)
        assert window._trash_worker._origins[path].path == path, "capture must precede native Trash"
        assert window._journal.recent().records[0].outcome.status == "approved"
        os.rename(source, payload)
        receipt.write_bytes(b"owned fixture metadata")
        calls.append("trash")
        return MoveReceipt(True, str(payload))

    def undelete(**_kwargs):
        assert any(record.reason == "undo" and record.outcome.status == "approved"
                   for record in window._journal.recent().records), "inverse approval must precede native restore"
        calls.append("restore")
        os.rename(payload, source)
        receipt.unlink()  # Only this freshly created fixture metadata, simulating the native Shell.

    @contextmanager
    def selected(*_args, **_kwargs):
        yield SimpleNamespace(trashed=str(payload), undelete=undelete)

    def prepare(origin, actual, cancel):
        return windows_restore.prepare_windows_restore(origin, actual=actual, cancel=cancel)

    monkeypatch.setattr(file_actions, "trash_receipt", move)
    monkeypatch.setattr(trash_worker, "prepare_undo", prepare)
    monkeypatch.setattr(windows_restore, "recycle_item", selected)
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "exec", lambda dialog: questions.append(
        (dialog.textFormat(), dialog.text())) or QMessageBox.StandardButton.Ok)
    window.move_to_trash([node])
    _wait(qapp, lambda: window._trash_worker is None)
    return source, payload, receipt, node, calls, questions


def test_capture_precedes_trash_offer_never_restores_automatically_and_path_survives_detachment(
        window, qapp, tmp_path, monkeypatch):
    source, payload, receipt, node, calls, _ = _fixture(window, qapp, tmp_path, monkeypatch)
    assert window._undo.available and not window._undo.button.isHidden() and calls == ["trash"]
    assert node.parent is None and node.path != str(source)
    assert window._undo.entries[0].plan.origin.path == str(source)
    assert not source.exists() and payload.exists() and receipt.exists() and window._worker is None
    window._undo.undo()
    worker = window._undo.worker
    window._undo.undo()  # A second click has no authority and never queues another worker.
    _wait(qapp, lambda: window._undo.worker is None)
    assert worker.result.results[0].restored and calls == ["trash", "restore"]
    assert (source / "file").read_bytes() == b"owned original payload" and (source / "empty").is_dir()
    assert not payload.exists() and not receipt.exists() and not window._undo.available
    _wait(qapp, lambda: window._worker is None)
    assert window.results.tree_model.root.children[0].path == str(source), "source parent is rescanned"
    records = window._journal.recent().records
    assert {record.outcome.status for record in records} == {"moved", "restored"}
    assert {record.reason for record in records} == {"manual", "undo"}


def test_collision_preserves_arrival_and_payload_with_plaintext_actual_paths(window, qapp, tmp_path, monkeypatch):
    source, payload, receipt, _, calls, questions = _fixture(window, qapp, tmp_path, monkeypatch)
    source.mkdir()
    (source / "arrival").write_bytes(b"preserved arrival")
    window._undo.undo()
    _wait(qapp, lambda: window._undo.worker is None)
    assert calls == ["trash"] and payload.exists() and receipt.exists()
    assert (source / "arrival").read_bytes() == b"preserved arrival"
    assert questions[0][0] == Qt.TextFormat.PlainText
    assert str(source) in questions[0][1] and str(payload) in questions[0][1] and "occupied" in questions[0][1]
    assert {record.outcome.status for record in window._journal.recent().records} == {"moved", "failed"}


@pytest.mark.parametrize("stale", ["expiry", "root", "scan", "new_trash"])
def test_expired_or_replaced_offer_never_starts_inverse_operation(window, qapp, tmp_path, monkeypatch, stale):
    source, payload, receipt, _, calls, _ = _fixture(window, qapp, tmp_path, monkeypatch)
    if stale == "expiry":
        window._undo.deadline = time.monotonic() - 1
    elif stale == "root":
        window.results.show_outcome(analyse(scan(source.parent)))
    elif stale == "scan":
        window.start_scan(str(source.parent))
        assert not window._undo.available
    else:
        fresh = source.parent / "new"
        fresh.write_bytes(b"new")
        root = window.results.tree_model.root
        node = Node("new", False, size=3, parent=root, snapshot=stat_snapshot(str(fresh)))
        root.children.append(node)
        monkeypatch.setattr(file_actions, "trash_receipt", lambda path: path != str(fresh))
        monkeypatch.setattr(QMessageBox, "warning", lambda *_: QMessageBox.StandardButton.Ok)
        window.move_to_trash([node])
        _wait(qapp, lambda: window._trash_worker is None)
        assert not window._undo.available and fresh.exists(), "a new accepted but failed Trash expires the old offer"
    window._undo.undo()
    assert calls == ["trash"] and window._undo.worker is None
    assert not source.exists() and payload.exists() and receipt.exists()


def test_worker_rechecks_deadline_before_journaling_or_native_restore(window, qapp, tmp_path, monkeypatch):
    _, payload, receipt, _, calls, _ = _fixture(window, qapp, tmp_path, monkeypatch)
    worker = undo_worker.UndoWorker(window._undo.entries, window._journal, time.monotonic() - 1, 0)
    worker.start()
    wait_for(worker)
    assert worker.result.results[0].error and not worker.result.results[0].restored
    assert calls == ["trash"] and payload.exists() and receipt.exists()
    assert len(window._journal.recent().records) == 1


def test_inverse_approval_failure_performs_no_restore_and_reports_audit_error(window, qapp, tmp_path, monkeypatch):
    source, payload, receipt, _, calls, questions = _fixture(window, qapp, tmp_path, monkeypatch)

    def denied(_records):
        raise OSError("owned audit unavailable <error>&")

    monkeypatch.setattr(window._journal, "append", denied)
    window._undo.undo()
    _wait(qapp, lambda: window._undo.worker is None)
    assert calls == ["trash"] and not source.exists() and payload.exists() and receipt.exists()
    assert "audit unavailable <error>&" in questions[0][1] and questions[0][0] == Qt.TextFormat.PlainText


def test_close_joins_native_inverse_and_reports_late_partial_truth(window, qapp, tmp_path, monkeypatch):
    source, payload, receipt, _, calls, questions = _fixture(window, qapp, tmp_path, monkeypatch)
    entered = threading.Event()

    def partial(plan, **_kwargs):
        entered.set()
        time.sleep(0.04)
        os.rename(payload, source)
        calls.append("restore")
        return RestoreResult(True, plan.origin.path, plan.trashed, "owned late receipt error <error>&", True)

    monkeypatch.setattr(undo_worker, "restore_windows", partial)
    window._undo.undo()
    worker = window._undo.worker
    assert entered.wait(3)
    assert window.operation_busy and not window._actions["open"].isEnabled()
    window.start_scan(str(source.parent))
    assert window._worker is None, "scan cannot overlap an active inverse operation"
    window.close()
    assert not worker.isRunning() and window._undo.worker is None and worker.result.results[0].restored
    assert (source / "file").exists() and not payload.exists() and receipt.exists() and calls == ["trash", "restore"]
    assert "late receipt error <error>&" in questions[-1][1] and questions[-1][0] == Qt.TextFormat.PlainText
    qapp.processEvents()
    assert window._worker is None, "late completion never starts a rescan after close"


def test_redirect_is_an_occupied_original_and_never_grants_undo(tmp_path):
    source = tmp_path / "original"
    source.mkdir()
    origin = capture_origin(str(source), stat_snapshot(str(source)))
    # The occupied-path gate uses lexists, so an existing junction/link is refused too, without removing it.
    with pytest.raises(ValueError, match="occupied.*redirect"):
        undo_worker.prepare_undo(origin, None, threading.Event())
    assert source.is_dir()


def test_timer_expiry_rescans_parent_without_restoring_payload(window, qapp, tmp_path, monkeypatch):
    source, payload, receipt, _, calls, _ = _fixture(window, qapp, tmp_path, monkeypatch)
    window._undo.timer.timeout.emit()
    assert not window._undo.available and window._undo.button.isHidden()
    _wait(qapp, lambda: window._worker is None)
    assert calls == ["trash"] and not source.exists() and payload.exists() and receipt.exists()
    assert not window.results.tree_model.root.children


def test_late_inverse_result_never_rescans_a_replaced_tree(window, qapp, tmp_path, monkeypatch):
    source, _, _, _, calls, _ = _fixture(window, qapp, tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    native = undo_worker.restore_windows

    def blocked(plan, **kwargs):
        entered.set()
        assert release.wait(3)
        return native(plan, **kwargs)

    monkeypatch.setattr(undo_worker, "restore_windows", blocked)
    window._undo.undo()
    assert entered.wait(3)
    other = tmp_path / "other"
    other.mkdir()
    (other / "preserved").write_bytes(b"other tree")
    outcome = analyse(scan(other))
    window.results.show_outcome(outcome)
    release.set()
    _wait(qapp, lambda: window._undo.worker is None)
    assert calls == ["trash", "restore"] and source.exists()
    assert window.results.tree_model.root is outcome.result.root and window._worker is None
    assert window._undo._operation_root is None and not window._trash_rescans


def test_failed_inverse_result_journal_preserves_observed_success(window, qapp, tmp_path, monkeypatch):
    source, payload, _, _, calls, questions = _fixture(window, qapp, tmp_path, monkeypatch)
    append, counts = window._journal.append, []

    def fail_after_approval(records):
        counts.append(len(records))
        if len(counts) > 1:
            raise OSError("owned inverse result journal failure")
        append(records)

    monkeypatch.setattr(window._journal, "append", fail_after_approval)
    window._undo.undo()
    worker = window._undo.worker
    _wait(qapp, lambda: window._undo.worker is None)
    assert calls == ["trash", "restore"] and source.exists() and not payload.exists()
    assert worker.result.results[0].restored and worker.result.journal_errors
    assert "inverse result journal failure" in questions[0][1]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="native Linux current-user Trash and mount APIs")
def test_native_linux_owned_private_bin_uses_normal_gui_capture_undo_and_parent_rescan(
        window, qapp, tmp_path, monkeypatch):
    owned = tmp_path.resolve()
    data, source = owned / "data", owned / "scan" / "original"
    scope = data / "Trash"
    scope.mkdir(parents=True, mode=0o700)
    files, info = scope / "files", scope / "info"
    files.mkdir(mode=0o700)
    info.mkdir(mode=0o700)
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    (source / "empty").mkdir(parents=True)
    (source / "file").write_bytes(b"fresh native Linux GUI undo payload")
    window._journal = OperationJournal(owned / "journal")
    window.results.show_outcome(analyse(scan(source.parent)))
    payload, receipt = files / "owned-payload", info / "owned-payload.trashinfo"

    def move(path):
        assert path == str(source) and window._trash_worker._origins[path].path == path
        source.rename(payload)  # Only this newly created private fixture, never an existing user bin.
        receipt.write_text(f"[Trash Info]\nPath={quote(path)}\nDeletionDate=2026-10-08T00:00:00\n", encoding="utf-8")
        return MoveReceipt(True, str(payload))

    monkeypatch.setattr(file_actions, "trash_receipt", move)
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    window.move_to_trash(window.results.tree_model.root.children)
    _wait(qapp, lambda: window._trash_worker is None)
    assert window._undo.available and payload.exists() and receipt.exists()
    window._undo.undo()
    worker = window._undo.worker
    _wait(qapp, lambda: window._undo.worker is None)
    assert worker.result.results[0].restored and not worker.result.results[0].error
    assert (source / "file").read_bytes() == b"fresh native Linux GUI undo payload" and (source / "empty").is_dir()
    assert not payload.exists() and not receipt.exists() and files.is_dir() and info.is_dir()
    _wait(qapp, lambda: window._worker is None)
    assert window.results.tree_model.root.children[0].path == str(source)
