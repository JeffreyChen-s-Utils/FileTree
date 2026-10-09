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
from test_cleanup import age_tree


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
        assert dialog.selected_nodes() == [], "uncertain rules must start unchecked"
        dialog.model.setData(dialog.model.index(1, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
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


def test_bulk_selection_contains_only_lower_risk_groups_and_keeps_manual_unchecked(qapp, tmp_path) -> None:
    from conftest import make_tree
    from je_file_tree.gui.cleanup_panel import CleanupPanel
    from je_file_tree.gui.tree_model import NODE_ROLE

    make_tree(tmp_path, {"AppData": {"Local": {
        "pip": {"Cache": {"wheel": b"data"}}, "Temp": {"private.tmp": b"private"},
        "Google": {"Chrome": {"User Data": {"Default": {"Cache": {"page": b"data"}}}}},
    }}})
    age_tree(tmp_path)
    root = scan(tmp_path).root
    panel = CleanupPanel()
    requests = []
    panel.review_requested.connect(requests.append)
    try:
        panel.set_root(root)
        _wait(qapp, lambda: not panel.busy)
        panel.select_all_entries()
        assert {node.name for node in requests[0]} == {"Cache"} and len(requests[0]) == 2
        selected = [index.data(NODE_ROLE) for index in panel.view.selectionModel().selectedRows()
                    if index.data(NODE_ROLE) is not None]
        assert set(selected) == set(requests[0]), "all lower-risk groups remain selected"
        row = next(index for index, group in enumerate(panel.groups) if group.key == "temp")
        panel.view.setCurrentIndex(panel.model.index(row, 0))
        assert panel.select_group.text() == "Review manually"
        panel.select_current_group()
        dialog = CleanupReview(requests[1], panel.reasons_for(requests[1]), [], "B", root)
        try:
            assert dialog.selected_nodes() == []
            assert "minimum age: 7 days" in dialog.model.data(dialog.model.index(0, 3))
            assert "cannot necessarily be recreated" in dialog.model.data(dialog.model.index(0, 8))
        finally:
            dialog.shutdown()
            dialog.deleteLater()
    finally:
        panel.stop(wait=True)
        panel.deleteLater()
