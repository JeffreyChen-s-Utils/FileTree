"""Complete failure diagnostics retain observed processes and query uncertainty without source actions."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QDialog, QMessageBox

from je_file_tree.core.lock_holders import Holder, LockReport
from je_file_tree.core.node import Node
from je_file_tree.core.operations import MoveResult
from je_file_tree.gui.failed_dialog import FailedEntriesDialog
from je_file_tree.gui.tree_model import NODE_ROLE
from test_gui import window as window  # noqa: PLC0414


def test_report_preserves_all_observations_errors_and_missing_visibility(qapp):
    nodes = [Node("<b>literal path</b>\twith\nnewline", False), Node("none-observed", False),
             Node("not-queried", False)]
    holders = [Holder(100 + i, f"Observed-{i}") for i in range(12)]
    error = "captured <query> & error\twith\nnewline"
    report = LockReport(holders, incomplete=True, error=error)
    dialog = FailedEntriesDialog(nodes, {nodes[0]: report, nodes[1]: LockReport()})
    try:
        assert dialog.model.rowCount() == 3
        text = dialog.details.toPlainText()
        assert nodes[0].path in text and error in text
        for holder in holders:
            assert holder.name in text and str(holder.pid) in text
        assert "unknown" in text and "query error" in text
        tooltip = QTextDocument()
        tooltip.setHtml(dialog.model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole))
        assert nodes[0].path in tooltip.toPlainText() and error in tooltip.toPlainText()
        assert dialog.model.index(0, 0).data(NODE_ROLE) is None
        assert "unknown" not in dialog.model.index(1, 1).data()
        assert "unknown" in dialog.model.index(2, 1).data()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_large_report_uses_owned_lazy_table_and_retains_last_failure(window, monkeypatch):
    nodes = [Node(f"captured-{i}", False) for i in range(1000)]
    report = LockReport([Holder(7, "Observed app")], incomplete=True, error="captured query error")
    result = MoveResult(failed=nodes, holders={node: report for node in nodes})
    def no_warning(*_args):
        raise AssertionError("Large failure diagnostics must not become one warning label")
    monkeypatch.setattr(QMessageBox, "warning", no_warning)
    shown = []
    def inspect(dialog):
        assert dialog in window._path_dialogs and window.operation_busy
        assert dialog.model.rowCount() == len(nodes)
        last = dialog.model.index(len(nodes) - 1, 0)
        dialog.view.setCurrentIndex(last)
        assert last.data() == nodes[-1].path and report.error in dialog.details.toPlainText()
        shown.append(1)
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(FailedEntriesDialog, "exec", inspect)
    window._show_failed(result)
    assert shown == [1] and not window._path_dialogs and window._trash_worker is None


def test_brief_complete_report_keeps_existing_warning(window, monkeypatch):
    node = Node("captured", False)
    result = MoveResult(failed=[node], holders={node: LockReport([Holder(7, "Observed app")])})
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(_args[-1]))
    window._show_failed(result)
    assert len(warnings) == 1 and node.name in warnings[0] and "Observed app" in warnings[0]
    assert not window._path_dialogs and window._trash_worker is None


@pytest.mark.parametrize("kind", ["many_holders", "query_error", "long_path", "markup"])
def test_small_reports_cannot_omit_or_interpret_diagnostic_text(window, monkeypatch, kind):
    node = Node("captured", False)
    report = LockReport([Holder(7, "Observed app")])
    if kind == "many_holders":
        report.holders = [Holder(i, f"Observed-{i}") for i in range(12)]
    elif kind == "query_error":
        report.error = "captured diagnostic detail"
    elif kind == "long_path":
        node.name *= 300
    else:
        report.holders = [Holder(7, "<b>Observed app</b>")]
    def inspect(dialog):
        assert report.holders[-1].name in dialog.details.toPlainText()
        if report.error:
            assert report.error in dialog.details.toPlainText()
        return QDialog.DialogCode.Rejected
    def no_warning(*_args):
        raise AssertionError("Non-brief failure details require a complete literal report")
    monkeypatch.setattr(FailedEntriesDialog, "exec", inspect)
    monkeypatch.setattr(QMessageBox, "warning", no_warning)
    window._show_failed(MoveResult(failed=[node], holders={node: report}))
    assert not window._path_dialogs
