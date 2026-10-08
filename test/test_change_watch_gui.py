"""Per-tab native-following ownership, bounded dirty state and fresh-scan-only event authority."""

import hashlib
import os
import sys
import time

import pytest
from PySide6.QtWidgets import QDialog
from PySide6.QtTest import QSignalSpy
from PySide6.QtCore import QSettings

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree.core.change_watch import MAX_CHANGED, ChangeBatch
from je_file_tree.core.scanner import scan
from je_file_tree.core.multi_scan import scan_roots
from je_file_tree.gui import change_watch as following
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.app import create_workspace


def _source(window, tmp_path):
    source = tmp_path / "來源"
    (source / "資料" / "nested").mkdir(parents=True)
    (source / "另一個").mkdir()
    (source / "資料" / "file").write_bytes(b"kept")
    (source / "另一個" / "untouched").write_bytes(b"untouched")
    window.results.show_outcome(analyse(scan(source)))
    return source, window.results.outcome.result.root


def _enable(window, qapp, monkeypatch):
    def watch(_root, _changed, cancel, *, ready):
        ready("directory_changes")
        cancel.wait()

    monkeypatch.setattr(following, "watch", watch)
    monkeypatch.setattr(following, "supported", lambda: True)
    window._actions["follow_changes"].setChecked(True)
    _wait(qapp, lambda: window._follow.worker is not None and bool(window._follow.worker.backend))
    return window._follow


def _dirty(controller, *paths, full=False):
    controller.worker.record(ChangeBatch(tuple(str(path) for path in paths), full))
    controller.tick()
    controller._since = time.monotonic() - 2


def test_default_off_and_opt_out_joins_worker_before_return(window, qapp, tmp_path, monkeypatch):
    _source(window, tmp_path)
    assert not window._actions["follow_changes"].isChecked() and window._follow.worker is None
    controller = _enable(window, qapp, monkeypatch)
    worker = controller.worker
    assert worker.isRunning() and window.settings.value("follow_changes", type=bool)
    window._actions["follow_changes"].setChecked(False)
    assert controller.worker is None and worker.cancel.is_set() and not worker.isRunning()
    assert not controller.timer.isActive() and not controller.label.isVisible()


def test_bounded_coalescing_only_refreshes_outermost_dirty_branch(window, qapp, tmp_path, monkeypatch):
    source, root = _source(window, tmp_path)
    controller = _enable(window, qapp, monkeypatch)
    calls = []
    monkeypatch.setattr(window, "rescan_folder", calls.append)
    _dirty(controller, source / "資料", source / "資料" / "nested")
    assert not calls
    controller.tick()
    assert len(calls) == 1 and calls[0].path == str(source / "資料")
    assert calls[0].is_in(root) and not controller._pending.folders
    controller.worker.record(ChangeBatch(tuple(str(number) for number in range(MAX_CHANGED + 1))))
    assert controller.worker.take().full


def test_busy_review_retains_events_and_joins_before_tree_mutation(window, qapp, tmp_path, monkeypatch):
    source, root = _source(window, tmp_path)
    controller = _enable(window, qapp, monkeypatch)
    _dirty(controller, source / "資料")
    old = controller.worker
    calls = []
    monkeypatch.setattr(window, "rescan_folder", calls.append)
    dialog = QDialog(window)
    window._path_dialogs.add(dialog)
    window._update_actions()
    controller.tick()
    assert not calls and controller.worker is None and not old.isRunning()
    assert controller._pending.full
    window._path_dialogs.remove(dialog)
    controller.tick()
    assert calls == [root]
    dialog.deleteLater()


def test_scope_loss_accounting_and_periodic_reconciliation_request_full_root(window, qapp, tmp_path, monkeypatch):
    source, root = _source(window, tmp_path)
    controller = _enable(window, qapp, monkeypatch)
    calls = []
    monkeypatch.setattr(window, "rescan_folder", calls.append)
    _dirty(controller, source / "not-captured")
    controller.tick()
    assert controller._pending.full and not calls
    controller.tick()
    assert calls == [root]
    controller._reconcile = time.monotonic() - 1
    controller.tick()
    controller._since -= 2
    controller.tick()
    assert calls == [root, root]
    controller._reconcile = time.monotonic() + 300
    deadline = controller._reconcile
    controller.adopt(root)
    assert controller._reconcile == deadline


def test_feed_error_is_visible_plain_text_without_automatic_retry(window, qapp, tmp_path, monkeypatch):
    _source(window, tmp_path)

    def failed(*_args, **_kwargs):
        raise OSError("owned <unsafe> native limit")

    monkeypatch.setattr(following, "watch", failed)
    monkeypatch.setattr(following, "supported", lambda: True)
    window._actions["follow_changes"].setChecked(True)
    _wait(qapp, lambda: bool(window._follow.worker.error))
    calls = []
    monkeypatch.setattr(window, "rescan_folder", calls.append)
    window._follow._merge(ChangeBatch(full=True))
    window._follow.tick()
    assert "owned <unsafe> native limit" in window._follow.label.text()
    assert not calls
    worker = window._follow.worker
    window.close()
    assert not worker.isRunning() and window._follow.worker is None


def test_unrelated_dirty_branches_survive_the_first_refresh(window, qapp, tmp_path, monkeypatch):
    source, _root = _source(window, tmp_path)
    controller = _enable(window, qapp, monkeypatch)
    calls = []
    monkeypatch.setattr(window, "rescan_folder", calls.append)
    _dirty(controller, source / "資料", source / "另一個")
    controller.tick()
    assert len(calls) == 1 and len(controller._pending.folders) == 1
    controller.tick()
    assert {node.path for node in calls} == {str(source / "資料"), str(source / "另一個")}
    assert not controller._pending.folders


@pytest.mark.parametrize("combined", [False, True])
def test_partial_or_combined_scan_refuses_following_without_native_setup(window, tmp_path, monkeypatch, combined):
    source, _root = _source(window, tmp_path)
    result = scan_roots((str(source / "資料"), str(source / "另一個"))) if combined else scan(source)
    window.results.show_outcome(analyse(result, partial=not combined))
    dialog = QDialog(window)
    window._path_dialogs.add(dialog)

    def forbidden(*_args, **_kwargs):
        pytest.fail("partial scan started a native feed")

    monkeypatch.setattr(following, "watch", forbidden)
    monkeypatch.setattr(following, "supported", lambda: True)
    window._actions["follow_changes"].setChecked(True)
    assert window._follow.worker is None and window._follow._status == "follow_incomplete"
    window._path_dialogs.remove(dialog)
    window._follow._merge(ChangeBatch(full=True))
    window._follow._since -= 2
    monkeypatch.setattr(window, "rescan_folder", lambda _node: pytest.fail("refused scope was rescanned"))
    window._follow.tick()
    dialog.deleteLater()


def test_counted_hard_links_require_full_root_reconciliation(window, qapp, tmp_path, monkeypatch):
    source, root = _source(window, tmp_path)
    os.link(source / "資料" / "file", source / "另一個" / "alias")
    window._actions["count_hard_links"].setChecked(True)
    controller = _enable(window, qapp, monkeypatch)
    _dirty(controller, source / "資料")
    controller.tick()
    _wait(qapp, lambda: window._worker is None and window.results.outcome.result.root is not root)
    result = window.results.outcome.result
    assert result.root.path == str(source) and result.hard_links is not None
    assert result.root.size == 17 and result.root.accounted_size == 13
    assert (source / "資料" / "file").read_bytes() == b"kept"


def test_tab_close_joins_only_its_monitor_and_pending_state_is_independent(qapp, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "workspace.ini"), QSettings.Format.IniFormat)
    workspace = create_workspace(settings)
    try:
        first = workspace.current
        second = workspace.add_tab()
        first_source, _root = _source(first, tmp_path / "first")
        _source(second, tmp_path / "second")
        first_controller = _enable(first, qapp, monkeypatch)
        second_controller = _enable(second, qapp, monkeypatch)
        _dirty(first_controller, first_source / "資料")
        first_worker, second_worker = first_controller.worker, second_controller.worker
        assert first_controller._pending.folders and not second_controller._pending.folders
        workspace.close_tab(0)
        assert first_controller.worker is None and first_worker.cancel.is_set() and not first_worker.isRunning()
        assert second_controller.worker is second_worker and second_worker.isRunning()
        assert not second_worker.cancel.is_set() and not second_controller._pending.folders
    finally:
        workspace.close()


@pytest.mark.skipif(not (sys.platform == "win32" or sys.platform.startswith("linux")), reason="native feed platform")
def test_native_event_replaces_one_branch_preserves_other_source_and_joins(window, qapp, tmp_path, monkeypatch):
    if sys.platform == "win32":
        from je_file_tree.core import windows_watch

        # Volume-wide USN changes can legitimately require a full rescan; this case proves branch notifications.
        def unavailable(*_args):
            raise PermissionError("Native GUI branch test uses recursive directory notifications")

        monkeypatch.setattr(windows_watch, "_watch_usn", unavailable)
    source, root = _source(window, tmp_path)
    untouched = next(child for child in root.children if child.name == "另一個")
    file = source / "另一個" / "untouched"
    proof = file.stat().st_ino, hashlib.sha256(file.read_bytes()).hexdigest()
    old_branch = next(child for child in root.children if child.name == "資料")
    assert any(item.node is old_branch for item in window.results.charts.tree.rows())
    window._actions["follow_changes"].setChecked(True)
    _wait(qapp, lambda: window._follow.worker is not None and bool(window._follow.worker.backend))
    worker = window._follow.worker
    if sys.platform == "win32":
        assert worker.backend == "directory_changes"
    finished = QSignalSpy(worker.finished)
    cancelled = worker.cancel
    (source / "資料" / "新增.bin").write_bytes(b"owned event" * 2048)
    _wait(qapp, lambda: root.size == 4 + 9 + 22528 and window._worker is None and not window._analysers)
    assert window.results.outcome.result.root is root and untouched in root.children
    assert (file.stat().st_ino, hashlib.sha256(file.read_bytes()).hexdigest()) == proof
    current_branch = next(child for child in root.children if child.name == "資料")
    assert current_branch is not old_branch
    assert any(item.node is current_branch for item in window.results.charts.tree.rows())
    assert not any(item.node is old_branch for item in window.results.charts.tree.rows())
    assert cancelled.is_set() and finished.count() == 1
    active = window._follow.worker
    assert active is not None
    window.close()
    assert not active.isRunning() and active.cancel.is_set()
