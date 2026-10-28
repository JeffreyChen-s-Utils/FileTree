"""Folder budgets use complete scan evidence and durable, ordered alert episodes."""

import json
import threading

import pytest
from PySide6.QtCore import QSettings, Qt

from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.folder_budgets import BudgetRule, BudgetTicket, observe_budgets
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import NOT_SCANNED, ScanOptions, scan
from je_file_tree.core.history import ScanHistory
from je_file_tree.gui.app import create_workspace
from je_file_tree.gui.background_worker import ScheduledWorker
from je_file_tree.gui.folder_budget_store import FolderBudgetStore, KEY
from je_file_tree.gui.scan_worker import ScanWorker, wait_for
from je_file_tree.gui.search_ranges import exact_bytes
from test_gui import _wait


def _store(tmp_path):
    settings = QSettings(str(tmp_path / "budgets.ini"), QSettings.Format.IniFormat)
    return FolderBudgetStore(settings)


def _batch(root, ticket):
    return observe_budgets(root, coverage_of(root), ticket, 1_700_000_000.0)


def test_exact_limits_and_alert_episode_survive_restart(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    item = source / "data"
    item.write_bytes(b"x")
    store = _store(tmp_path)
    rule = store.put("zero", str(source), 0)
    first = _batch(scan(source).root, store.ticket())
    assert len(store.publish(first)) == 1
    assert store.rows[0].status == "over"
    assert store.rows[0].observation.bytes == 1
    assert store.publish(_batch(scan(source).root, store.ticket())) == ()
    reopened = _store(tmp_path)
    assert reopened.rows[0].alerted
    assert reopened.publish(_batch(scan(source).root, reopened.ticket())) == ()
    item.unlink()
    assert reopened.publish(_batch(scan(source).root, reopened.ticket())) == ()
    assert reopened.rows[0].status == "within" and not reopened.rows[0].alerted
    item.write_bytes(b"x")
    assert reopened.publish(_batch(scan(source).root, reopened.ticket()))[0].rule == rule
    assert exact_bytes("1", "KiB") == 1024
    with pytest.raises(ValueError):
        exact_bytes("0.1", "B")
    with pytest.raises(ValueError):
        store.put("invalid", str(source / "bad"), True)


def test_coverage_missing_link_file_nested_and_unrelated(tmp_path):
    base = str(tmp_path / "base")
    root = Node(base, True, children=[])
    good = Node("good", True, size=5, parent=root, children=[])
    bad = Node("bad", True, error=NOT_SCANNED, parent=root, children=[])
    link = Node("link", True, is_link=True, parent=root)
    file = Node("file", False, parent=root)
    root.children = [good, bad, link, file]
    rules = tuple(BudgetRule(str(index), 1, name, str(tmp_path / "base" / name), 1)
                  for index, name in enumerate(("good", "bad", "link", "file", "missing", "good/child")))
    batch = _batch(root, BudgetTicket(1, rules))
    assert [(item.bytes, item.reason) for item in batch.observations] == [
        (5, None), (None, "incomplete"), (None, "linked"), (None, "not_folder"),
        (None, "missing"), (None, "missing"),
    ]
    other = Node(str(tmp_path / "elsewhere"), True, children=[])
    assert _batch(other, BudgetTicket(2, rules)).observations == ()
    virtual = Node("", True, children=[root, other])
    root.parent = virtual
    other.parent = virtual
    assert len(_batch(virtual, BudgetTicket(3, rules)).observations) == 6
    stopped = threading.Event()
    stopped.set()
    assert observe_budgets(root, coverage_of(root), BudgetTicket(4, rules), 1.0, stopped) is None


def test_old_edit_delete_and_independent_rule_versions(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_bytes(b"123")
    store = _store(tmp_path)
    a = store.put("a", str(source), 1)
    b = store.put("b", str(source / "nested"), 1)
    old = store.ticket()
    store.put("a renamed", str(source), 1, a.identity)
    store.put("b", str(source / "nested"), 2, b.identity)
    batch = _batch(scan(source).root, old)
    assert len(store.publish(batch)) == 1
    assert store.rows[0].status == "over" and store.rows[1].status == "waiting"
    newer = store.ticket()
    store.publish(_batch(scan(source).root, newer))
    assert store.publish(batch) == ()
    store.delete(a.identity)
    assert store.publish(_batch(scan(source).root, newer)) == ()
    assert len(store.rows) == 1
    changed = store.put("moved", str(source / "other"), 2, b.identity)
    assert changed.identity != b.identity and store.rows[0].status == "waiting"


def test_unknown_retains_alert_then_recovery_rearms(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    store = _store(tmp_path)
    store.put("target", str(source), 0)
    root = Node(str(source), True, size=1, children=[])
    assert len(store.publish(_batch(root, store.ticket()))) == 1
    root.error = NOT_SCANNED
    assert store.publish(_batch(root, store.ticket())) == ()
    assert store.rows[0].status == "unknown" and store.rows[0].alerted
    root.error, root.size = None, 1
    assert store.publish(_batch(root, store.ticket())) == ()
    root.size = 0
    store.publish(_batch(root, store.ticket()))
    assert not store.rows[0].alerted
    root.size = 2
    assert len(store.publish(_batch(root, store.ticket()))) == 1


@pytest.mark.parametrize("payload", [
    "{", '{"sequence":true,"rows":[]}', '{"sequence":0,"rows":[{}]}',
    '{"sequence":0,"rows":[{"id":1}]}', '{"sequence":0,"rows":[],"rows":[]}',
])
def test_corrupt_settings_fail_closed(tmp_path, payload):
    settings = QSettings(str(tmp_path / "bad.ini"), QSettings.Format.IniFormat)
    settings.setValue(KEY, payload)
    settings.sync()
    store = FolderBudgetStore(settings)
    assert store.error
    with pytest.raises(ValueError):
        store.ticket()


def test_corrupt_date_and_lock_failure_are_visible(tmp_path):
    store = _store(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    store.put("source", str(source), 0)
    lock = store._lock()
    try:
        with pytest.raises(OSError, match="locked"):
            store.ticket()
        assert "locked" in store.error
    finally:
        lock.unlock()
    data = json.loads(str(store.settings.value(KEY)))
    data["sequence"] = 1
    data["rows"][0]["applied"] = 1
    data["rows"][0]["observation"] = {
        "version": 1, "sequence": 1, "at": 1e300, "bytes": 1, "reason": None,
    }
    store.settings.setValue(KEY, json.dumps(data))
    store.settings.sync()
    with pytest.raises(ValueError, match="date"):
        store.reload()


@pytest.mark.parametrize(("field", "value"), [
    ("reason", []), ("reason", {}), ("at", 10 ** 400),
])
def test_malformed_observation_keeps_startup_open_and_settings_intact(tmp_path, field, value):
    path = tmp_path / "settings.ini"
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    store = FolderBudgetStore(settings)
    source = tmp_path / "source"
    source.mkdir()
    store.put("source", str(source), 1)
    data = json.loads(str(settings.value(KEY)))
    data["sequence"] = 1
    data["rows"][0]["applied"] = 1
    observation = {"version": 1, "sequence": 1, "at": 1_700_000_000.0,
                   "bytes": None, "reason": "missing"}
    observation[field] = value
    data["rows"][0]["observation"] = observation
    original = json.dumps(data)
    settings.setValue(KEY, original)
    settings.sync()
    fresh = QSettings(str(path), QSettings.Format.IniFormat)
    reopened = FolderBudgetStore(fresh)
    assert reopened.error
    assert str(fresh.value(KEY)) == original


def test_failed_settings_sync_does_not_claim_or_later_commit_alert(tmp_path):
    class FailingSettings(QSettings):
        fail_after = None
        calls = 0

        def sync(self):
            self.calls += 1
            if self.fail_after is None or self.calls < self.fail_after:
                super().sync()

        def status(self):
            failed = self.fail_after is not None and self.calls >= self.fail_after
            return QSettings.Status.AccessError if failed else super().status()

    settings = FailingSettings(str(tmp_path / "sync.ini"), QSettings.Format.IniFormat)
    store = FolderBudgetStore(settings)
    source = tmp_path / "source"
    source.mkdir()
    store.put("source", str(source), 0)
    ticket = store.ticket()
    settings.fail_after = settings.calls + 2
    with pytest.raises(OSError, match="save"):
        store.publish(_batch(Node(str(source), True, size=1), ticket))
    assert store.error and not store.rows[0].alerted
    settings.fail_after = None
    settings.sync()
    reopened = FolderBudgetStore(QSettings(str(tmp_path / "sync.ini"), QSettings.Format.IniFormat))
    assert not reopened.rows[0].alerted and reopened.rows[0].observation is None


def test_scheduled_cancel_in_budget_phase_keeps_history_unpublished(tmp_path, qapp, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_bytes(b"x")
    store = _store(tmp_path)
    store.put("source", str(source), 0)
    history = ScanHistory(tmp_path / "history")
    from je_file_tree.gui import background_worker
    monkeypatch.setattr(background_worker, "coverage_of", lambda _root, *, cancel: None)
    worker = ScheduledWorker(str(source), ScanOptions(), history, qapp, budget_ticket=store.ticket())
    worker.run()
    assert worker.state == "canceled" and worker.entry is None and worker.budget_batch is None
    assert not history.read(str(source)).entries


def test_foreground_cancel_in_budget_phase_has_no_full_publication(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_bytes(b"x")
    store = _store(tmp_path)
    store.put("source", str(source), 0)
    history = ScanHistory(tmp_path / "history")
    from je_file_tree.gui import scan_worker
    monkeypatch.setattr(scan_worker, "observe_budgets", lambda *_args: None)
    worker = ScanWorker(str(source), ScanOptions(), history=history, budget_ticket=store.ticket())
    succeeded, cancelled = [], []
    worker.succeeded.connect(succeeded.append)
    worker.cancelled.connect(cancelled.append)
    worker.run()
    assert not succeeded and len(cancelled) == 1 and cancelled[0].partial
    assert not history.read(str(source)).entries
    assert store.rows[0].observation is None


def test_both_complete_scan_producers_emit_scalar_batches(tmp_path, qapp):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_bytes(b"123")
    store = _store(tmp_path)
    store.put("source", str(source), 1)
    ticket = store.ticket()
    ordinary = ScanWorker(str(source), ScanOptions(), budget_ticket=ticket)
    outcomes = []
    ordinary.succeeded.connect(outcomes.append)
    ordinary.start()
    _wait(qapp, lambda: bool(outcomes))
    wait_for(ordinary)
    assert outcomes[0].budget_batch.observations[0].bytes == 3
    assert len(store.publish(outcomes[0].budget_batch)) == 1
    scheduled = ScheduledWorker(str(source), ScanOptions(), ScanHistory(tmp_path / "history"),
                                qapp, budget_ticket=store.ticket())
    scheduled.start()
    _wait(qapp, lambda: scheduled.state == "complete")
    wait_for(scheduled)
    assert scheduled.budget_batch.observations[0].bytes == 3
    assert store.publish(scheduled.budget_batch) == ()
    ordinary.deleteLater()
    scheduled.deleteLater()


def test_workspace_manager_prefills_real_selection_and_retranslates(tmp_path, qapp):
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    workspace = create_workspace(settings)
    workspace.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    workspace.show()
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_bytes(b"123")
    nested = source / "nested"
    nested.mkdir()
    changing = nested / "changing"
    changing.write_bytes(b"x")
    workspace.budget_action.trigger()
    dialog = workspace._budget_dialog
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    assert dialog is not None
    dialog.path.setText(str(source))
    dialog.name.setText("source")
    dialog.limit.setText("2")
    dialog.add_button.click()
    assert len(workspace.budgets.rows) == 1
    assert "1 unknown" in workspace.budget_label.text()
    workspace.current.start_scan(str(source))
    _wait(qapp, lambda: workspace.current._worker is None)
    assert workspace.budgets.rows[0].status == "over"
    assert "1 over" in workspace.budget_label.text()
    _branch_rescan_keeps_budget(workspace, qapp, nested, changing)
    dialog.reject()
    qapp.processEvents()
    workspace.current.results.select_node(workspace.current.results.outcome.result.root)
    workspace.current._actions["folder_budgets"].trigger()
    dialog = workspace._budget_dialog
    assert dialog.path.text() == str(source)
    from je_file_tree.gui.i18n import set_language
    set_language("zh-TW")
    workspace.retranslate()
    assert dialog.name_label.text() == "名稱"
    assert "超過上限" in dialog.table.item(0, 6).text()
    dialog.name.setText("錯誤")
    dialog.path.setText("relative")
    dialog.limit.setText("1")
    dialog.add_button.click()
    assert "絕對路徑" in dialog.error.text()
    dialog.reject()
    workspace.close()
    _wait(qapp, lambda: workspace._close_ready)
    set_language("en")


def _branch_rescan_keeps_budget(workspace, qapp, nested, changing):
    before = workspace.budgets.rows[0].observation.bytes
    changing.write_bytes(b"more bytes")
    branch = next(node for node in workspace.current.results.outcome.result.root.iter_nodes()
                  if node.path == str(nested))
    workspace.current.rescan_folder(branch)
    _wait(qapp, lambda: workspace.current._worker is None)
    assert workspace.current.results.outcome.result.root.size > before
    assert workspace.budgets.rows[0].observation.bytes == before
