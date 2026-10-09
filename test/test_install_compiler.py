"""Compiler installation preserves the existing wheel/hash restrictions and fails visibly."""

import subprocess
import sys
from unittest.mock import Mock

import pytest

from tools import install_compiler as compiler


def test_shared_compiler_installs_from_current_interpreter_without_credentials(monkeypatch):
    run = Mock()
    monkeypatch.setattr(compiler.subprocess, "run", run)
    compiler.install()
    commands = [call.args[0] for call in run.call_args_list]
    assert len(commands) == 6
    assert all(command[:4] == [sys.executable, "-m", "pip", "install"] for command in commands)
    assert all("--only-binary" in command and ":all:" in command for command in commands)
    assert all(call.kwargs["check"] and call.kwargs["timeout"] == 900 for call in run.call_args_list)
    source = [command for command in commands if "--no-binary" in command]
    assert len(source) == 1 and source[0][source[0].index("--no-binary") + 1] == "nuitka"
    assert [command[-1] for command in commands if "--require-hashes" in command] == [
        ".github/requirements/reports.txt", ".github/requirements/archives.txt", ".github/requirements/photos.txt"]


def test_failed_install_stops_before_other_tools(monkeypatch):
    run = Mock(side_effect=subprocess.CalledProcessError(1, "pip"))
    monkeypatch.setattr(compiler.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        compiler.install()
    assert run.call_count == 1
