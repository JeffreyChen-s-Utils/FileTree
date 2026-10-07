"""Compression previews retain exact Node routing and cancellation/close ownership."""

import threading

from PySide6.QtCore import Qt

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core.compression import CompressionPlan
from je_file_tree.core.compression_ops import CompressionResult
from je_file_tree.core.scanner import scan
from je_file_tree.gui import compression as gui
from je_file_tree.gui.compression import CompressionDialog
from je_file_tree.gui import main_window
from je_file_tree.gui import compression_worker
from PySide6.QtWidgets import QMessageBox
from je_file_tree.gui.scan_worker import analyse
from types import SimpleNamespace


def test_preview_is_read_only_and_selects_exact_recorded_node(window, qapp, sample_tree, monkeypatch):
    root = scan(sample_tree).root
    node = next(node for node in root.iter_files() if node.name == "notes.txt")
    plan = CompressionPlan(root, [node], 1, node.size, node.allocated, 6, 1, True, "NTFS", 4096)
    monkeypatch.setattr(gui, "compression_plan", lambda _root, **_kwargs: plan)
    dialog = CompressionDialog(root, "auto", window, partial=True)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    assert "NTFS" in dialog.status.text() and "Incomplete" in dialog.status.text()
    assert "0–" in dialog.status.text() and dialog.status.textFormat() == Qt.TextFormat.PlainText
    assert not dialog.model.flags(dialog.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    selected = []
    dialog.selected.connect(selected.append)
    dialog._select(dialog.proxy.index(0, 0))
    assert selected == [node] and not dialog.worker.isRunning() and (sample_tree / "notes.txt").exists()
    dialog.deleteLater()


def test_stop_close_joins_preview_and_ignores_late_result(window, qapp, sample_tree, monkeypatch):
    entered = threading.Event()
    root = scan(sample_tree).root
    plan = CompressionPlan(root, [], 0, 0, 0, 6, 0, False, None, None)
    def waiting(_root, *, cancel):
        entered.set()
        assert cancel.wait(10)
        return plan
    monkeypatch.setattr(gui, "compression_plan", waiting)
    dialog = CompressionDialog(root, "auto", window)
    _wait(qapp, entered.is_set)
    dialog.stop_button.click()
    dialog.reject()
    dialog._show(plan)
    assert not dialog.worker.isRunning() and dialog.plan is None and dialog.model.rowCount() == 0
    dialog.deleteLater()


def test_main_preview_route_rejects_detached_nonfolder_and_unsupported_scopes(window, sample_tree, monkeypatch):
    root = scan(sample_tree).root
    window.results.show_outcome(analyse(scan(sample_tree)))
    current = window.results.outcome.result.root
    calls = []
    class Dialog:
        selected = SimpleNamespace(connect=lambda _callback: None)
        changed = False
        def __init__(self, node, unit, parent, **_kwargs):
            calls.append((node, unit, parent))
        def exec(self):
            return 0
        def shutdown(self):
            calls.append("joined")
        def deleteLater(self):  # noqa: N802 - mirrors Qt's public API
            assert calls[-1] == "joined"
    monkeypatch.setattr(main_window, "CompressionDialog", Dialog)
    monkeypatch.setattr(main_window.elevation, "supported", lambda: True)
    window.show_compression(root)  # A detached scan of the same path is not the displayed result.
    window.show_compression(next(current.iter_files()))
    assert not calls
    window.show_compression(current)
    assert calls == [(current, window._unit, window), "joined"]
    monkeypatch.setattr(main_window.elevation, "supported", lambda: False)
    window.show_compression(current)
    assert len(calls) == 2


def test_confirmed_operation_captures_only_listed_files_and_reports_partial_result(
        window, qapp, sample_tree, monkeypatch):
    root = scan(sample_tree).root
    node = next(node for node in root.iter_files() if node.name == "notes.txt")
    plan = CompressionPlan(root, [node], 2, node.size, node.allocated, 6, 0, False, "NTFS", 4096)
    monkeypatch.setattr(gui, "compression_plan", lambda *_args, **_kwargs: plan)
    questions, operations = [], []
    def answer(question):
        questions.append((question.defaultButton().text(), question.text(), question.textFormat()))
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "exec", answer)
    def run(scope, files, mode, **_kwargs):
        operations.append((scope, files, mode))
        return CompressionResult(1, 0, 4096, 4096, 0, ((node.path, "<error>"),), True)
    monkeypatch.setattr(compression_worker, "compress_files", run)
    dialog = CompressionDialog(root, "auto", window)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    dialog.apply_button.click()
    _wait(qapp, lambda: dialog.operation is not None and not dialog.operation.isRunning()
          and "Stopped" in dialog.status.text())
    assert operations == [(root, (node,), "ntfs")]
    assert questions[0][0] == "&No" and "1 listed files" in questions[0][1]
    assert questions[0][2] == Qt.TextFormat.PlainText
    assert "<error>" in dialog.output.toPlainText() and dialog.changed
    assert not dialog.mode.isEnabled() and not dialog.apply_button.isEnabled()
    dialog.reject()
    dialog.deleteLater()


def test_declined_operation_and_close_cancel_joins_owned_command(window, qapp, sample_tree, monkeypatch):
    root = scan(sample_tree).root
    node = next(node for node in root.iter_files() if node.name == "notes.txt")
    plan = CompressionPlan(root, [node], 1, node.size, node.allocated, 6, 0, False, "NTFS", 4096)
    monkeypatch.setattr(gui, "compression_plan", lambda *_args, **_kwargs: plan)
    entered = threading.Event()
    def run(_root, _files, _mode, *, cancel, progress):
        entered.set()
        assert cancel.wait(10)
        return CompressionResult(1, 0, 0, 0, 1, (), True)
    monkeypatch.setattr(compression_worker, "compress_files", run)
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.No)
    dialog = CompressionDialog(root, "auto", window)
    _wait(qapp, lambda: dialog.plan is not None and not dialog.worker.isRunning())
    dialog._apply()
    assert not dialog.changed and dialog.operation is None
    monkeypatch.setattr(QMessageBox, "exec", lambda _question: QMessageBox.StandardButton.Yes)
    dialog._apply()
    _wait(qapp, entered.is_set)
    dialog.reject()
    assert dialog.operation.cancel.is_set() and not dialog.operation.isRunning()
    assert dialog._closed and dialog.changed
    dialog.deleteLater()


def test_main_rescans_attempted_scope_with_exact_allocation(window, sample_tree, monkeypatch):
    window.results.show_outcome(analyse(scan(sample_tree)))
    root = window.results.outcome.result.root
    rescans = []
    class Dialog:
        selected = SimpleNamespace(connect=lambda _callback: None)
        changed = True
        def __init__(self, *_args, **_kwargs):
            pass
        def exec(self):
            return 0
        def shutdown(self):
            pass
        def deleteLater(self):  # noqa: N802 - mirrors Qt API
            pass
    monkeypatch.setattr(main_window, "CompressionDialog", Dialog)
    monkeypatch.setattr(main_window.elevation, "supported", lambda: True)
    monkeypatch.setattr(window, "rescan_folder", lambda node, **kwargs: rescans.append((node, kwargs)))
    window._actions["exact_allocation"].setChecked(False)
    window.show_compression(root)
    assert rescans == [(root, {"exact_allocation": True})]
    assert window._scan_options(exact_allocation=True).exact_windows_allocation
    assert not window._scan_options().exact_windows_allocation
