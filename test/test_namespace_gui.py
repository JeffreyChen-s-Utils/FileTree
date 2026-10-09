"""Explicit namespace approvals, frozen options, native owned moves and safe dialog lifetime."""

import threading
from types import SimpleNamespace

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import QMenu, QMessageBox

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core import namespace_moves
from je_file_tree.core.namespace_moves import NamespaceResult
from je_file_tree.core.scanner import scan
from je_file_tree.gui import main_window, namespace_worker
from je_file_tree.gui.namespace_dialog import NamespaceDialog
from je_file_tree.gui.scan_worker import analyse


def _dialog(window, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(namespace_moves, "protected_places", lambda: ())
    source, target = tmp_path.resolve() / "source", tmp_path.resolve() / "target"
    source.mkdir()
    target.mkdir()
    (source / "reviewed.txt").write_bytes(b"payload")
    root = scan(source).root
    dialog = NamespaceDialog(root, root.children, "auto", window, rename=False)
    dialog.destination.setText(str(target))
    dialog._query()
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    return dialog, source, target


def test_close_waits_asynchronously_for_native_work_and_retains_source_exclusion(
        window, qapp, tmp_path, monkeypatch):
    dialog, source, target = _dialog(window, qapp, tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    finished = []

    def held(_plan, *, cancel, progress):
        entered.set()
        release.wait(5)
        return NamespaceResult(canceled=cancel.is_set())

    monkeypatch.setattr(namespace_worker, "execute_namespace", held)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    window._path_dialogs.add(dialog)
    dialog.finished.connect(finished.append)
    dialog.finished.connect(lambda _code: window._path_dialogs.discard(dialog))
    dialog.show()
    try:
        dialog._apply()
        _wait(qapp, entered.is_set)
        dialog.reject()
        dialog.accept()  # Repeated input must not replace the pending rejection.
        assert not finished and dialog._finish_waiting and dialog.isVisible()
        assert dialog.operation.cancel.is_set() and window.operation_busy
        window.start_scan(str(source))
        assert window._worker is None
        QTimer.singleShot(20, release.set)
        _wait(qapp, lambda: bool(finished))
        assert finished == [NamespaceDialog.DialogCode.Rejected]
        assert dialog.operation.wait(0) and dialog.operation.result.canceled
        assert not window.operation_busy and not dialog.isVisible()
        assert (source / "reviewed.txt").read_bytes() == b"payload" and not list(target.iterdir())
    finally:
        release.set()
        dialog.shutdown()
        window._path_dialogs.discard(dialog)


def test_preview_replacement_coalesces_behind_canceled_native_reads(window, qapp, tmp_path, monkeypatch):
    (tmp_path / "kept").write_bytes(b"kept")
    root = scan(tmp_path).root
    entered, release = threading.Event(), threading.Event()
    requests = []
    original = namespace_worker.prepare_namespace

    def held(scope, nodes, **options):
        requests.append(options["pattern"])
        if len(requests) == 1:
            entered.set()
            release.wait(5)
        return original(scope, nodes, **options)

    monkeypatch.setattr(namespace_worker, "prepare_namespace", held)
    dialog = NamespaceDialog(root, root.children, "auto", window, rename=True)
    try:
        _wait(qapp, entered.is_set)
        dialog.destination.setText("middle-{name}")
        dialog._query()
        dialog.destination.setText("last-{name}")
        dialog._query()
        assert len(requests) == 1 and dialog.plan is None
        QTimer.singleShot(20, release.set)
        _wait(qapp, lambda: dialog.plan is not None)
        assert len(requests) == 2 and requests[-1] == "last-{name}"
        assert dialog.plan.items[0].destination.endswith("last-kept")
        assert (tmp_path / "kept").read_bytes() == b"kept"
    finally:
        release.set()
        dialog.shutdown()


def test_preview_plain_paths_decline_and_option_invalidation(window, qapp, tmp_path, monkeypatch):
    dialog, source, target = _dialog(window, qapp, tmp_path, monkeypatch)
    assert dialog.model.rowCount() == 1 and dialog.apply_button.isEnabled()
    assert dialog.model.data(dialog.model.index(0, 0)) == "reviewed.txt"
    assert dialog.model.data(dialog.model.index(0, 2)) == "reviewed.txt"
    assert not dialog.model.flags(dialog.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    questions = []

    def decline(question):
        questions.append((question.textFormat(), question.defaultButton().text(), question.detailedText()))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "exec", decline)
    dialog._apply()
    assert questions[0][:2] == (Qt.TextFormat.PlainText, "&No")
    assert str(source / "reviewed.txt") in questions[0][2] and str(target / "reviewed.txt") in questions[0][2]
    assert dialog.operation is None and not dialog.changed
    dialog.collision.setCurrentIndex(1)
    assert dialog.plan is None and not dialog.apply_button.isEnabled()
    assert (source / "reviewed.txt").read_bytes() == b"payload" and not list(target.iterdir())
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)


def test_actual_confirmed_move_rescans_external_parent(window, qapp, tmp_path, monkeypatch):
    dialog, source, target = _dialog(window, qapp, tmp_path, monkeypatch)
    approved = dialog.plan
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog._apply()
    _wait(qapp, lambda: dialog.operation is not None and not dialog.operation.isRunning()
          and "Moved/renamed: 1" in dialog.status.text())
    assert dialog.operation.plan is approved and dialog.changed
    assert dialog.operation.refreshed == [(str(target), 1, 0)]
    assert not (source / "reviewed.txt").exists() and (target / "reviewed.txt").read_bytes() == b"payload"
    assert not dialog.destination.isEnabled() and not dialog.preview_button.isEnabled()
    assert str(target) in dialog.output.toPlainText()
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)


def test_stop_close_joins_and_suppresses_late_preview(window, qapp, tmp_path, monkeypatch):
    (tmp_path / "file").write_bytes(b"data")
    root = scan(tmp_path).root
    entered = threading.Event()

    def waiting(_root, _nodes, **kwargs):
        entered.set()
        assert kwargs["cancel"].wait(10)
        return SimpleNamespace(items=())

    monkeypatch.setattr(namespace_worker, "prepare_namespace", waiting)
    dialog = NamespaceDialog(root, root.children, "auto", window, rename=True)
    _wait(qapp, entered.is_set)
    dialog.stop()
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    dialog._show(SimpleNamespace(items=()))
    assert not dialog.worker.isRunning() and dialog.plan is None and dialog._closed
    assert dialog.model.rowCount() == 0 and (tmp_path / "file").read_bytes() == b"data"


def test_operation_close_cancels_and_retains_result_without_late_ui(window, qapp, tmp_path, monkeypatch):
    dialog, source, _ = _dialog(window, qapp, tmp_path, monkeypatch)
    entered = threading.Event()

    def waiting(_plan, *, cancel, progress):
        entered.set()
        assert cancel.wait(10)
        return NamespaceResult(canceled=True)

    monkeypatch.setattr(namespace_worker, "execute_namespace", waiting)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog._apply()
    _wait(qapp, entered.is_set)
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    before = dialog.status.text()
    dialog._completed(NamespaceResult())
    assert dialog.status.text() == before and not dialog.operation.isRunning()
    assert dialog.operation.result.canceled and dialog.changed
    assert (source / "reviewed.txt").read_bytes() == b"payload"


def test_error_paths_are_plain_and_actual_outcomes_visible(window, qapp, tmp_path, monkeypatch):
    dialog, _, _ = _dialog(window, qapp, tmp_path, monkeypatch)
    item = dialog.plan.items[0]
    monkeypatch.setattr(namespace_worker, "execute_namespace", lambda *_args, **_kwargs:
                        NamespaceResult(failed=[(item, "<locked>& denied")]))
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog._apply()
    _wait(qapp, lambda: dialog.operation is not None and not dialog.operation.isRunning()
          and "failed: 1" in dialog.status.text())
    assert "<locked>& denied" in dialog.output.toPlainText()
    assert dialog.status.textFormat() == Qt.TextFormat.PlainText
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)


def test_shared_context_menu_routes_exact_selection_and_rescans_after_join(
        window, sample_tree, monkeypatch):
    outcome = analyse(scan(sample_tree))
    window.results.show_outcome(outcome)
    root = outcome.result.root
    node = next(root.iter_files())
    events = []

    class Dialog:
        changed = True
        def __init__(self, scope, nodes, _unit, _parent, *, rename):
            events.append((scope, tuple(nodes), rename))
        def exec(self):
            return 0
        def shutdown(self):
            events.append("joined")
        def deleteLater(self):  # noqa: N802 - Qt API
            events.append("deleted")

    monkeypatch.setattr(main_window, "NamespaceDialog", Dialog)
    monkeypatch.setattr(window, "rescan_folder", lambda parent: events.append(("rescan", parent)))
    monkeypatch.setattr(window._bin_labels, "refresh", lambda: None)

    class ChoosingMenu(QMenu):
        def exec(self, _point):
            next(action for action in self.actions() if action.text() == "Rename…").trigger()

    monkeypatch.setattr(main_window, "QMenu", ChoosingMenu)
    window.show_menu_for(node, [node], QPoint())
    assert events == [(root, (node,), True), "joined", "deleted", ("rescan", root)]
    detached = next(scan(sample_tree).root.iter_files())
    window.show_namespace([detached])
    window.show_namespace([root])
    assert len(events) == 4


def test_close_reports_failures_received_while_joining(window, qapp, tmp_path, monkeypatch):
    dialog, _, _ = _dialog(window, qapp, tmp_path, monkeypatch)
    item = dialog.plan.items[0]
    entered = threading.Event()
    questions = []

    def answer(question):
        questions.append((question.text(), question.detailedText(), question.textFormat()))
        return QMessageBox.StandardButton.Yes

    def waiting(_plan, *, cancel, progress):
        entered.set()
        assert cancel.wait(10)
        return NamespaceResult(failed=[(item, "retained <destination>")], canceled=True)

    monkeypatch.setattr(namespace_worker, "execute_namespace", waiting)
    monkeypatch.setattr(QMessageBox, "exec", answer)
    dialog._apply()
    _wait(qapp, entered.is_set)
    dialog.reject()
    _wait(qapp, lambda: not dialog._finish_waiting)
    assert not dialog.operation.isRunning() and len(questions) == 2
    assert "retained <destination>" in questions[1][1] and item.source in questions[1][1]
    assert questions[1][2] == Qt.TextFormat.PlainText
    dialog.shutdown()
    assert len(questions) == 2
