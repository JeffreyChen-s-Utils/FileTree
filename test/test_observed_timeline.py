"""Later owned-child samples preserve the one target execution and its original deadline."""

import subprocess
from types import SimpleNamespace

import pytest

from tools import observed_process as runner


def _timeline(monkeypatch, *, ends=30, code=0, startup=0, finishing=0, interrupt=False):
    state = SimpleNamespace(now=0, launches=0, waits=[], samples=[], finished=[], killed=[], joined=[])

    class Observer:
        def __init__(self, pid):
            assert pid == 123
            state.samples.append(state.now)
            if interrupt and len(state.samples) == 2:
                raise KeyboardInterrupt
            self.record = {'status': 'observed', 'child_pid': pid, 'records': [{'sample': len(state.samples)}]}
            state.now += startup

        def finish(self):
            state.finished.append(self.record)
            state.now += finishing
            return self.record

    class Child:
        pid = 123
        returncode = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def poll(self):
            return self.returncode

        def communicate(self, timeout=None):
            state.waits.append(timeout)
            if timeout is not None and state.now + timeout < ends:
                state.now += timeout
                raise subprocess.TimeoutExpired(['owned'], timeout, output=b'partial')
            if timeout is None:
                self.returncode = -1
            else:
                state.now = ends
                self.returncode = code
            return b'complete output', b'complete error'

        def kill(self):
            state.killed.append(state.now)
            self.returncode = -1

        def wait(self):
            state.joined.append(True)

    def launch(command, **kwargs):
        assert command == ['owned']
        assert kwargs == {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE, 'env': None}
        state.launches += 1
        return Child()

    monkeypatch.setattr(runner.time, 'monotonic', lambda: state.now)
    monkeypatch.setattr(runner.sys, 'platform', 'win32')
    monkeypatch.setattr(runner.subprocess, 'Popen', launch)
    monkeypatch.setattr(runner, '_Observer', Observer)
    return state


@pytest.mark.parametrize('code', [0, 7, 'timeout'])
def test_later_sample_reaches_the_final_window_without_retrying_or_resetting_deadline(monkeypatch, code):
    state = _timeline(monkeypatch, ends=30 if code == 'timeout' else 19, code=code)
    if code == 'timeout':
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            runner.run_observed(['owned'], timeout=20)
        result = caught.value
        assert result.timeout == 20 and state.killed == [20]
    else:
        result = runner.run_observed(['owned'], timeout=20)
        assert result.returncode == code and not state.killed
    assert state.samples == [5, 15] and len(state.finished) == 2 and state.launches == 1
    assert result.stdout == b'complete output' and result.stderr == b'complete error'
    observation = result.process_observation
    assert observation['records'] == [{'sample': 1}]
    assert observation['later_samples'] == [state.finished[1]]
    assert len(state.waits) == 3 + (code == 'timeout')


def test_child_finishing_between_samples_keeps_original_single_sample_contract(monkeypatch):
    state = _timeline(monkeypatch, ends=12)
    result = runner.run_observed(['owned'], timeout=20)
    assert state.samples == [5] and state.launches == 1 and not state.killed
    assert result.process_observation is state.finished[0] and 'later_samples' not in result.process_observation


def test_observer_startup_and_finish_cost_are_subtracted_before_the_final_wait(monkeypatch):
    state = _timeline(monkeypatch, startup=2, finishing=1)
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        runner.run_observed(['owned'], timeout=20)
    assert state.samples == [5, 15] and state.waits == [5, 8, 3, None]
    assert state.killed == [20] and caught.value.timeout == 20 and state.launches == 1
    assert len(state.finished) == 2


def test_interrupted_later_observer_start_reaps_target_and_preserves_interruption(monkeypatch):
    state = _timeline(monkeypatch, interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        runner.run_observed(['owned'], timeout=20)
    assert state.samples == [5, 15] and state.killed == [15] and state.joined == [True]
    assert state.launches == 1 and len(state.finished) == 1


@pytest.mark.parametrize(('timeout', 'after', 'expected'), [(10, 5, [5]), (20, 20, []), (20, 7, [7, 15])])
def test_sampling_is_bounded_deduplicated_and_never_precedes_the_requested_delay(monkeypatch, timeout, after, expected):
    state = _timeline(monkeypatch)
    with pytest.raises(subprocess.TimeoutExpired):
        runner.run_observed(['owned'], timeout=timeout, sample_after=after)
    assert state.samples == expected and state.killed == [timeout] and state.launches == 1


def test_slow_observer_cleanup_happens_only_after_the_target_is_reaped(monkeypatch):
    state = _timeline(monkeypatch, finishing=6)
    with pytest.raises(subprocess.TimeoutExpired):
        runner.run_observed(['owned'], timeout=20)
    assert state.samples == [5, 15] and state.launches == 1
    assert len(state.finished) == 2 and state.killed == [20] and state.now == 32
