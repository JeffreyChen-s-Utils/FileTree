"""Background work gives way to the window: the gate the workers wait at."""

from __future__ import annotations

import threading
import time

import pytest

from je_file_tree.core import pacing
from je_file_tree.core.pacing import Gate


def _timed_give_way(gate: Gate) -> float:
    """How long ``give_way`` took on another thread."""
    took: list[float] = []

    def work() -> None:
        started = time.perf_counter()
        gate.give_way()
        took.append(time.perf_counter() - started)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join(5)
    return took[0]


def test_an_open_gate_lets_workers_through_at_once() -> None:
    gate = Gate()
    assert gate.is_open
    assert _timed_give_way(gate) < 0.01


def test_a_closed_gate_holds_workers_but_never_longer_than_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pacing, "PAUSE_LIMIT", 0.2)
    gate = Gate()
    gate.close()
    took = _timed_give_way(gate)
    assert 0.15 <= took < 1.0, "held while the window is busy, then one more step: nothing hangs on it"


def test_opening_the_gate_lets_a_waiting_worker_go_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pacing, "PAUSE_LIMIT", 5.0)
    gate = Gate()
    gate.close()
    threading.Timer(0.05, gate.open).start()
    assert _timed_give_way(gate) < 1.0


def test_the_thread_that_closed_the_gate_never_waits_at_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pacing, "PAUSE_LIMIT", 5.0)
    gate = Gate()
    gate.close()
    started = time.perf_counter()
    gate.give_way()  # the window running core code itself (a synchronous scan, say) must not stall
    assert time.perf_counter() - started < 0.1
