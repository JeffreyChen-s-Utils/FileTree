"""The review queue is mandatory for cleanup and preserves unchecked/protected entries."""

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from je_file_tree.core.protected import PROGRAMS, Protection
from je_file_tree.core.scanner import scan
from je_file_tree.gui.cleanup_review import CleanupReview
from je_file_tree.gui import file_actions
from test_gui import _wait


def test_review_collapses_children_and_shows_protection_and_consequences(qapp, tmp_path: Path, monkeypatch) -> None:
    folder = tmp_path / "node_modules"
    folder.mkdir()
    (folder / "file").write_bytes(b"data")
    (tmp_path / "safe.dmp").write_bytes(b"dump")
    root = scan(tmp_path).root
    by_name = {node.name: node for node in root.children}
    protected = by_name["node_modules"]
    safe = by_name["safe.dmp"]
    guard = Protection(protected.path, PROGRAMS)
    dialog = CleanupReview([protected, protected.children[0], safe],
                           {protected: "build_output", safe: "crash_dumps"}, [guard], "B", root)
    try:
        assert dialog.model.rowCount() == 2
        assert dialog.model.data(dialog.model.index(0, 1)) == protected.path
        assert dialog.model.data(dialog.model.index(0, 7)) == "installed programs"
        assert "building the project again" in dialog.model.data(dialog.model.index(0, 8))
        assert dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        _wait(qapp, lambda: "1 entries" in dialog.summary.text() and "free now" in dialog.summary.text())
        assert dialog.selected_nodes() == [safe]
        assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        assert "0–" in dialog.summary.text() and "Moving to Trash does not free space" in dialog.summary.text()
        opened = []
        monkeypatch.setattr(file_actions, "reveal_in_file_manager", lambda path: opened.append(path) or True)
        dialog.view.setCurrentIndex(dialog.model.index(1, 1))
        dialog._open_folder()
        assert opened == [safe.path]
        dialog.reject()
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert (folder / "file").read_bytes() == b"data"
    finally:
        dialog.shutdown()
        dialog.deleteLater()


def test_unchecking_every_entry_disables_continue(qapp, tmp_path: Path) -> None:
    (tmp_path / "file").write_bytes(b"data")
    root = scan(tmp_path).root
    dialog = CleanupReview(root.children, {}, [], "B", root)
    try:
        dialog.show()
        qapp.processEvents()
        index = dialog.model.index(0, 0)
        rect = dialog.view.visualRect(index)
        QTest.mouseClick(dialog.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(10, rect.center().y()))
        assert dialog.model.data(index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked
        _wait(qapp, lambda: "free now" in dialog.summary.text())
        assert dialog.selected_nodes() == []
        assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    finally:
        dialog.shutdown()
        dialog.deleteLater()
