"""Large refusals remain complete, read-only, copyable and owned by the source window."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QShortcut, QTextDocument
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from je_file_tree.core.node import Node
from je_file_tree.core.system_files import SystemFile
from je_file_tree.gui import main_window
from je_file_tree.gui.list_transfer import ListCapture
from je_file_tree.gui.skipped_dialog import SkippedEntriesDialog
from je_file_tree.gui.tree_model import NODE_ROLE
from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414


class _CountedNode(Node):
    comparisons = 0
    __hash__ = object.__hash__

    def __eq__(self, other):
        type(self).comparisons += 1
        return self is other


def test_large_managed_refusal_is_owned_and_partitions_once(window, monkeypatch):
    nodes = [_CountedNode(f"captured-{i}", False) for i in range(96)]
    allowed = nodes[::3]
    monkeypatch.setattr(main_window, "system_file", lambda path:
                        None if int(path.rsplit("-", 1)[1]) % 3 == 0 else SystemFile("winsxs", "cleanup"))
    def no_warning(*_args):
        raise AssertionError("A large refusal must not build a giant warning label")
    monkeypatch.setattr(QMessageBox, "warning", no_warning)
    shown = []
    def inspect(dialog):
        assert dialog in window._path_dialogs and window.operation_busy
        assert callable(dialog.shutdown)
        assert dialog.model.rowCount() == 64
        assert dialog.model.row_at(0)[0] is nodes[1]
        assert dialog.model.row_at(63)[0] is nodes[95]
        assert "Windows manages this entry" in dialog.details.toPlainText()
        shown.append(1)
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(SkippedEntriesDialog, "exec", inspect)
    _CountedNode.comparisons = 0
    assert window._without_managed(nodes) == allowed
    assert _CountedNode.comparisons < len(nodes)
    assert shown == [1] and not window._path_dialogs


def test_complete_lazy_rows_literal_details_and_copy(qapp):
    nodes = [Node(f"captured-{i}", False) for i in range(10_000)]
    nodes[-1].name = "<b>資料 & filename</b>\twith\nnewline"
    rows = [(node, "system_managed") for node in nodes]
    dialog = SkippedEntriesDialog(rows)
    try:
        dialog.resize(900, 500)
        dialog.show()
        qapp.processEvents()
        assert dialog.height() <= 550 and dialog.model.rowCount() == len(nodes)
        index = dialog.model.index(len(nodes) - 1, 0)
        assert index.data() == nodes[-1].path and index.data(NODE_ROLE) is None
        tooltip = QTextDocument()
        tooltip.setHtml(index.data(Qt.ItemDataRole.ToolTipRole))
        assert nodes[-1].path in tooltip.toPlainText()
        assert not dialog.model.flags(index) & Qt.ItemFlag.ItemIsEditable
        dialog.view.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.ClearAndSelect
                                                    | QItemSelectionModel.SelectionFlag.Rows)
        dialog.view.scrollTo(index)
        assert dialog.details.toPlainText().startswith(nodes[-1].path + "\n")
        assert "Windows manages this entry" in dialog.details.toPlainText()
        QApplication.clipboard().setText("before captured refusal copy")
        dialog.view.findChild(QShortcut).activated.emit()
        _wait(qapp, lambda: QApplication.clipboard().text() != "before captured refusal copy")
        assert '<b>資料 & filename</b>\twith\nnewline' in QApplication.clipboard().text()
        assert "Windows manages this entry" in QApplication.clipboard().text()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_notice_close_cancels_pending_capture(qapp):
    dialog = SkippedEntriesDialog([(Node("captured", False), "changed")])
    capture = ListCapture(dialog.view, dialog, selected=True)
    capture.start()
    assert capture._active
    dialog.reject()
    assert not capture._active
    dialog.deleteLater()


@pytest.mark.parametrize("name", ["long-path-" * 200, "<b>literal filename</b>"])
def test_long_or_markup_like_paths_also_use_literal_table(window, monkeypatch, name):
    node = Node(name, False)
    shown = []
    def inspect(dialog):
        assert dialog.model.rowCount() == 1
        assert dialog.details.toPlainText().startswith(name + "\n")
        shown.append(1)
        return QDialog.DialogCode.Rejected
    def no_warning(*_args):
        raise AssertionError("Long or markup-like filenames must not enter automatic rich-text labels")
    monkeypatch.setattr(QMessageBox, "warning", no_warning)
    monkeypatch.setattr(SkippedEntriesDialog, "exec", inspect)
    window._show_skipped([(node, "changed")])
    assert shown == [1]


def test_owner_closing_during_refusal_does_not_ask_or_queue(window, tmp_path, monkeypatch):
    root = Node(str(tmp_path / "captured"), True, children=[])
    nodes = [Node(str(i), False, parent=root) for i in range(12)]
    root.children.extend(nodes)
    window.results.tree_model.set_root(root)
    monkeypatch.setattr(main_window, "system_file", lambda path:
                        None if path == nodes[-1].path else SystemFile("winsxs", "cleanup"))
    questions = []
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: questions.append(1))
    def close_owner(_dialog):
        window._closing = True
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(SkippedEntriesDialog, "exec", close_owner)
    try:
        window.move_to_trash(nodes)
        assert not questions and window._trash_worker is None and not window._path_dialogs
        assert root.children == nodes
    finally:
        window._closing = False
