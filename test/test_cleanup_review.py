"""The review queue is mandatory for cleanup and preserves unchecked/protected entries."""

from pathlib import Path
import threading

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from je_file_tree.core.protected import PROGRAMS, Protection
from je_file_tree.core.scanner import scan
from je_file_tree.core.node import Node
from je_file_tree.core.savings import Savings
from je_file_tree.gui.cleanup_review import CleanupReview, ReviewModel
from je_file_tree.gui.cleanup_text import explanation
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
        assert dialog.model.columnCount() == 4
        assert dialog.model.data(dialog.model.index(0, 1)) == protected.path
        assert "installed programs" in dialog.model.risk_text(0)
        assert "building the project again" in dialog.model.details_text(0)
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
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.show()
        qapp.processEvents()
        index = dialog.model.index(0, 0)
        dialog.view.setFocus()
        dialog.view.setCurrentIndex(index)
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Space)
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
            assert "minimum age: 7 days" in dialog.model.details_text(0)
            assert "cannot necessarily be recreated" in dialog.model.details_text(0)
        finally:
            dialog.shutdown()
            dialog.deleteLater()
    finally:
        panel.stop(wait=True)
        panel.deleteLater()


def test_risk_and_full_details_preserve_all_three_initial_selection_rules(qapp) -> None:
    root = Node("owned-review-root", True, children=[])
    ordinary, low, manual = [Node(name, False, size=123, allocated=4096, modified=1_700_000_000,
                                 parent=root) for name in ("ordinary", "cache", "build")]
    root.children.extend((ordinary, low, manual))
    model = ReviewModel(root.children, {low: "browser_cache", manual: "build_output"},
                        [Protection(manual.path, PROGRAMS)], "B")
    assert model.selected_nodes() == [ordinary, low]
    assert model.risk_text(0) == "Review manually"
    assert "unchecked" not in model.details_text(0)
    assert model.risk_text(1) == "Lower risk"
    assert "installed programs" in model.risk_text(2)
    details = model.details_text(2)
    assert details.count(explanation("build_output")) == 1
    assert all(value in details for value in (manual.path, "Modified:", "123 B", "4,096 B",
                                              "Risk:", "Protection:", "building the project again"))


def test_details_keyboard_selection_scroll_and_tab_escape(qapp, tmp_path) -> None:
    (tmp_path / ("long-name-" * 15)).write_bytes(b"data")
    root = scan(tmp_path).root
    node = root.children[0]
    dialog = CleanupReview([node], {node: "build_output"}, [], "B", root)
    try:
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.resize(980, 600)
        dialog.show()
        qapp.processEvents()
        dialog.view.setFocus()
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Space)
        _wait(qapp, lambda: dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        assert dialog.selected_nodes() == [node]
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
        assert dialog.focusWidget() is dialog.details
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        assert dialog.details.textCursor().selectedText().replace("\u2029", "\n") == dialog.model.details_text(0)
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
        qapp.processEvents()
        assert dialog.details.verticalScrollBar().value() > 0
        assert dialog.details.textCursor().atEnd()
        assert dialog.details.viewport().rect().contains(dialog.details.cursorRect())
        QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
        assert dialog.focusWidget() is dialog.open_folder
        assert dialog.scope.text() == root.path
        assert dialog.view.horizontalScrollBar().maximum() == 0
    finally:
        dialog.shutdown()
        dialog.deleteLater()


def test_replaced_estimate_cannot_overwrite_latest_checked_selection(qapp, tmp_path, monkeypatch) -> None:
    from je_file_tree.gui import cleanup_review

    (tmp_path / "first").write_bytes(b"one")
    (tmp_path / "second").write_bytes(b"two")
    root = scan(tmp_path).root
    started, release = threading.Event(), threading.Event()

    def estimate(nodes, **_kwargs):
        if len(nodes) == 2:
            started.set()
            release.wait(5)
        return Savings(len(nodes), 0, 0, None, None, True)

    monkeypatch.setattr(cleanup_review, "estimate_savings", estimate)
    dialog = CleanupReview(root.children, {}, [], "B", root)
    try:
        _wait(qapp, started.is_set)
        dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        _wait(qapp, lambda: dialog._current is None)
        latest = dialog.summary.text()
        assert "1 entries" in latest and "after emptying the Recycle Bin: unknown" in latest
        release.set()
        _wait(qapp, lambda: not dialog._running)
        assert dialog.summary.text() == latest
        assert dialog.selected_nodes() == [root.children[1]]
    finally:
        release.set()
        dialog.shutdown()
        dialog.deleteLater()


def test_close_joins_estimate_and_ignores_its_late_reply(qapp, tmp_path, monkeypatch) -> None:
    from je_file_tree.gui import cleanup_review

    (tmp_path / "file").write_bytes(b"data")
    root = scan(tmp_path).root
    started, release = threading.Event(), threading.Event()
    cancellations = []

    def estimate(_nodes, *, cancel, **_kwargs):
        cancellations.append(cancel)
        started.set()
        release.wait(5)
        return Savings(999, 999, 0, 999, 999, True)

    monkeypatch.setattr(cleanup_review, "estimate_savings", estimate)
    dialog = CleanupReview(root.children, {}, [], "B", root)
    finished = []
    dialog.finished.connect(finished.append)
    try:
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.show()
        _wait(qapp, started.is_set)
        summary = dialog.summary.text()
        dialog.reject()
        assert cancellations[0].is_set() and not finished and not dialog.isEnabled()
        release.set()
        _wait(qapp, lambda: bool(finished))
        assert finished == [QDialog.DialogCode.Rejected]
        assert dialog.summary.text() == summary
        assert not dialog._running
    finally:
        release.set()
        dialog.shutdown()
        dialog.deleteLater()
