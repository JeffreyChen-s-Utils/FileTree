"""Native registry ownership, Explorer quoting, explicit opt-in and the Properties ABI."""

import ctypes
import os
import runpy
import sys
import uuid
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox

from test_gui import window as window  # noqa: PLC0414 - explicit pytest fixture re-export
from je_file_tree.core.scanner import scan
from je_file_tree.gui import shell_integration as shell
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.shell_dialog import ShellIntegrationDialog


@pytest.fixture
def registry_key(monkeypatch):
    if sys.platform != "win32":
        pytest.skip("Native current-user registry test")
    import winreg

    path = rf"Software\FileTreeTests-{uuid.uuid4()}"
    monkeypatch.setattr(shell, "VERB_KEY", path)
    yield winreg, path
    # Only the exact owned fixture key is removed; never the Explorer verb.
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            children = [winreg.EnumKey(key, index) for index in range(winreg.QueryInfoKey(key)[0])]
            for child in children:
                winreg.DeleteKey(key, child)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        pass  # removal is the behavior under test


def test_real_registration_round_trip_and_update(registry_key):
    registry, path = registry_key
    assert not shell.installed()
    shell.set_enabled(True, "使用 FileTree 掃描")
    assert shell.installed()
    with registry.OpenKey(registry.HKEY_CURRENT_USER, path) as key:
        assert registry.QueryValueEx(key, "")[0] == "使用 FileTree 掃描"
        assert registry.QueryValueEx(key, "MultiSelectModel")[0] == "Single"
        with registry.OpenKey(key, "command") as command:
            assert registry.QueryValueEx(command, "")[0].endswith(' "%1"')
    shell.set_enabled(True, "Scan with FileTree")
    assert shell.installed()
    shell.set_enabled(False, "unused")
    assert not shell.installed()
    shell.set_enabled(False, "unused")


def test_never_claims_or_removes_existing_foreign_key(registry_key):
    registry, path = registry_key
    with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, path) as key:
        registry.SetValueEx(key, "", 0, registry.REG_SZ, "Other program")
    for enabled in (True, False):
        with pytest.raises(OSError, match="another application"):
            shell.set_enabled(enabled, "ours")
    with registry.OpenKey(registry.HKEY_CURRENT_USER, path) as key:
        assert registry.QueryValueEx(key, "")[0] == "Other program"


@pytest.mark.parametrize("foreign_child", [True, False])
def test_ownership_marker_does_not_allow_deleting_foreign_content(registry_key, foreign_child):
    registry, path = registry_key
    shell.set_enabled(True, "ours")
    with registry.OpenKey(registry.HKEY_CURRENT_USER, path, 0, registry.KEY_WRITE) as key:
        if foreign_child:
            registry.CreateKeyEx(key, "Foreign").Close()
        else:
            registry.SetValueEx(key, "Foreign", 0, registry.REG_SZ, "keep")
    for enabled in (True, False):
        with pytest.raises(OSError, match="not owned"):
            shell.set_enabled(enabled, "new")
    with registry.OpenKey(registry.HKEY_CURRENT_USER, path) as key:
        assert registry.QueryValueEx(key, "")[0] == "ours"


def test_launcher_command_uses_absolute_paths_and_single_quoted_placeholder(tmp_path):
    exe = str(tmp_path / "space 目錄" / "FileTree.exe")
    command = shell.launch_command(is_compiled=True, executable="unused", program_path=exe)
    assert command == f'"{os.path.abspath(exe)}" "%1"'
    source = shell.launch_command(is_compiled=False, executable=exe, program_path="ignored")
    assert "launcher.py" in source and source.endswith(' "%1"')
    assert f'"{os.path.abspath(exe)}"' in source


def test_source_launcher_bootstraps_outside_checkout(monkeypatch, tmp_path):
    from je_file_tree.gui import app
    import je_file_tree

    calls = []
    monkeypatch.setattr(app, "run", lambda: calls.append(sys.path[0]))
    monkeypatch.chdir(tmp_path)
    original = list(sys.path)
    try:
        runpy.run_path(str(Path(je_file_tree.__file__).with_name("launcher.py")), run_name="__main__")
        assert calls == [str(Path(je_file_tree.__file__).resolve().parent.parent)]
    finally:
        sys.path[:] = original


def test_dialog_reads_without_writes_cancel_and_failed_save(qapp, monkeypatch):
    changes, warnings = [], []
    monkeypatch.setattr(shell, "installed", lambda: False)
    monkeypatch.setattr(shell, "set_enabled", lambda *args: changes.append(args))
    dialog = ShellIntegrationDialog()
    assert not changes and not dialog.enabled.isChecked()
    dialog.enabled.setChecked(True)
    dialog.reject()
    assert not changes
    dialog.accept()
    assert changes == [(True, tr("shell_scan"))]
    assert dialog.result() == QDialog.DialogCode.Accepted
    dialog.deleteLater()

    def fail(*_args):
        raise PermissionError("denied")

    monkeypatch.setattr(shell, "set_enabled", fail)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(_args[-1]))
    dialog = ShellIntegrationDialog()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted and "denied" in warnings[0]
    dialog.deleteLater()


def test_properties_sets_correct_native_structure_and_fixed_verb(monkeypatch, tmp_path):
    observed = []

    class Execute:
        def __call__(self, pointer):
            info = ctypes.cast(pointer, ctypes.POINTER(shell._ShellExecuteInfo)).contents
            observed.append((info.cbSize, info.fMask, info.hwnd, info.lpVerb, info.lpFile, info.nShow))
            return 1

    class Shell32:
        ShellExecuteExW = Execute()

    class Libraries:
        shell32 = Shell32()

    monkeypatch.setattr(shell, "supported", lambda: True)
    monkeypatch.setattr(ctypes, "windll", Libraries(), raising=False)
    target = str(tmp_path / "內容, test.txt")
    assert shell.show_properties(target, 123)
    assert observed == [(ctypes.sizeof(shell._ShellExecuteInfo), 0x0C, 123, "properties", target, 1)]


def test_properties_context_menu_uses_the_clicked_entry(window, sample_tree, monkeypatch):
    from je_file_tree.gui import main_window

    root = scan(sample_tree).root
    chosen = root.children[0]
    calls = []
    monkeypatch.setattr(shell, "supported", lambda: True)
    monkeypatch.setattr(shell, "show_properties", lambda path, parent: calls.append((path, parent)) or True)

    class RecordingMenu(QMenu):
        def exec(self, _point):
            next(action for action in self.actions() if action.text() == tr("menu_properties")).trigger()

    monkeypatch.setattr(main_window, "QMenu", RecordingMenu)
    window.show_menu_for(chosen, [root], QPoint())
    assert calls[0][0] == chosen.path


def test_non_windows_has_no_shell_feature(monkeypatch):
    monkeypatch.setattr(shell, "supported", lambda: False)
    assert not shell.installed() and not shell.show_properties("anything")
    with pytest.raises(OSError, match="only on Windows"):
        shell.set_enabled(True, "ours")
