"""Cross-drive review lifetime and final copy gates use only disposable fixtures, never real Trash."""

import os
import threading

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QMenu, QMessageBox

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core import verified_copy
from je_file_tree.core.copy_approval import CopyApproval
from je_file_tree.core.operations import MoveReceipt
from je_file_tree.core.scanner import scan
from je_file_tree.gui import copy_dialog, main_window, trash_worker
from je_file_tree.gui.copy_dialog import CopyDialog, CopyPreviewWorker
from je_file_tree.gui.scan_worker import analyse


def _fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(verified_copy, "protected_places", lambda: ())
    source, destination = tmp_path.resolve() / "source", tmp_path.resolve() / "destination"
    (source / "folder" / "empty").mkdir(parents=True)
    destination.mkdir()
    (source / "folder" / "file").write_bytes(b"payload")
    root = scan(source).root
    return root, source, destination


def _dialog(window, qapp, tmp_path, monkeypatch):
    root, source, destination = _fixture(tmp_path, monkeypatch)
    # Portable lifetime tests reuse same-volume fixtures; a separate test exercises the GUI refusal.
    monkeypatch.setattr(CopyPreviewWorker, "_prepare", lambda self, request: verified_copy.prepare_copy(
        request.root, request.nodes, request.directory, collision=request.collision, cancel=self.cancel))
    dialog = CopyDialog(root, root.children, "auto", window)
    dialog.destination.setText(str(destination))
    dialog._query()
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    return dialog, source, destination


def test_preview_refuses_same_volume_and_no_automatic_source_trash(window, qapp, tmp_path, monkeypatch):
    root, source, destination = _fixture(tmp_path, monkeypatch)
    dialog = CopyDialog(root, root.children, "auto", window)
    dialog.destination.setText(str(destination))
    dialog._query()
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    assert dialog.plan.items[0].reason == "same_volume" and not dialog.apply_button.isEnabled()
    assert not dialog.redirect.isChecked() and not dialog.finish_button.isEnabled()
    assert (source / "folder" / "file").read_bytes() == b"payload" and not list(destination.iterdir())
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)


def test_confirmed_copy_freezes_options_and_requires_separate_finish(window, qapp, tmp_path, monkeypatch):
    dialog, source, destination = _dialog(window, qapp, tmp_path, monkeypatch)
    questions = []

    def answer(question):
        questions.append((question.textFormat(), question.defaultButton().text(), question.detailedText()))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "exec", answer)
    dialog.redirect.setChecked(True)
    assert dialog.plan is None
    dialog._query()
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    dialog._apply()
    _wait(qapp, lambda: dialog.operation is not None and not dialog.operation.isRunning()
          and dialog.finish_button.isEnabled())
    assert questions[0][:2] == (Qt.TextFormat.PlainText, "&No")
    assert str(source / "folder") in questions[0][2] and str(destination / "folder") in questions[0][2]
    assert dialog.approval.redirect and not dialog.redirect.isEnabled() and not dialog.finish_requested
    assert dialog.operation.refreshed == [(str(destination), 1, 0)]
    assert (source / "folder" / "file").read_bytes() == (destination / "folder" / "file").read_bytes()
    dialog._finish()
    assert dialog.finish_requested and dialog._closed and not dialog.operation.isRunning()
    assert (source / "folder").is_dir()


def test_partial_failure_is_visible_and_cannot_offer_original_trash(window, qapp, tmp_path, monkeypatch):
    dialog, source, destination = _dialog(window, qapp, tmp_path, monkeypatch)

    def failed(*_args, **_kwargs):
        raise PermissionError("<locked>& permission denied")

    monkeypatch.setattr(verified_copy, "copy_file", failed)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog._apply()
    _wait(qapp, lambda: dialog.operation is not None and not dialog.operation.isRunning()
          and "failed: 1" in dialog.status.text())
    assert "<locked>& permission denied" in dialog.output.toPlainText()
    assert str(destination / "folder") in dialog.output.toPlainText()
    assert not dialog.finish_button.isEnabled() and dialog.approval is None
    assert (source / "folder" / "file").read_bytes() == b"payload"
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)


def test_close_joins_and_reports_retained_partial_paths(window, qapp, tmp_path, monkeypatch):
    dialog, source, destination = _dialog(window, qapp, tmp_path, monkeypatch)
    entered, questions = threading.Event(), []
    item = dialog.plan.items[0]

    def waiting(_plan, *, cancel, progress):
        entered.set()
        assert cancel.wait(10)
        return verified_copy.CopyResult(failed=[(item, "canceled <copy>")],
                                        partial=[item.destination], canceled=True)

    monkeypatch.setattr(copy_dialog, "copy_folders", waiting)
    monkeypatch.setattr(QMessageBox, "exec", lambda question: questions.append(question.detailedText())
                        or QMessageBox.StandardButton.Yes)
    dialog._apply()
    _wait(qapp, entered.is_set)
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    assert len(questions) == 2 and str(destination / "folder") in questions[1]
    assert not dialog.operation.isRunning() and dialog.operation.result.canceled and dialog.approval is None
    assert (source / "folder" / "file").read_bytes() == b"payload"


def _worker(root, proof, monkeypatch, mover, *, redirect=False):
    monkeypatch.setattr(trash_worker.file_actions, "trash_receipt", mover)
    worker = trash_worker.TrashWorker(root, [proof.item.node], [], {proof.item.node: None})
    worker.copy_approval = CopyApproval((proof,), redirect)
    results = []
    worker.done.connect(results.append)
    worker.run()
    return results[0]


def test_final_rehash_blocks_changed_copy_and_preserves_original(tmp_path, monkeypatch):
    root, source, destination = _fixture(tmp_path, monkeypatch)
    proof = verified_copy.copy_folders(verified_copy.prepare_copy(root, root.children, str(destination))).verified[0]
    copied = destination / "folder" / "file"
    info = copied.stat()
    copied.write_bytes(b"changed")
    os.utime(copied, ns=(info.st_atime_ns, info.st_mtime_ns))
    calls = []
    result = _worker(root, proof, monkeypatch, lambda path: calls.append(path) or True)
    assert not calls and not result.moved and result.failed == [proof.item.node]
    assert result.copy_errors[0][:3] == (str(source / "folder"), str(destination / "folder"), "verify")
    assert (source / "folder" / "file").read_bytes() == b"payload"


def test_failed_trash_never_creates_redirect_and_rejects_unrelated_proof(tmp_path, monkeypatch):
    root, source, destination = _fixture(tmp_path, monkeypatch)
    proof = verified_copy.copy_folders(verified_copy.prepare_copy(root, root.children, str(destination))).verified[0]
    result = _worker(root, proof, monkeypatch, lambda _path: MoveReceipt(False), redirect=True)
    assert not result.moved and result.failed == [proof.item.node] and not result.copy_errors
    assert not scan(source).root.children[0].is_link
    assert not CopyApproval((proof, proof)).matches(root, root.children)
    assert not CopyApproval((proof,)).matches(scan(source).root, root.children)


def test_copy_trash_confirmation_is_default_no_with_all_frozen_paths(window, tmp_path, monkeypatch):
    root, _source, destination = _fixture(tmp_path, monkeypatch)
    proof = verified_copy.copy_folders(verified_copy.prepare_copy(root, root.children, str(destination))).verified[0]
    questions = []
    monkeypatch.setattr(QMessageBox, "exec", lambda question: questions.append(
        (question.defaultButton().text(), question.textFormat(), question.text(), question.detailedText()))
        or QMessageBox.StandardButton.No)
    assert window._confirm_copy_trash(root.children, CopyApproval((proof,), True)) == QMessageBox.StandardButton.No
    assert questions[0][:2] == ("&No", Qt.TextFormat.PlainText)
    assert proof.item.source in questions[0][3] and proof.item.destination in questions[0][3]
    assert "64 MiB" in questions[0][2] and "junction/symbolic link" in questions[0][2]


def test_main_close_joins_owned_copy_and_suppresses_post_close_trash(window, qapp, tmp_path, monkeypatch):
    dialog, source, _destination = _dialog(window, qapp, tmp_path, monkeypatch)
    entered = threading.Event()

    def waiting(_plan, *, cancel, progress):
        entered.set()
        assert cancel.wait(10)
        return verified_copy.CopyResult(canceled=True)

    monkeypatch.setattr(copy_dialog, "copy_folders", waiting)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog._apply()
    _wait(qapp, entered.is_set)
    window._path_dialogs.add(dialog)
    window.close()
    assert dialog._closed and not dialog.operation.isRunning() and not dialog.finish_requested
    assert (source / "folder" / "file").read_bytes() == b"payload"
    window._path_dialogs.discard(dialog)


def test_main_close_surfaces_final_copy_gate_failure_received_during_join(window, qapp, tmp_path, monkeypatch):
    root, source, destination = _fixture(tmp_path, monkeypatch)
    proof = verified_copy.copy_folders(verified_copy.prepare_copy(root, root.children, str(destination))).verified[0]
    entered, questions, moves = threading.Event(), [], []

    def waiting(_proof, *, cancel):
        entered.set()
        assert cancel.wait(10)
        raise ValueError("closed <verification> retained")

    monkeypatch.setattr(trash_worker, "verify_copy", waiting)
    monkeypatch.setattr(trash_worker.file_actions, "trash_receipt", lambda path: moves.append(path) or True)
    monkeypatch.setattr(QMessageBox, "exec", lambda question: questions.append(
        (question.detailedText(), question.textFormat())) or QMessageBox.StandardButton.Ok)
    worker = trash_worker.TrashWorker(root, [proof.item.node], [], {proof.item.node: None}, window)
    worker.copy_approval = CopyApproval((proof,))
    window._trash_worker = worker
    worker.start()
    _wait(qapp, entered.is_set)
    window.close()
    assert not worker.isRunning() and worker.result.copy_errors and not moves
    assert window._trash_worker is None and len(questions) == 1
    assert "closed <verification> retained" in questions[0][0] and questions[0][1] == Qt.TextFormat.PlainText
    assert (source / "folder" / "file").read_bytes() == b"payload"


def test_successful_trash_can_create_exclusive_native_redirect(tmp_path, monkeypatch):
    root, source, destination = _fixture(tmp_path, monkeypatch)
    proof = verified_copy.copy_folders(verified_copy.prepare_copy(root, root.children, str(destination))).verified[0]
    owned_bin = tmp_path / "owned-bin"

    def move(path):
        os.rename(path, owned_bin)
        return MoveReceipt(True, str(owned_bin))

    result = _worker(root, proof, monkeypatch, move, redirect=True)
    assert result.moved == [proof.item.node] and not result.copy_errors
    assert result.destinations[proof.item.node] == str(owned_bin)
    assert (source / "folder" / "file").read_bytes() == b"payload" and (owned_bin / "file").read_bytes() == b"payload"
    link = scan(source).root.children[0]
    assert link.is_link and not link.children


def test_redirect_collision_preserves_arrival_and_successful_trash_receipt(tmp_path, monkeypatch):
    root, source, destination = _fixture(tmp_path, monkeypatch)
    proof = verified_copy.copy_folders(verified_copy.prepare_copy(root, root.children, str(destination))).verified[0]
    owned_bin = tmp_path / "owned-bin"

    def move(path):
        os.rename(path, owned_bin)
        (source / "folder").mkdir()
        (source / "folder" / "new-arrival").write_bytes(b"retain")
        return MoveReceipt(True, str(owned_bin))

    result = _worker(root, proof, monkeypatch, move, redirect=True)
    assert result.moved == [proof.item.node] and not result.failed
    assert result.copy_errors[0][2] == "redirect"
    assert (source / "folder" / "new-arrival").read_bytes() == b"retain"
    assert (owned_bin / "file").read_bytes() == (destination / "folder" / "file").read_bytes() == b"payload"


def test_shared_menu_passes_frozen_proofs_before_rescan(window, tmp_path, monkeypatch):
    root, _source, destination = _fixture(tmp_path, monkeypatch)
    proof = verified_copy.copy_folders(verified_copy.prepare_copy(root, root.children, str(destination))).verified[0]
    outcome = analyse(scan(root.path))
    window.results.show_outcome(outcome)
    root = outcome.result.root
    events = []

    class Dialog:
        changed = finish_requested = True
        approval = CopyApproval((proof,))
        def __init__(self, scope, nodes, _unit, _parent):
            events.append((scope, tuple(nodes)))
        def exec(self):
            return 0
        def shutdown(self):
            events.append("joined")
        def deleteLater(self):  # noqa: N802 - Qt API
            events.append("deleted")

    class ChoosingMenu(QMenu):
        def exec(self, _point):
            next(action for action in self.actions() if action.text() == "Move to another drive…").trigger()

    monkeypatch.setattr(main_window, "CopyDialog", Dialog)
    monkeypatch.setattr(main_window, "QMenu", ChoosingMenu)
    monkeypatch.setattr(window, "move_to_trash", lambda nodes, *, copies: events.append(("trash", nodes, copies)))
    monkeypatch.setattr(window, "rescan_folder", lambda parent: events.append(("rescan", parent)))
    monkeypatch.setattr(window._bin_labels, "refresh", lambda: None)
    window.show_menu_for(root.children[0], root.children, QPoint())
    assert events[1:3] == ["joined", "deleted"] and events[3] == ("trash", [proof.item.node], Dialog.approval)
    assert events[4] == ("rescan", root)
    window.show_copy([root])
    assert len(events) == 5
