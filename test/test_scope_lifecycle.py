"""Folder-scope analysis must not outlive the result or closing lifecycle."""

import threading

import pytest
from PySide6.QtCore import QTimer
from test_gui import _wait, window as window  # noqa: PLC0414 - shared fixture

from je_file_tree.core.scanner import scan
from je_file_tree.gui import scan_worker
from je_file_tree.gui.scan_worker import analyse


def _transition(results, transition, new_outcome):
    if transition == "new_scan":
        results.begin_scan()
    elif transition == "new_outcome":
        results.show_outcome(new_outcome)
    elif transition == "shutdown":
        results._scope_timer.start()
        results.wait_for_lists(wait=False)
    elif transition == "scope_off":
        results._scope_button.setChecked(False)
    else:
        results.select_node(next(node for node in results.tree_model.root.children if node.name == "photos"))
        results._rescope(force=True)


@pytest.mark.parametrize("transition", ["new_scan", "new_outcome", "shutdown", "scope_off", "replacement"])
def test_pending_scope_is_canceled_and_cannot_refill_lists(window, qapp, sample_tree, monkeypatch, transition):
    results = window.results
    results.show_outcome(analyse(scan(sample_tree)))
    queued = scan_worker.summarise(results.tree_model.root)
    new_outcome = analyse(scan(sample_tree))
    entered, release = threading.Event(), threading.Event()
    original = scan_worker.summarise
    replies = []
    original_ready = results._scope_ready

    def ready(folder, summary):
        replies.append(folder)
        original_ready(folder, summary)

    monkeypatch.setattr(results, "_scope_ready", ready)

    def held(root, *args, **kwargs):
        entered.set()
        assert release.wait(5), "scope transition blocked the GUI release timer"
        # A completed/queued result must also be invalidated, independently of traversal cancellation.
        kwargs.pop("cancel", None)
        return original(root, *args, **kwargs)

    monkeypatch.setattr(scan_worker, "summarise", held)
    results._scope_button.setChecked(True)
    worker = results._scope_worker
    _wait(qapp, entered.is_set)
    try:
        _transition(results, transition, new_outcome)
        assert results._scope_worker is not worker
        assert worker._cancel.is_set()
        assert not results._scope_timer.isActive()
        assert not release.is_set()
        worker.done.emit(queued)  # a signal already queued before cancellation must not be applied
        assert replies == []
        QTimer.singleShot(20, release.set)
        _wait(qapp, lambda: not results._list_workers)
        if transition == "new_scan":
            assert results.largest_model.rowCount() == 0
            assert results.types_model.rowCount() == 0
        elif transition == "new_outcome":
            assert results.outcome is new_outcome
            assert all(node.is_in(new_outcome.result.root) for node in results.largest_model.rows())
        elif transition == "replacement":
            assert {node.name for node in results.largest_model.rows()} == {"a.jpg", "b.png"}
        elif transition == "shutdown":
            assert results._scope_worker is None
    finally:
        release.set()
        results.wait_for_lists()


def test_cancel_during_capacity_keeps_worker_owned_and_suppresses_all_replies(qapp, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    replies = []

    def held_capacity(*_args, **_kwargs):
        entered.set()
        assert release.wait(5), "capacity cancellation blocked its GUI release timer"
        return object()

    from je_file_tree.core.node import Node

    worker = scan_worker.AnalyseWorker(Node("root", True), with_capacity=True)
    monkeypatch.setattr(scan_worker, "capacity_ledger", held_capacity)
    worker.done.connect(replies.append)
    worker.capacity_ready.connect(replies.append)
    worker.start()
    _wait(qapp, entered.is_set)
    try:
        worker.stop()
        assert worker.isRunning()
        assert not release.is_set()
        QTimer.singleShot(20, release.set)
        _wait(qapp, lambda: worker.wait(0))
        assert replies == []
    finally:
        release.set()
        worker.wait()
