"""Cleanup completion preserves actual outcomes without implying free-space recovery."""

import dataclasses
import json
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import pytest

from test_gui import window as window  # noqa: PLC0414 - shared fixture
from je_file_tree.core.node import Node
from je_file_tree.core.formatting import format_size, format_time
from je_file_tree.core.operations import MoveResult, MoveSummary, summarise_moves
from je_file_tree.core.scanner import scan
from je_file_tree.gui import i18n
from je_file_tree.gui.cleanup_completion import CleanupCompletion
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.trash_worker import TrashWorker


def test_summary_captures_counts_and_reasons_without_reading_descendants():
    class Unreadable(list):
        def __iter__(self):
            pytest.fail("summary walked descendants")
    folder = Node("captured", True, size=123, children=Unreadable())
    other = Node("other", False, size=20)
    result = MoveResult(moved=[folder], skipped=[(other, "changed"), (other, "changed")], failed=[other],
                        journal_errors=["owned journal error"])
    summary = summarise_moves(result)
    assert summary == MoveSummary(1, 2, 1, 123, (("changed", 2),), 1)
    assert json.loads(json.dumps(dataclasses.asdict(summary)))["moved_bytes"] == 123


def test_worker_publishes_summary_before_done(window, sample_tree, monkeypatch):
    root = scan(sample_tree).root
    node = next(node for node in root.children if not node.is_dir)
    result = MoveResult(moved=[node], skipped=[(node, "changed")])
    worker = TrashWorker(root, [node], [], {}, window)
    monkeypatch.setattr(worker._audit, "begin", lambda _nodes: True)
    monkeypatch.setattr(worker._audit, "finish", lambda _result: None)
    monkeypatch.setattr(worker, "_move_checked", lambda: result)
    received = []
    worker.done.connect(lambda observed: received.append(observed.summary))
    try:
        worker.run()
        assert received == [MoveSummary(1, 1, 0, node.size, (("changed", 1),))]
    finally:
        worker.deleteLater()


@pytest.mark.parametrize("language", i18n.LANGUAGES)
def test_summary_retains_selection_and_collapse_across_language_and_unit(window, sample_tree, language):
    results = window.results
    outcome = analyse(scan(sample_tree))
    results.show_outcome(outcome)
    results.select_node(outcome.top_folders[0])
    selected = results.selected_node()
    completion = results.completion
    summary = MoveSummary(1, 2, 1, 4096, (("changed", 2),))
    completion.show_summary(summary, outcome.result.root, outcome.capacity)
    i18n.set_language(language)
    results.retranslate()
    results.set_unit("KB")
    assert completion.toggle.text().startswith(i18n.tr("completion_title"))
    assert "4.0 KB" in completion.counts.text()
    assert completion.counts.text() in completion.toggle.text()
    assert i18n.tr("trash_skip_changed") in completion.reasons.text()
    completion.toggle.setChecked(True)
    assert not completion.popup.isHidden()
    QTest.keyClick(completion.toggle, Qt.Key.Key_Space)
    results.retranslate()
    assert completion.body.isHidden() and results.selected_node() is selected
    results.begin_scan()
    assert not completion.isHidden() and completion._summary is summary


def test_popup_close_clears_toggle_and_preserves_summary(window, sample_tree):
    outcome = analyse(scan(sample_tree))
    completion = window.results.completion
    summary = MoveSummary(1, 0, 0, 100)
    completion.show_summary(summary, outcome.result.root, outcome.capacity)
    completion.toggle.setChecked(True)
    QTest.keyClick(completion.popup, Qt.Key.Key_Escape)
    assert completion.popup.isHidden() and not completion.toggle.isChecked()
    assert completion._summary is summary


def test_free_space_is_a_later_same_root_observation_not_moved_bytes(window, sample_tree, tmp_path):
    outcome = analyse(scan(sample_tree))
    root = outcome.result.root
    baseline = dataclasses.replace(outcome.capacity, free=1000, measured_at=10)
    completion = window.results.completion
    completion.show_summary(MoveSummary(1, 0, 0, 9000), root, baseline)
    assert completion._delta is None
    later = dataclasses.replace(baseline, free=1500, measured_at=20)
    window.results.show_outcome(dataclasses.replace(outcome, capacity=later))
    assert completion._delta == 500
    assert "+500 B" in completion.space.text() and format_size(9000) in completion.counts.text()
    assert completion.space.toolTip() == i18n.tr("completion_measurements", before=format_time(10),
                                                after=format_time(20))
    window.results.set_capacity(dataclasses.replace(later, free=800, measured_at=30))
    assert completion._delta == -200
    completion.observe(root, dataclasses.replace(later, free=99999, measured_at=15))
    assert completion._delta == -200
    other = scan(tmp_path).root
    completion.observe(other, dataclasses.replace(later, free=0, measured_at=40))
    assert completion._delta == -200
    completion.show_summary(MoveSummary(1, 0, 0, 9000), root, None)
    completion.observe(root, later)
    assert completion._delta is None


def test_summary_navigation_uses_captured_source_and_never_extends_undo(qapp, sample_tree):
    outcome = analyse(scan(sample_tree))
    completion = CleanupCompletion()
    seen = []
    completion.rescan_requested.connect(seen.append)
    try:
        completion.show_summary(MoveSummary(0, 0, 0, 0), outcome.result.root, outcome.capacity)
        assert not completion.undo.isEnabled() and not completion.rescan.isEnabled()
        completion.set_actions(undo=False, rescan=True)
        completion.rescan.click()
        assert seen == [str(sample_tree)]
        completion.clear()
        assert completion._summary is None and not completion.rescan.isEnabled()
    finally:
        completion.deleteLater()


@pytest.mark.parametrize("identity", [(0, 0), (1, 0), (0, 1)])
def test_unknown_root_identity_never_produces_a_free_space_delta(window, sample_tree, monkeypatch, identity):
    outcome = analyse(scan(sample_tree))
    monkeypatch.setattr("je_file_tree.gui.cleanup_completion.unpack_snapshot",
                        lambda _snapshot: SimpleNamespace(identity=identity))
    baseline = dataclasses.replace(outcome.capacity, free=1000, measured_at=10)
    completion = window.results.completion
    completion.show_summary(MoveSummary(0, 1, 0, 0), outcome.result.root, baseline)
    completion.observe(outcome.result.root, dataclasses.replace(baseline, free=1500, measured_at=20))
    assert completion._delta is None


def test_main_window_keeps_existing_failure_reports_and_shows_captured_totals(window, sample_tree, monkeypatch):
    outcome = analyse(scan(sample_tree))
    window.results.show_outcome(outcome)
    nodes = outcome.result.root.children
    result = MoveResult(moved=[nodes[0]], skipped=[(nodes[1], "changed")], failed=[nodes[2]])
    result.summary = summarise_moves(result)
    reports = []
    monkeypatch.setattr(window, "refresh_bin_labels", lambda: None)
    monkeypatch.setattr(window, "_show_failed", lambda _result: reports.append("failed"))
    monkeypatch.setattr(window, "_show_skipped", lambda _rows: reports.append("skipped"))
    window._trash_finished(result)
    assert reports == ["failed", "skipped"]
    assert window.results.completion._summary is result.summary
    assert not window.results.completion.isHidden()
    assert window._worker is None
