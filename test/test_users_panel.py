"""Lazy Users analysis, scan-setting capture, numeric rows and replacement/close ownership."""

import threading

from PySide6.QtCore import Qt

from test_gui import _scanned, _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core.node import Node
from je_file_tree.core.owners import OwnerInventory, OwnerStat
from je_file_tree.core.scanner import scan
from je_file_tree.gui import users_panel as users
from je_file_tree.gui.results_view import USERS_TAB
from je_file_tree.gui.scan_worker import ScanWorker
from je_file_tree.gui.tables import SORT_ROLE
from je_file_tree.gui.list_transfer import ListCapture


def test_windows_owner_capture_is_off_and_running_workers_keep_their_options(window):
    assert not window._scan_options().windows_owners
    original = window._scan_options()
    worker = ScanWorker("unstarted-owned", original, window)
    window._worker = worker
    try:
        window._actions["capture_owners"].setChecked(True)
        assert window._scan_options().windows_owners and not worker._options.windows_owners
        assert str(window.settings.value("capture_owners")).lower() == "true"
    finally:
        window._worker = None
        worker.deleteLater()


def test_users_are_lazy_whole_root_readonly_sortable_and_current_export_list(window, qapp, sample_tree, monkeypatch):
    calls = []
    row = OwnerStat(123, "<owner>", "uid:123", 1000, 4096, 6, 1)
    def query(root, **_kwargs):
        calls.append(root)
        return OwnerInventory([row], 1, 6, 1000, 0, 0, False)
    monkeypatch.setattr(users, "owner_stats", query)
    _scanned(window, qapp, sample_tree)
    panel = window.results.users
    assert not calls and panel.model.rowCount() == 0
    window.results.tabs.setCurrentIndex(USERS_TAB)
    _wait(qapp, lambda: not panel.busy)
    assert calls == [window.results.outcome.result.root] and panel.model.rowCount() == 1
    assert window.results.current_list() is panel.view
    assert panel.status.textFormat() == Qt.TextFormat.PlainText
    assert not panel.model.flags(panel.model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    assert panel.model.data(panel.model.index(0, 2), SORT_ROLE) == 1000
    captured = []
    capture = ListCapture(panel.view, panel)
    capture.ready.connect(lambda header, rows: captured.append((header, rows)))
    capture.start()
    _wait(qapp, lambda: bool(captured))
    assert captured[0][1] == [["<owner>", "uid:123", "1,000 B", "4.0 KB", "6", "100.0 %"]]
    capture.deleteLater()
    window.set_unit("KB")
    assert "KB" in panel.model.data(panel.model.index(0, 2))
    window.results.select_node(next(window.results.outcome.result.root.iter_files()))
    assert len(calls) == 1  # Selection does not mislabel whole-root data as a selected subtree.
    window.results.users.set_root(window.results.outcome.result.root, partial=True)
    _wait(qapp, lambda: not panel.busy)
    assert "Incomplete" in panel.status.text()


def test_replacement_and_stop_close_discard_late_ownership_inventory(window, qapp, monkeypatch):
    panel = window.results.users
    entered, roots = threading.Event(), []
    def waiting(root, *, cancel):
        roots.append(root)
        entered.set()
        assert cancel.wait(10)
        return OwnerInventory([], 0, 0, 0, 0, 0, False)
    monkeypatch.setattr(users, "owner_stats", waiting)
    root, fresh = Node("old", True), Node("new", True)
    panel.set_root(root)
    panel.set_active(True)
    _wait(qapp, entered.is_set)
    old = panel._current
    entered.clear()
    panel.set_root(fresh)
    _wait(qapp, entered.is_set)
    assert roots == [root, fresh] and old.cancel.is_set()
    panel._show(old, OwnerInventory([OwnerStat(1, "old", "uid:1", 1, 1, 1, 1)], 1, 1, 1, 0, 0, False))
    assert panel.model.rowCount() == 0
    active = panel._current
    panel.stop_button.click()
    panel.stop(wait=True)
    assert not active.isRunning() and panel.model.rowCount() == 0
    entered.clear()
    panel.refresh_button.click()
    _wait(qapp, entered.is_set)
    active = panel._current
    window.close()
    assert not active.isRunning() and not panel.busy
    panel._show(active, OwnerInventory([], 0, 0, 0, 0, 0, False))
    assert panel.model.rowCount() == 0


def test_recorded_owner_totals_refresh_after_forgetting_entries_and_replacing_branch(window, qapp, sample_tree):
    _scanned(window, qapp, sample_tree)
    window.results.tabs.setCurrentIndex(USERS_TAB)
    panel = window.results.users
    _wait(qapp, lambda: not panel.busy)
    assert panel._inventory.files == 6 and panel._inventory.size == 1000
    root = window.results.outcome.result.root
    folder = next(node for node in root.children if node.name == "code")
    (sample_tree / "code" / "new.txt").write_bytes(b"new")
    window.results.replace_branch(folder, scan(folder.path))
    _wait(qapp, lambda: not panel.busy)
    assert panel._inventory.files == 7 and panel._inventory.size == 1003
    node = next(node for node in root.children if node.name == "notes.txt")
    window.results.forget([node])
    _wait(qapp, lambda: not panel.busy)
    assert panel._inventory.files == 6 and panel._inventory.size == 903
    assert (sample_tree / "notes.txt").exists()  # UI record mutation does not remove the fixture.
