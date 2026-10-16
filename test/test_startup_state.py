"""Restart metadata preserves scan kinds and refuses malformed or ambiguous handoffs."""

import ctypes
import hashlib
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings, Qt

from test_gui import _wait
from test_workspace_gui import workspace as workspace  # noqa: PLC0414 - owned lifecycle
from je_file_tree.gui import app
from je_file_tree.gui.startup_state import MAX_TABS, WorkspaceState, workspace_state


def _argument(value):
    return "--restore-workspace=" + json.dumps(value, ensure_ascii=False)


@pytest.mark.parametrize("tabs,active", [
    ((None, None), 1),
    (("C:/單一 & folder", ("D:/two", "E:/three"), None), 1),
    ((("D:/one",),), 0),
    (("-literal folder",), 0),
    ((("C:/quote\" and newline\n", "D:/尾\\"), None), 1),
])
def test_roundtrip_keeps_blank_single_and_combined_scopes(tabs, active):
    state = WorkspaceState(tabs, active)
    assert workspace_state(state.arguments()) == state
    assert workspace_state(["--background", *state.arguments()]) == state


def test_single_folder_and_blank_startup_keep_existing_arguments():
    assert WorkspaceState(("ordinary folder",)).arguments() == ["ordinary folder"]
    assert WorkspaceState((None,)).arguments() == []
    assert workspace_state(["--background", "ordinary folder"]) is None


@pytest.mark.parametrize("value", [
    None, [], {}, {"version": 2, "tabs": [None], "active": 0},
    {"version": True, "tabs": [None], "active": 0},
    {"version": 1, "tabs": [], "active": 0},
    {"version": 1, "tabs": [None] * (MAX_TABS+1), "active": 0},
    {"version": 1, "tabs": [[]], "active": 0},
    {"version": 1, "tabs": [["root"] * 257], "active": 0},
    {"version": 1, "tabs": [""], "active": 0},
    {"version": 1, "tabs": ["null\0root"], "active": 0},
    {"version": 1, "tabs": [True], "active": 0},
    {"version": 1, "tabs": [[1]], "active": 0},
    {"version": 1, "tabs": [None], "active": True},
    {"version": 1, "tabs": [None], "active": -1},
    {"version": 1, "tabs": [None], "active": 1},
    {"version": 1, "tabs": [None], "active": 0, "approval": True},
])
def test_invalid_state_never_becomes_scan_or_operation_authority(value):
    with pytest.raises(ValueError):
        workspace_state([_argument(value)])


@pytest.mark.parametrize("arguments", [
    ["--restore-workspace"], ["--restore-workspace="], ["--restore-workspace={"],
    ["--restore-workspace=" + "[" * 2000],
    ["--restore-workspace=" + " " * (1024*1024+1)],
    ['--restore-workspace={"version":1,"version":1,"tabs":[null],"active":0}'],
    [_argument({"version": 1, "tabs": [None], "active": 0}), "folder"],
    [_argument({"version": 1, "tabs": [None], "active": 0})] * 2,
])
def test_missing_ambiguous_deep_or_oversized_arguments_are_refused(arguments):
    with pytest.raises(ValueError):
        workspace_state(arguments)


class _Tab:
    def __init__(self):
        self.scans = []

    def start_scan(self, path):
        self.scans.append(("single", path))

    def start_scan_roots(self, roots):
        self.scans.append(("combined", roots))


class _Workspace:
    def __init__(self):
        self.windows, self.active = [_Tab()], 0
        self.tabs = SimpleNamespace(count=lambda: len(self.windows), setCurrentIndex=self.activate)
        self.background = SimpleNamespace(can_hide=False)
        self.events = []

    @property
    def current(self):
        return self.windows[self.active]

    def activate(self, index):
        self.active = index

    def add_tab(self):
        self.windows.append(_Tab())
        self.active = len(self.windows)-1
        return self.current

    def show(self):
        self.events.append("show")

    def start_services(self):
        self.events.append("services")


def test_startup_dispatches_each_scan_kind_and_active_tab(qapp, monkeypatch, tmp_path):
    state = WorkspaceState((None, "single", ("combined one", "combined two"), ("one virtual",)), 2)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    target = _Workspace()
    monkeypatch.setattr(app, "QSettings", lambda: settings)
    monkeypatch.setattr(app, "wants_admin_prompt", lambda _settings: False)
    monkeypatch.setattr(app, "create_workspace", lambda *_args: target)
    monkeypatch.setattr(type(qapp), "exec", lambda _self: 0)
    assert app.main(state.arguments()) == 0
    assert [window.scans for window in target.windows] == [[], [("single", "single")],
            [("combined", ("combined one", "combined two"))], [("combined", ("one virtual",))]]
    assert target.active == 2 and target.events == ["show", "services"]


def test_invalid_startup_reports_literal_error_before_any_administrator_prompt(qapp, monkeypatch, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    messages = []
    monkeypatch.setattr(app, "QSettings", lambda: settings)
    monkeypatch.setattr(app, "wants_admin_prompt", lambda _settings: pytest.fail("invalid data requested elevation"))
    monkeypatch.setattr(app.QMessageBox, "exec", lambda box: messages.append((box.text(), box.textFormat())) or 0)
    assert app.main(["--restore-workspace={"]) == 2
    assert messages and "Invalid workspace restart data" in messages[0][0]
    assert messages[0][1] == Qt.TextFormat.PlainText


def test_owned_roots_rescan_without_becoming_mutation_approval(workspace, qapp, tmp_path):
    roots = [tmp_path / name for name in ("single", "two", "three")]
    for index, root in enumerate(roots):
        root.mkdir()
        (root / "kept.bin").write_bytes(b"payload" * (index+1))
    before = [hashlib.sha256((root / "kept.bin").read_bytes()).hexdigest() for root in roots]
    state = WorkspaceState((str(roots[0]), tuple(map(str, roots[1:])), None), 1)
    state.restore(workspace)
    _wait(qapp, lambda: all(window._worker is None for window in workspace.operations.windows))
    first, combined, empty = workspace.operations.windows
    assert first.results.outcome.result.root.path == str(roots[0])
    assert combined.results.outcome.result.root.path is None
    assert {node.path for node in combined.results.outcome.result.root.children} == set(map(str, roots[1:]))
    assert empty.results.outcome is None and workspace.current is combined
    assert not workspace.operations.busy
    assert [hashlib.sha256((root / "kept.bin").read_bytes()).hexdigest() for root in roots] == before


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows command-line decoding")
@pytest.mark.parametrize("prefix", [["C:/Program Files/FileTree.exe"],
                                   ["C:/Program Files/Python/pythonw.exe", "-m", "je_file_tree"]])
def test_windows_command_line_preserves_workspace_metadata_verbatim(prefix):
    state = WorkspaceState((None, ("D:/資料 & spaces", 'E:/quoted"name\\tail'), "C:/single"), 1)
    arguments = state.arguments()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes, parse.restype = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)], ctypes.POINTER(ctypes.c_wchar_p)
    free = ctypes.windll.kernel32.LocalFree
    free.argtypes, free.restype = [ctypes.c_void_p], ctypes.c_void_p
    count = ctypes.c_int()
    pointer = parse(subprocess.list2cmdline([*prefix, *arguments]), ctypes.byref(count))
    assert pointer
    try:
        restored = [pointer[index] for index in range(count.value)]
        assert restored == [*prefix, *arguments]
        assert workspace_state(restored[len(prefix):]) == state
    finally:
        assert not free(pointer)
