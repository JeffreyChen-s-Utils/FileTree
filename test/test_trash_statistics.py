"""Trash completion must not traverse removed subtrees on the GUI thread."""

import dataclasses
import threading

import pytest
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QMessageBox
from test_gui import _wait, window as window  # noqa: PLC0414 - shared fixture

from je_file_tree.core import analysis
from je_file_tree.core.node import Node
from je_file_tree.core.operations import MoveResult
from je_file_tree.core.scanner import scan
from je_file_tree.gui import file_actions, trash_worker
from je_file_tree.gui.scan_worker import analyse


def test_successful_trash_statistics_do_not_walk_the_subtree_on_gui(window, qapp, sample_tree, monkeypatch):
    window.results.show_outcome(analyse(scan(sample_tree)))
    root = window.results.outcome.result.root
    removed = next(node for node in root.children if node.name == "photos")
    names = {node.name for node in removed.children}
    original, threads = analysis.extension_of, []

    def extension(name):
        if name in names:
            threads.append(QThread.currentThread())
        return original(name)

    monkeypatch.setattr(analysis, "extension_of", extension)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda _path: True)
    monkeypatch.setattr(window, "rescan_folder", lambda _node: None)
    window.move_to_trash([removed])
    _wait(qapp, lambda: window._trash_worker is None)
    assert threads and all(thread is not qapp.thread() for thread in threads)
    assert root.size == 750 and removed.parent is None
    assert {row.extension for row in window.results.types_model.rows()}.isdisjoint({".jpg", ".png"})
    assert sum(row.count for row in window.results.age_model.rows()) == 4
    assert (sample_tree / "photos" / "a.jpg").read_bytes() == b"j" * 200


@pytest.mark.parametrize("discard", [False, True])
def test_stop_finishes_moved_totals_but_closing_can_discard_statistics(qapp, monkeypatch, discard):
    frozen = 1_800_000_000
    root = Node("root", True, children=[])
    moved = Node("moved.py", False, size=17, modified=frozen - 400 * 86400, parent=root)
    retained = Node("retained.bin", False, size=300, parent=root)
    root.children.extend((moved, retained))
    result = MoveResult(moved=[moved], failed=[retained])
    worker = trash_worker.TrashWorker(root, [moved, retained], [], {})
    worker.summary_now = frozen
    monkeypatch.setattr(worker, "_move_checked", lambda: result)
    entered, release = threading.Event(), threading.Event()
    original = trash_worker.summarise

    def held(*args, **kwargs):
        entered.set()
        assert release.wait(5), "statistics blocked its GUI release timer"
        return original(*args, **kwargs)

    monkeypatch.setattr(trash_worker, "summarise", held)
    worker.start()
    _wait(qapp, entered.is_set)
    try:
        worker.cancel(discard_results=discard)
        assert worker.isRunning() and not release.is_set()
        QTimer.singleShot(20, release.set)
        _wait(qapp, lambda: worker.wait(0))
        assert worker.result is result and worker.result.moved == [moved]
        assert worker.result.failed == [retained]
        assert moved.parent is root and retained.parent is root
        if discard:
            assert worker.removed_summary is None
        else:
            summary = worker.removed_summary
            assert summary.now == frozen and summary.largest == []
            assert sum(row.size for row in summary.extensions) == 17
            assert sum(row.count for row in summary.ages) == 1
            assert next(row for row in summary.ages if row.age == "two_years").size == 17
    finally:
        release.set()
        worker.wait()
        worker.deleteLater()


def test_forget_refuses_statistics_with_a_different_age_reference(window, sample_tree):
    results = window.results
    results.show_outcome(analyse(scan(sample_tree)))
    outcome = results.outcome
    node = outcome.result.root.children[0]
    prepared = analysis.summarise(node, limit=0, now=outcome.now)
    wrong = dataclasses.replace(prepared, now=outcome.now + 1)
    with pytest.raises(ValueError, match="age reference"):
        results.forget([node], removed=wrong)
    assert results.outcome is outcome and node.parent is outcome.result.root
    assert outcome.result.root.size == 1000


def test_window_close_cancels_statistics_and_keeps_completed_move_result(window, qapp, sample_tree, monkeypatch):
    window.results.show_outcome(analyse(scan(sample_tree)))
    root = window.results.outcome.result.root
    moved = next(node for node in root.children if node.name == "photos")
    entered, release = threading.Event(), threading.Event()
    original = trash_worker.summarise

    def held(*args, **kwargs):
        entered.set()
        assert release.wait(5), "closing blocked the statistics release timer"
        return original(*args, **kwargs)

    monkeypatch.setattr(trash_worker, "summarise", held)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(file_actions, "trash_receipt", lambda _path: True)
    window.move_to_trash([moved])
    worker = window._trash_worker
    _wait(qapp, entered.is_set)
    try:
        window.close()
        assert not window._close_ready and not release.is_set()
        QTimer.singleShot(20, release.set)
        _wait(qapp, lambda: window._close_ready)
        assert worker.removed_summary is None and worker.result.moved == [moved]
        assert moved.parent is root
        assert (sample_tree / "photos" / "a.jpg").read_bytes() == b"j" * 200
    finally:
        release.set()
        _wait(qapp, lambda: window._close_ready)
