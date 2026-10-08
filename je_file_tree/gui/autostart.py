"""Explicit per-user login registration; never register or launch during construction."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import plistlib
import subprocess  # nosec B404 - Windows command-line quoting only
import sys

import je_file_tree
from je_file_tree.gui.elevation import compiled

OWNER = "je_file_tree.background.v1"
LABEL = "io.github.jechen.FileTree.background"
MAX_BYTES = 16384
_MAX_ARGUMENT = 4096
_CONTROL_LIMIT = 32
_DELETE_CHARACTER = 127
_RUN_LIMIT = 260


@dataclass(frozen=True)
class Registration:
    """Actual registration and its literal native location, not a saved preference."""

    installed: bool
    target: str


def launch_arguments(*, is_compiled: bool, executable: str, program_path: str) -> tuple[str, ...]:
    """Use absolute programs and the source launcher without a shell or working-directory dependency."""
    if is_compiled:
        arguments = (os.path.abspath(program_path), "--background")
    else:
        windowless = Path(executable).with_name("pythonw.exe")
        program = str(windowless) if sys.platform == "win32" and windowless.is_file() else executable
        launcher = Path(je_file_tree.__file__).with_name("launcher.py").absolute()
        arguments = (os.path.abspath(program), str(launcher), "--background")
    validate_arguments(arguments)
    return arguments


def validate_arguments(arguments: tuple[str, ...]) -> None:
    """Refuse malformed, relative or unbounded registration commands."""
    if (not isinstance(arguments, tuple) or len(arguments) not in (2, 3)
            or arguments[-1] != "--background"):
        raise ValueError("Invalid FileTree startup arguments")
    for argument in arguments:
        if (not isinstance(argument, str) or not argument or len(argument) > _MAX_ARGUMENT
                or any(ord(char) < _CONTROL_LIMIT or ord(char) == _DELETE_CHARACTER for char in argument)):
            raise ValueError("Invalid FileTree startup argument")
    if any(not os.path.isabs(argument) for argument in arguments[:-1]):
        raise ValueError("Startup programs must be absolute paths")


def windows_command(arguments: tuple[str, ...]) -> str:
    """Quote literal Windows arguments within the Run key's native command limit."""
    validate_arguments(arguments)
    command = subprocess.list2cmdline(arguments)
    if len(command.encode("utf-16-le")) // 2 > _RUN_LIMIT:
        raise ValueError("Windows startup command exceeds the 260-character limit")
    return command


def desktop_entry(arguments: tuple[str, ...]) -> bytes:
    """Build one canonical desktop entry with fixed metadata and literal Exec arguments."""
    validate_arguments(arguments)
    # Field codes inside quoted arguments are undefined by the specification. Refuse rather than expand them.
    if any("%" in argument for argument in arguments):
        raise ValueError("Linux startup paths containing percent signs are unsupported")
    if "=" in arguments[0]:
        raise ValueError("Linux startup executable paths containing equal signs are unsupported")
    quoted = []
    for argument in arguments:
        escaped = "".join("\\" + char if char in '\\"`$' else char for char in argument)
        quoted.append('"' + escaped.replace("\\", "\\\\") + '"')
    receipt = json.dumps(arguments, ensure_ascii=True, separators=(",", ":"))
    # JSON backslashes also need the desktop-entry general string escaping rule.
    receipt = receipt.replace("\\", "\\\\")
    text = ("[Desktop Entry]\nType=Application\nName=FileTree\nTerminal=false\n"
            f"Exec={' '.join(quoted)}\nX-FileTree-Owner={OWNER}\nX-FileTree-Arguments={receipt}\n")
    return text.encode("utf-8")


def launch_agent(arguments: tuple[str, ...]) -> bytes:
    """Build next-login-only user-agent metadata; no KeepAlive or immediate launchctl invocation."""
    validate_arguments(arguments)
    return plistlib.dumps({"Label": LABEL, "ProgramArguments": list(arguments), "RunAtLoad": True,
                          "ProcessType": "Background", "EnvironmentVariables": {"FILETREE_STARTUP_OWNER": OWNER}})


def registration() -> Registration:
    """Read actual per-user state without creating directories, registry keys or processes."""
    if sys.platform == "win32":
        from je_file_tree.gui.startup_windows import inspect  # noqa: PLC0415 - platform dispatch

        return inspect()
    if sys.platform in ("linux", "darwin"):
        from je_file_tree.gui.startup_posix import inspect  # noqa: PLC0415 - platform dispatch

        return inspect()
    raise OSError("Per-user startup is unsupported on this platform")


def set_enabled(enabled: bool) -> Registration:
    """Apply an explicit choice only to a recognized current-user registration; never start a process."""
    if type(enabled) is not bool:
        raise ValueError("Startup selection must be a boolean")
    arguments = launch_arguments(is_compiled=compiled(), executable=sys.executable, program_path=sys.argv[0])
    if sys.platform == "win32":
        from je_file_tree.gui.startup_windows import apply  # noqa: PLC0415 - platform dispatch

        return apply(enabled, arguments)
    if sys.platform in ("linux", "darwin"):
        from je_file_tree.gui.startup_posix import apply  # noqa: PLC0415 - platform dispatch

        return apply(enabled, arguments)
    raise OSError("Per-user startup is unsupported on this platform")
