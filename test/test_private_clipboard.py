"""Private station ownership fails closed before clipboard access and closes only created handles."""

import ctypes as c
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools import windows_private_clipboard as private


def _scope(monkeypatch, *, fail=None):
    scope = private.PrivateStation.__new__(private.PrivateStation)
    scope.station_name = 'filetree-clipboard-' + 'a'*32
    scope.desktop_name = 'probe-' + 'b'*32
    scope.station = scope.desktop = None
    scope.previous_station, scope.previous_desktop = 1, 2
    scope.station_changed = scope.desktop_changed = False
    scope.cleanup = []
    state = SimpleNamespace(station=1, desktop=2, calls=[], visible=False, windows={})

    def call(operation, handle):
        state.calls.append((operation, handle))
        if operation == fail and not (operation == 'desktop' and handle == 2):
            return 0
        if operation == 'station':
            state.station = handle
        elif operation == 'desktop':
            state.desktop = handle
        return 1

    def create(name, flags, access, attributes):
        state.calls.append(('create', name, flags, access))
        assert flags == 1 and attributes._obj.descriptor == 17 and attributes._obj.inherit
        return 0 if fail == 'create' else 3

    def checked(value):
        if not value:
            raise OSError('modeled native refusal')
        return value

    def create_desktop(*_args):
        assert _args[-1]._obj.descriptor == 17 and _args[-1]._obj.inherit
        if fail == 'create-desktop':
            return 0
        state.desktop = 4
        return 4

    def destroy(handle):
        state.calls.append(('destroy', handle))
        if handle in getattr(state, 'stuck', ()):
            return 0
        state.windows.pop(handle)
        if not any(name != 'IME' for name in state.windows.values()):
            state.windows = {}  # the default IME window retires with the thread's last other window
        return 1

    scope.native = SimpleNamespace(
        security=lambda: c.c_void_p(17), free=lambda pointer: state.calls.append(('free', pointer.value)),
        create_station=create, checked=checked, station=lambda: state.station,
        desktop=lambda _thread: state.desktop, thread=lambda: 7,
        name=lambda handle: {1:'WinSta0', 2:'Default', 3:scope.station_name, 4:scope.desktop_name}[handle],
        visible=lambda _handle: state.visible,
        set_station=lambda handle: call('station', handle), set_desktop=lambda handle: call('desktop', handle),
        create_desktop=create_desktop,
        close_desktop=lambda handle: call('close-desktop', handle),
        close_station=lambda handle: call('close-station', handle),
        thread_windows=lambda: list(state.windows), class_name=lambda handle: state.windows.get(handle, ''),
        is_window=lambda handle: handle in state.windows, destroy_window=destroy)
    monkeypatch.setattr(private.c, 'get_last_error', lambda: 5, raising=False)
    return scope, state


def test_create_only_scope_restores_before_closing_its_own_handles_and_is_idempotent(monkeypatch):
    scope, state = _scope(monkeypatch)
    with scope:
        assert scope.check()['noninteractive'] and state.station == 3 and state.desktop == 4
    assert state.calls[-4:] == [('desktop', 2), ('station', 1), ('close-desktop', 4), ('close-station', 3)]
    assert ('free', 17) in state.calls
    assert all(item['ok'] for item in scope.cleanup)
    before = list(state.calls)
    scope.close()
    assert state.calls == before


def test_existing_or_denied_station_never_sets_scope_or_closes_a_borrowed_handle(monkeypatch):
    scope, state = _scope(monkeypatch, fail='create')
    with pytest.raises(OSError, match='refusal'):
        scope.__enter__()
    assert [call[0] for call in state.calls] == ['create', 'free']
    assert state.station == 1 and state.desktop == 2 and not scope.cleanup


@pytest.mark.parametrize('failure', ['create-desktop', 'desktop'])
def test_partial_creation_restores_scope_and_closes_only_new_objects(monkeypatch, failure):
    scope, state = _scope(monkeypatch, fail=failure)
    with pytest.raises(OSError, match='refusal'):
        scope.__enter__()
    assert state.station == 1 and state.desktop == 2
    closed = [item for item in state.calls if item[0].startswith('close-')]
    assert ('close-station', 3) in closed
    assert all(handle not in (1, 2) for _operation, handle in closed)


def test_failed_restoration_retains_error_and_does_not_close_a_still_assigned_station(monkeypatch):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    scope.native.set_desktop = lambda _handle: 0
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        scope.close()
    assert scope.cleanup[0] == {'action': 'restore-desktop', 'ok': False, 'error': 5}
    assert not any(call[0].startswith('close-') for call in state.calls)


@pytest.mark.parametrize('change', ['station', 'desktop', 'visible'])
def test_active_scope_or_visibility_change_is_refused(monkeypatch, change):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    if change == 'visible':
        state.visible = True
    else:
        setattr(state, change, 1 if change == 'station' else 2)
    with pytest.raises(RuntimeError, match='scope changed'):
        scope.check()


@pytest.mark.parametrize(('station', 'desktop'), [('WinSta0', 'Default'), ('filetree-clipboard-x', 'probe-x')])
def test_foreign_scope_names_are_refused_before_any_native_query(station, desktop):
    with pytest.raises(RuntimeError, match='Unknown private'):
        private.guard(object(), station, desktop)


def test_imported_qt_prevents_station_construction_before_native_calls(monkeypatch):
    monkeypatch.setattr(private, 'disposable_runner', lambda: None)
    monkeypatch.setitem(sys.modules, 'PySide6.QtWidgets', object())
    monkeypatch.setattr(private, '_Native', lambda: pytest.fail('Native API before fresh-process guard'))
    with pytest.raises(RuntimeError, match='precede Qt'):
        private.PrivateStation()


@pytest.mark.parametrize('module', ['PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets'])
def test_every_qt_namespace_is_refused_in_a_fresh_child_before_any_native_call(module):
    script = '''
import json,sys
from tools import windows_private_clipboard as private
private.disposable_runner=lambda:None
sys.modules[sys.argv[1]]=object()
calls=[]
private._Native=lambda:calls.append('native-called') or object()
try:
    private.PrivateStation()
except RuntimeError as error:
    print(json.dumps({'calls':calls,'message':str(error)}))
else:
    raise AssertionError('Qt namespace was accepted')
'''
    result = subprocess.run(  # noqa: S603 - fresh stdlib-only guard fixture; native constructor is a recording stub
        [sys.executable, '-c', script, module], capture_output=True, check=True, timeout=10,
        env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1])))
    import json
    assert json.loads(result.stdout) == {'calls': [], 'message': 'Private station must precede Qt imports'}


def test_native_security_descriptor_is_protected_owner_and_system_only():
    native = private._Native.__new__(private._Native)
    seen = []

    def convert(sddl, revision, pointer, optional):
        seen.append((sddl, revision, optional))
        pointer._obj.value = 17
        return True

    native.descriptor = convert
    assert native.security().value == 17
    assert seen == [('D:P(A;;GA;;;OW)(A;;GA;;;SY)', 1, None)]


def test_reader_refuses_wrong_parent_before_native_api(monkeypatch):
    monkeypatch.setattr(private, 'disposable_runner', lambda: None)
    monkeypatch.setattr(private, '_Native', lambda: pytest.fail('Native API before parent guard'))
    with pytest.raises(RuntimeError, match='parent differs'):
        private.read_private('unused', 'unused', -1, 0, 0)


@pytest.mark.parametrize('payload', ['quoted\t資料夾\r\n😀\0', 'missing terminator'])
def test_native_reader_bounds_and_decodes_utf16_and_closes_even_on_invalid_text(monkeypatch, payload):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    buffer = c.create_string_buffer(payload.encode('utf-16-le'))
    calls = []
    scope.native.open_clipboard = lambda _owner: calls.append('open') or True
    scope.native.clipboard_data = lambda _format: calls.append('data') or 42
    scope.native.size = lambda _handle: len(payload.encode('utf-16-le'))
    scope.native.lock = lambda _handle: calls.append('lock') or c.addressof(buffer)
    scope.native.unlock = lambda _handle: calls.append('unlock') or True
    scope.native.close_clipboard = lambda: calls.append('close') or True
    monkeypatch.setattr(private, '_Native', lambda: scope.native)
    monkeypatch.setattr(private, 'disposable_runner', lambda: None)
    monkeypatch.setattr(private, 'before_qt', lambda: None)
    if payload.endswith('\0'):
        result = private.read_private(scope.station_name, scope.desktop_name, os.getppid(), 3, 4)
        assert result['normalized_sha256'] == hashlib.sha256(payload[:-1].replace('\r\n','\n').encode()).hexdigest()
    else:
        with pytest.raises(RuntimeError, match='terminator'):
            private.read_private(scope.station_name, scope.desktop_name, os.getppid(), 3, 4)
    assert calls == ['open', 'data', 'lock', 'unlock', 'close'] and state.station == 3


@pytest.mark.parametrize('size', [0, 3, 128*1024*1024+2])
def test_native_reader_refuses_invalid_sizes_before_locking_or_reading_memory(monkeypatch, size):
    scope, _state = _scope(monkeypatch)
    scope.__enter__()
    calls = []
    scope.native.open_clipboard = lambda _owner: calls.append('open') or True
    scope.native.clipboard_data = lambda _format: 42
    scope.native.size = lambda _handle: size
    scope.native.lock = lambda _handle: pytest.fail('Unbounded native allocation read')
    scope.native.close_clipboard = lambda: calls.append('close') or True
    monkeypatch.setattr(private, '_Native', lambda: scope.native)
    monkeypatch.setattr(private, 'disposable_runner', lambda: None)
    monkeypatch.setattr(private, 'before_qt', lambda: None)
    with pytest.raises(RuntimeError, match='payload size'):
        private.read_private(scope.station_name, scope.desktop_name, os.getppid(), 3, 4)
    assert calls == ['open', 'close']


@pytest.mark.parametrize('handles', [(1, 4), (3, 2)])
def test_reader_rejects_foreign_inherited_handles_before_changing_namespace(monkeypatch, handles):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    before = list(state.calls)
    with pytest.raises(RuntimeError, match='handle identity'):
        private._join(scope.native, scope.station_name, scope.desktop_name, handles)
    assert state.calls == before


def test_reader_explicitly_joins_only_its_validated_inherited_handles(monkeypatch):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    state.station, state.desktop = 1, 2
    private._join(scope.native, scope.station_name, scope.desktop_name, (3,4))
    assert state.station == 3 and state.desktop == 4
    assert state.calls[-2:] == [('station',3),('desktop',4)]


def test_windows_left_on_the_owned_desktop_are_retired_before_restoring(monkeypatch):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    state.windows = {11: 'Qt6112ThemeChangeObserverWindow', 12: 'IME'}
    scope.close()
    assert ('destroy', 12) not in state.calls  # the system IME window is never destroyed directly
    assert state.calls.index(('destroy', 11)) < state.calls.index(('desktop', 2))
    assert scope.cleanup[0] == {'action': 'retire-window', 'class': 'Qt6112ThemeChangeObserverWindow',
                                'ok': True, 'error': 0}
    assert all(item['ok'] for item in scope.cleanup) and ('close-desktop', 4) in state.calls


def test_unretired_windows_are_reported_and_keep_cleanup_failed(monkeypatch):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    state.windows, state.stuck = {11: 'Stubborn', 12: 'IME'}, {11}
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        scope.close()
    assert {'action': 'retire-window', 'class': 'Stubborn', 'ok': False, 'error': 5} in scope.cleanup
    assert {'action': 'residual-windows', 'ok': False, 'classes': ['Stubborn', 'IME']} in scope.cleanup


def test_windows_are_not_touched_once_the_thread_left_the_owned_desktop(monkeypatch):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    state.desktop, state.windows = 2, {11: 'Foreign'}
    scope.close()
    assert not any(call[0] == 'destroy' for call in state.calls)
    assert not any(item['action'].endswith('window') or item['action'] == 'residual-windows'
                   for item in scope.cleanup)


def test_an_unreadable_desktop_name_is_recorded_and_restoration_still_runs(monkeypatch):
    scope, state = _scope(monkeypatch)
    scope.__enter__()
    names = scope.native.name

    def name(handle):
        if handle == 4 and state.desktop == 4:
            raise OSError('modeled name refusal')
        return names(handle)
    scope.native.name = name
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        scope.close()
    assert scope.cleanup[0] == {'action': 'retire-windows', 'ok': False, 'error': 'modeled name refusal'}
    assert ('desktop', 2) in state.calls and ('station', 1) in state.calls


def test_helper_imports_where_ctypes_has_no_windows_callback_type():
    """Linux/macOS collect these tests too: Windows-only ctypes names must wait for ``_Native``."""
    code = "import ctypes; vars(ctypes).pop('WINFUNCTYPE', None); import tools.windows_private_clipboard"
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1],  # noqa: S603
                            capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
