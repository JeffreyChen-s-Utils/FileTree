"""Administrator rights on Windows, asked for the way TreeSize asks for them.

Some folders (other users' profiles, parts of Windows, System Volume
Information) can only be read by an administrator. A running program cannot
raise its own rights, so FileTree starts a second copy of itself through the
Windows "runas" verb, which shows the UAC prompt; when the user accepts, the
first copy closes. A declined prompt changes nothing: FileTree keeps running
and lists the folders it could not read under Problems.
"""

from __future__ import annotations

import ctypes
import os
import subprocess  # nosec B404 - only list2cmdline, to quote the arguments
import sys

import file_tree

_SHOW_NORMAL = 1
# ShellExecute returns a value above 32 when it started the program.
_STARTED_ABOVE = 32


def supported() -> bool:
    """Whether this platform has a prompt to ask for administrator rights (Windows only)."""
    return sys.platform == "win32"


def is_elevated() -> bool:
    """Whether FileTree already runs with administrator rights."""
    if not supported():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def can_elevate() -> bool:
    """Whether restarting as administrator would give FileTree more rights than it has."""
    return supported() and not is_elevated()


def compiled() -> bool:
    """Whether this is a program built with Nuitka (it puts ``__compiled__`` into every compiled module)."""
    return "__compiled__" in globals()


def relaunch_command(arguments: list[str], *, is_compiled: bool, executable: str,
                     program_path: str) -> tuple[str, str, str]:
    """The program, its quoted parameters and the working folder that start FileTree again.

    A built program starts itself (``program_path``, which a one-file build
    keeps pointing at the file the user started). From Python it is
    ``-m file_tree`` run by the windowless interpreter next to ``executable``
    when there is one, from the folder that holds the package so the import
    works from a source copy too.
    """
    if is_compiled:
        return os.path.abspath(program_path), subprocess.list2cmdline(arguments), os.getcwd()
    windowless = os.path.join(os.path.dirname(executable), "pythonw.exe")
    program = windowless if os.path.isfile(windowless) else executable
    package_parent = os.path.dirname(os.path.dirname(os.path.abspath(file_tree.__file__)))
    return program, subprocess.list2cmdline(["-m", "file_tree", *arguments]), package_parent


def relaunch_elevated(arguments: list[str]) -> bool:
    """Start FileTree again as administrator (Windows shows its prompt); True when the new copy started."""
    if not can_elevate():
        return False
    program, parameters, folder = relaunch_command(
        arguments, is_compiled=compiled(), executable=sys.executable, program_path=sys.argv[0])
    shell_execute = ctypes.windll.shell32.ShellExecuteW
    shell_execute.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                              ctypes.c_wchar_p, ctypes.c_int]
    shell_execute.restype = ctypes.c_void_p  # an HINSTANCE: pointer-sized, not an int
    result = shell_execute(None, "runas", program, parameters, folder, _SHOW_NORMAL)
    return (result or 0) > _STARTED_ABOVE
