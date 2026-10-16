"""Mocked Shell invocation verifies STA balance and completed launch without a UAC prompt."""

import ctypes
import sys
import threading
from types import SimpleNamespace

import pytest

from PySide6.QtWidgets import QWidget
from test_gui import _wait

from je_file_tree.gui import elevation, native_shell
from je_file_tree.gui.elevation_dialog import ElevationWorker


class _Call:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


@pytest.mark.parametrize("hresult", [0, 1, -2147417850, 0x80010106])
@pytest.mark.parametrize("outcome", [True, False, "error"])
def test_launch_balances_sta_and_joins_only_the_launch(monkeypatch, hresult, outcome, tmp_path):
    calls = []
    program, parameters, folder = str(tmp_path / "程式.exe"), '"D:\\folder & files"', str(tmp_path)

    def execute(pointer):
        info = ctypes.cast(pointer, ctypes.POINTER(native_shell.ShellExecuteInfo)).contents
        calls.append(("execute", info.cbSize, info.fMask, info.lpVerb, info.lpFile,
                      info.lpParameters, info.lpDirectory, info.nShow, info.hProcess))
        if outcome == "error":
            raise OSError("native failure")
        return int(outcome)

    ole = SimpleNamespace(CoInitializeEx=_Call(lambda *args: calls.append(("init", *args)) or hresult),
                          CoUninitialize=_Call(lambda: calls.append(("uninit",))))
    libs = SimpleNamespace(ole32=ole, shell32=SimpleNamespace(ShellExecuteExW=_Call(execute)))
    monkeypatch.setattr(ctypes, "windll", libs, raising=False)
    if hresult in (0, 1) and outcome == "error":
        with pytest.raises(OSError, match="native failure"):
            native_shell.launch_elevated(program, parameters, folder)
    else:
        assert native_shell.launch_elevated(program, parameters, folder) is (hresult in (0, 1) and outcome is True)
    assert calls[0] == ("init", None, 0x06)
    if hresult in (0, 1):
        assert calls[1] == ("execute", ctypes.sizeof(native_shell.ShellExecuteInfo), 0x100, "runas",
                            program, parameters, folder, 1, None)
        assert calls[-1] == ("uninit",)
    else:
        assert calls == [("init", None, 0x06)]


def _apartment_state(ole):
    query = ole.CoGetApartmentType
    query.argtypes, query.restype = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)], ctypes.c_long
    kind, qualifier = ctypes.c_int(-1), ctypes.c_int(-1)
    result = query(ctypes.byref(kind), ctypes.byref(qualifier))
    return ctypes.c_uint32(result).value, kind.value, qualifier.value


def _assert_balanced(before, after, initialised):
    if initialised == 1:
        assert before == after, "existing STA lost its owned COM reference"
    else:
        # No explicit thread reference remains: implicit process MTA may appear/disappear independently.
        assert after[0] == 0x800401F0 or after == (0, 1, 1), "a thread-owned STA reference leaked"


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows COM apartment APIs")
@pytest.mark.parametrize("outer_sta", [False, True])
def test_owned_qt_worker_balances_real_sta_with_mocked_shell(qapp, monkeypatch, tmp_path, outer_sta):

    ole = ctypes.windll.ole32
    initialise, uninitialise = ole.CoInitializeEx, ole.CoUninitialize
    initialise.argtypes, initialise.restype = [ctypes.c_void_p, ctypes.c_ulong], ctypes.c_long
    uninitialise.argtypes, uninitialise.restype = [], None
    observed = {"results": []}

    def init(*args):
        result = initialise(*args)
        observed["results"].append(result)
        return result

    def execute(pointer):
        info = ctypes.cast(pointer, ctypes.POINTER(native_shell.ShellExecuteInfo)).contents
        observed.update(during=_apartment_state(ole), thread=threading.get_ident(), mask=info.fMask,
                        verb=info.lpVerb, process_handle=info.hProcess)
        return 1

    wrapped_ole = SimpleNamespace(CoInitializeEx=_Call(init), CoUninitialize=_Call(uninitialise))
    libraries = SimpleNamespace(ole32=wrapped_ole, shell32=SimpleNamespace(ShellExecuteExW=_Call(execute)))
    monkeypatch.setattr(ctypes, "windll", libraries)

    def relaunch(_arguments):
        observed["entry"] = _apartment_state(ole)
        owned = initialise(None, 0x06) if outer_sta else None
        observed["outer_result"] = owned
        try:
            observed["before"] = _apartment_state(ole)
            result = native_shell.launch_elevated(str(tmp_path / "unexecuted.exe"), "literal", str(tmp_path))
            observed["after"] = _apartment_state(ole)
            return result
        finally:
            if owned in (0, 1):
                uninitialise()
            observed["released"] = _apartment_state(ole)

    monkeypatch.setattr(elevation, "relaunch_elevated", relaunch)
    parent = QWidget()
    worker = ElevationWorker([], parent)
    worker.start()
    try:
        _wait(qapp, lambda: worker.wait(0))
        assert observed["during"][0] == 0 and observed["during"][1] in (0, 3)  # STA / main STA
        assert len(observed["results"]) == 1 and observed["results"][0] in (0, 1)
        _assert_balanced(observed["before"], observed["after"], observed["results"][0])
        if outer_sta:
            assert observed["outer_result"] in (0, 1) and observed["results"] == [1]
            _assert_balanced(observed["entry"], observed["released"], observed["outer_result"])
        assert observed["thread"] != threading.get_ident()
        assert observed["mask"] == 0x100 and observed["verb"] == "runas"
        assert observed["process_handle"] is None and worker.started_copy and worker.error is None
        assert ctypes.sizeof(native_shell.ShellExecuteInfo) == (112 if ctypes.sizeof(ctypes.c_void_p) == 8 else 60)
    finally:
        worker.wait()
        parent.deleteLater()
