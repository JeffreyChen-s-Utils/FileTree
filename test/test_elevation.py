"""Asking for administrator rights: the restart command, the start-up prompt and the window's offers."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import je_file_tree
from je_file_tree.core import scanner
from je_file_tree.gui import app, elevation, i18n
from je_file_tree.gui.app import create_window, wants_admin_prompt
from je_file_tree.gui.main_window import ASK_ADMIN_KEY, MainWindow
from je_file_tree.gui.qt_translation import apply_qt_translation


def test_a_built_program_restarts_itself_with_the_same_arguments(tmp_path: Path) -> None:
    program, parameters, folder = elevation.relaunch_command(
        ["D:\\My Files"], is_compiled=True, executable="ignored", program_path=str(tmp_path / "FileTree.exe"))
    assert program == str(tmp_path / "FileTree.exe")
    assert parameters == '"D:\\My Files"'
    assert folder == os.getcwd()


def test_from_python_it_runs_the_package_with_the_windowless_interpreter(tmp_path: Path) -> None:
    (tmp_path / "python.exe").write_bytes(b"")
    (tmp_path / "pythonw.exe").write_bytes(b"")
    program, parameters, folder = elevation.relaunch_command(
        ["C:\\data"], is_compiled=False, executable=str(tmp_path / "python.exe"), program_path="start_file_tree.py")
    assert program == str(tmp_path / "pythonw.exe")
    assert parameters == "-m je_file_tree C:\\data"
    assert Path(folder) == Path(je_file_tree.__file__).resolve().parents[1]


def test_without_a_windowless_interpreter_it_uses_the_one_it_has(tmp_path: Path) -> None:
    program, _, _ = elevation.relaunch_command(
        [], is_compiled=False, executable=str(tmp_path / "python3"), program_path="x")
    assert program == str(tmp_path / "python3")


def test_only_windows_is_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(elevation.sys, "platform", "linux")
    assert not elevation.supported()
    assert not elevation.is_elevated()
    assert not elevation.can_elevate()
    assert not elevation.relaunch_elevated(["x"]), "nothing to start where there is no prompt"


def test_the_check_answers_a_plain_yes_or_no() -> None:
    assert isinstance(elevation.is_elevated(), bool)
    assert elevation.can_elevate() == (elevation.supported() and not elevation.is_elevated())


def test_the_start_up_prompt_follows_the_setting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(elevation, "can_elevate", lambda: True)
    assert wants_admin_prompt(settings), "on by default, like TreeSize"
    settings.setValue(ASK_ADMIN_KEY, False)
    assert not wants_admin_prompt(settings)
    settings.setValue(ASK_ADMIN_KEY, True)
    monkeypatch.setattr(elevation, "can_elevate", lambda: False)
    assert not wants_admin_prompt(settings), "already an administrator, or not Windows"


def test_main_stops_when_the_elevated_copy_started(monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(app, "wants_admin_prompt", lambda _settings: True)
    monkeypatch.setattr(elevation, "relaunch_elevated", lambda arguments: started.append(arguments) or True)
    monkeypatch.setattr(app, "create_window", lambda *_args: pytest.fail("no window when the new copy runs"))
    assert app.main(["C:\\data"]) == 0
    assert started == [["C:\\data"]]


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(elevation, "can_elevate", lambda: True)
    monkeypatch.setattr(elevation, "supported", lambda: True)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "en")
    main = create_window(settings)
    yield main
    main.close()
    main.deleteLater()
    i18n.set_language(i18n.DEFAULT_LANGUAGE)
    apply_qt_translation(i18n.DEFAULT_LANGUAGE)


def test_the_menu_offers_a_restart_and_the_start_up_setting(window: MainWindow) -> None:
    assert window.results._problems_bar.isHidden(), "no offer before a scan found denied folders"
    assert window._actions["elevate"].isVisible()
    assert window._actions["ask_admin"].isVisible()
    assert window._actions["ask_admin"].isChecked()
    window._actions["ask_admin"].trigger()
    assert str(window.settings.value(ASK_ADMIN_KEY)).lower() == "false"


def test_restarting_passes_the_folder_and_a_declined_prompt_keeps_this_copy(
        window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    asked: list[list[str]] = []
    monkeypatch.setattr(elevation, "relaunch_elevated", lambda arguments: asked.append(arguments) or False)
    window._last_path = str(tmp_path)
    window.restart_as_admin()
    assert asked == [[str(tmp_path)]]
    assert window.statusBar().currentMessage() == "FileTree is still running without administrator rights."
    closed: list[bool] = []
    monkeypatch.setattr(window, "close", lambda: closed.append(True))
    monkeypatch.setattr(elevation, "relaunch_elevated", lambda _arguments: True)
    window.restart_as_admin()
    assert closed == [True]


def test_denied_folders_bring_the_offer_to_the_problems_tab(window: MainWindow, qapp: QApplication,
                                                            sample_tree: Path,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    locked = str(sample_tree / "photos")
    real_scandir = os.scandir

    def scandir(path: str):
        if path == locked:
            raise PermissionError(13, "Access is denied")
        return real_scandir(path)

    monkeypatch.setattr(scanner.os, "scandir", scandir)
    window.start_scan(str(sample_tree))
    deadline = time.monotonic() + 10
    while window.results.outcome is None:
        assert time.monotonic() < deadline
        qapp.processEvents()
        time.sleep(0.01)
    bar = window.results._problems_bar
    assert not bar.isHidden(), "shown on the Problems tab (a tab that is not current hides its page, not the bar)"
    requested: list[bool] = []
    asked: list[list[str]] = []
    monkeypatch.setattr(elevation, "relaunch_elevated", lambda arguments: asked.append(arguments) or False)
    window.results.elevate_requested.connect(lambda: requested.append(True))
    window.results._elevate_button.click()
    assert requested == [True]
    assert asked == [[str(sample_tree)]], "the button restarts FileTree on the same folder"
