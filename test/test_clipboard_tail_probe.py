"""Exercise the real capture path with recording boundaries; native proof belongs to its CI job."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
import pytest

from tools import measure_clipboard_tail as probe


@pytest.fixture
def boundary(qapp, monkeypatch):
    previous = getattr(qapp, '_filetree_clipboard_copy', None)
    if previous is not None:
        previous.cancel()
    monkeypatch.delattr(qapp, '_filetree_clipboard_copy', raising=False)

    class Board(QObject):
        dataChanged = Signal()  # noqa: N815
        text = ''
        writes = 0
        cleared = 0

        def setText(self, text):  # noqa: N802
            self.text = text
            self.writes += 1
            self.dataChanged.emit()

        def clear(self):
            self.cleared += 1

    board = Board()
    scope = SimpleNamespace(station_name='filetree-clipboard-'+'a'*32, desktop_name='probe-'+'b'*32,
                            check=lambda: None)
    monkeypatch.setattr(QApplication, 'clipboard', staticmethod(lambda: board))

    def consumer(_scope):
        normalized = board.text.replace('\r\n', '\n')
        record = {'scope': {'station': scope.station_name, 'desktop': scope.desktop_name,
                            'pid': 123, 'noninteractive': True}, 'parent_pid': os.getpid(),
                  'normalized_sha256': hashlib.sha256(normalized.encode('utf-8')).hexdigest()}
        return SimpleNamespace(pid=123, returncode=0, poll=lambda: 0,
                               communicate=lambda **_kwargs: (json.dumps(record).encode(), b''))

    monkeypatch.setattr(probe, '_consumer', consumer)
    return scope, board


def test_probe_captures_every_quoted_unicode_row_and_retains_all_turns(qapp, boundary):
    scope, board = boundary
    report = {}
    result = probe._run_qt(qapp, scope, 30, 12, report)
    assert board.writes == 1 and board.cleared == 1 and len(board.text) > 1000
    assert '\tline\n😀' in board.text and "'=entry" in board.text
    assert result['callbacks_ms'] and result['heartbeat_ms'] and result['set_text_ms'] >= 0
    assert result['extract_ms'] >= 0 and result['native']['parent_pid'] == os.getpid()
    assert report == result and not hasattr(qapp, '_filetree_clipboard_copy')


def test_native_consumer_start_failure_quits_and_preserves_diagnostics_without_hanging(qapp, monkeypatch, boundary):
    scope, board = boundary

    def fail(_scope):
        raise OSError('modeled native start failure')

    monkeypatch.setattr(probe, '_consumer', fail)
    report = {}
    with pytest.raises(RuntimeError, match='did not finish'):
        probe._run_qt(qapp, scope, 2, 0, report)
    assert report['consumer_start_error']['message'] == 'modeled native start failure'
    assert board.cleared == 1 and not hasattr(qapp, '_filetree_clipboard_copy')


def test_stalled_native_consumer_is_stopped_only_by_its_owned_handle(qapp, monkeypatch, boundary):
    scope, board = boundary
    stopped = []
    process = SimpleNamespace(poll=lambda: None, kill=lambda: stopped.append('kill'),
                              returncode=124)

    def communicate(**_kwargs):
        stopped.append('join')
        return b'partial', b'kept native phase'

    process.communicate = communicate
    monkeypatch.setattr(probe, '_consumer', lambda _scope: process)
    monkeypatch.setattr(probe, '_GUI_WAIT_MS', 25)
    report = {}
    with pytest.raises(RuntimeError, match='did not finish'):
        probe._run_qt(qapp, scope, 2, 0, report)
    assert stopped == ['kill', 'join'] and board.cleared == 1
    assert report['consumer']['stderr'] == 'kept native phase' and report['consumer']['returncode'] == 124


@pytest.mark.parametrize(('rows', 'width'), [(0, 1), (100001, 1), (1, -1), (1, 513), (True, 1)])
def test_invalid_shapes_are_refused_before_native_construction(monkeypatch, rows, width):
    monkeypatch.setattr(probe, 'PrivateStation', lambda: pytest.fail('Native before bounds'))
    with pytest.raises(RuntimeError, match='Require 1'):
        probe._probe(rows, width)


def test_probe_refuses_a_normal_environment_before_native_or_qt_construction(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.setattr(probe, 'PrivateStation', lambda: pytest.fail('Native before runner guard'))
    with pytest.raises(RuntimeError, match='Disposable hosted'):
        probe._probe(1, 1)


def test_foreign_consumer_identity_is_rejected_before_content_verification(boundary):
    scope, _board = boundary
    payload = {'scope': {'station': 'WinSta0', 'desktop': 'Default', 'pid': 123, 'noninteractive': False},
               'parent_pid': os.getpid()}
    child = SimpleNamespace(pid=123, returncode=0, communicate=lambda **_kwargs: (json.dumps(payload).encode(), b''))
    with pytest.raises(RuntimeError, match='scope/identity'):
        probe._read_result(child, {}, scope)


@pytest.mark.parametrize('raw', [b'', b'FILETREE_CLIPBOARD_RESULT invalid\n',
                               b'FILETREE_CLIPBOARD_RESULT {}\nFILETREE_CLIPBOARD_RESULT {}\n'])
def test_driver_preserves_raw_output_without_inventing_a_missing_or_invalid_proof(raw):
    result = SimpleNamespace(stdout=raw, stderr=b'kept', returncode=1, process_observation={'status':'not-sampled'})
    proof = probe._result_proof(result, 'completed')
    assert proof['probe'] is None and proof['stdout'] == raw.decode() and proof['stderr'] == 'kept'


def test_failed_scope_guard_prevents_qt_finalization_and_switching(monkeypatch):
    stopped, deleted = [], []

    def refuse():
        raise RuntimeError('scope changed')

    def stop(code):
        stopped.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(probe.os, '_exit', stop)
    result = {}
    with pytest.raises(SystemExit):
        probe._dispose_app(SimpleNamespace(check=refuse), object(), deleted.append, result)
    assert stopped == [1] and not deleted and result['verified'] is False


@pytest.mark.parametrize('outcome', ['verified', 'unverified', 'timeout', 'start-failed'])
def test_driver_reserves_a_new_report_and_preserves_actual_child_outcomes(monkeypatch, tmp_path, outcome):
    output = tmp_path / 'owned-proof.json'
    monkeypatch.setattr(sys, 'argv', ['probe', '--rows', '2', '--width', '0', '--output', str(output)])
    monkeypatch.setattr(probe, 'disposable_runner', lambda: None)
    calls = []

    def run(command, **kwargs):
        assert output.exists() and output.read_bytes() == b''
        assert command[-5:] == ['--_probe', '--rows', '2', '--width', '0'] and kwargs == {'timeout':60}
        calls.append(command)
        if outcome == 'start-failed':
            raise OSError('modeled launch refusal')
        if outcome == 'timeout':
            raise subprocess.TimeoutExpired(command, 60, output=b'partial phase', stderr=b'kept')
        payload = {'verified':outcome == 'verified'}
        return SimpleNamespace(stdout=(probe._RESULT+json.dumps(payload)).encode(), stderr=b'kept',
                               returncode=0 if outcome == 'verified' else 7,
                               process_observation={'status':'not-sampled'})

    monkeypatch.setattr(probe, 'run_observed', run)
    assert probe.main() == (0 if outcome == 'verified' else 1)
    record = json.loads(output.read_text(encoding='utf-8'))
    assert len(calls) == 1
    assert record['outcome'] == ('completed' if outcome in ('verified','unverified') else outcome)
    if outcome == 'timeout':
        assert record['stdout'] == 'partial phase' and record['stderr'] == 'kept' and record['timeout'] == 60


def test_existing_evidence_is_never_overwritten_or_used_to_start_another_probe(monkeypatch, tmp_path):
    output = tmp_path / 'existing.json'
    output.write_text('keep', encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['probe', '--output', str(output)])
    monkeypatch.setattr(probe, 'disposable_runner', lambda: None)
    monkeypatch.setattr(probe, 'run_observed', lambda *_args, **_kwargs: pytest.fail('Existing report launched child'))
    with pytest.raises(RuntimeError, match='new evidence'):
        probe.main()
    assert output.read_text(encoding='utf-8') == 'keep'


def test_workflow_runs_native_windows_only_with_pinned_dependencies_and_preserved_failures():
    text = Path('.github/workflows/test.yml').read_text(encoding='utf-8')
    job = text.split('  windows-clipboard:\n',1)[1].split('  windows-msi:\n',1)[0]
    assert 'QT_QPA_PLATFORM: windows' in job and 'timeout-minutes: 3' in job
    assert '--require-hashes --only-binary :all: -r .github/requirements/test.txt' in job
    assert '--rows 100000 --width 80' in job and '--rows 100000 --width 512' in job
    assert 'if: always()' in job and 'windows-clipboard-*.json' in job and 'windows-clipboard-*.log' in job


def test_reader_launch_explicitly_inherits_only_the_owned_namespace_handles(monkeypatch):
    calls = []
    scope = SimpleNamespace(check=lambda: calls.append('guard'), station_name='private-station',
                            desktop_name='private-desktop', station=3, desktop=4)
    monkeypatch.setattr(subprocess, 'STARTUPINFO', SimpleNamespace, raising=False)
    monkeypatch.setattr(subprocess, 'CREATE_NO_WINDOW', 0, raising=False)

    def launch(command, **kwargs):
        assert calls == ['guard']
        assert kwargs['startupinfo'].lpAttributeList == {'handle_list':[3,4]}
        assert kwargs['close_fds'] and kwargs['creationflags'] == 0
        assert command[-5:] == ['private-station','private-desktop',str(os.getpid()),'3','4']
        calls.append('launch')
        return 'owned-reader'

    monkeypatch.setattr(subprocess, 'Popen', launch)
    assert probe._consumer(scope) == 'owned-reader' and calls == ['guard','launch']
