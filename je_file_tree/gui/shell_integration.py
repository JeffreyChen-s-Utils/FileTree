"""Opt-in Windows folder verb and native Properties, with ownership checks for registry changes."""

from __future__ import annotations

import ctypes
import os
import subprocess  # nosec B404 - command-line quoting only
import sys
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path

import je_file_tree
from je_file_tree.gui.elevation import compiled, supported

VERB_KEY = r"Software\Classes\Directory\shell\JeffreyChenFileTree"
_OWNER = "je_file_tree.folder-verb.v1"
_OWNER_VALUE = "FileTreeOwner"
_CREATED = 1
_MASK_INVOKE_ID_LIST = 0x0C


def launch_command(*, is_compiled: bool, executable: str, program_path: str) -> str:
    """Quote a fixed FileTree launcher and Explorer's single folder placeholder."""
    if is_compiled:
        arguments = [os.path.abspath(program_path)]
    else:
        windowless = Path(executable).with_name("pythonw.exe")
        program = str(windowless) if windowless.is_file() else os.path.abspath(executable)
        arguments = [program, str(Path(je_file_tree.__file__).with_name("launcher.py").resolve())]
    return subprocess.list2cmdline(arguments) + ' "%1"'


def _registry():
    import winreg  # noqa: PLC0415 - unavailable on other platforms

    return winreg


def _owned(key) -> None:
    registry = _registry()
    try:
        owner, kind = registry.QueryValueEx(key, _OWNER_VALUE)
    except FileNotFoundError as error:
        raise OSError("The Explorer verb belongs to another application") from error
    if owner != _OWNER or kind != registry.REG_SZ:
        raise OSError("The Explorer verb belongs to another application")


def installed() -> bool:
    """Read the owned verb's actual registration; no settings or registry writes."""
    if not supported():
        return False
    registry = _registry()
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, VERB_KEY) as key:
            _owned(key)
            with registry.OpenKey(key, "command") as command:
                value, kind = registry.QueryValueEx(command, "")
                return bool(value) and kind == registry.REG_SZ
    except FileNotFoundError:
        return False


@contextmanager
def _claim():
    """Use the native creation disposition so an existing unowned key is never claimed."""
    registry = _registry()
    create = ctypes.windll.advapi32.RegCreateKeyExW
    create.argtypes = [wintypes.HKEY, wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD,
                      wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HKEY),
                      ctypes.POINTER(wintypes.DWORD)]
    create.restype = wintypes.LONG
    handle, disposition = wintypes.HKEY(), wintypes.DWORD()
    result = create(registry.HKEY_CURRENT_USER, VERB_KEY, 0, None, 0, registry.KEY_READ | registry.KEY_WRITE,
                    None, ctypes.byref(handle), ctypes.byref(disposition))
    if result:
        raise ctypes.WinError(result)
    key = handle.value
    try:
        if disposition.value != _CREATED:
            _owned(key)
        registry.SetValueEx(key, _OWNER_VALUE, 0, registry.REG_SZ, _OWNER)
        yield key
    finally:
        registry.CloseKey(key)


def _install(label: str) -> None:
    registry = _registry()
    command = launch_command(is_compiled=compiled(), executable=sys.executable, program_path=sys.argv[0])
    with _claim() as key:
        _validate_shape(key)
        registry.SetValueEx(key, "", 0, registry.REG_SZ, label)
        registry.SetValueEx(key, "MultiSelectModel", 0, registry.REG_SZ, "Single")
        with registry.CreateKeyEx(key, "command") as child:
            registry.SetValueEx(child, "", 0, registry.REG_SZ, command)


def _validate_shape(key) -> None:
    registry = _registry()
    children, values, _modified = registry.QueryInfoKey(key)
    if any(registry.EnumValue(key, index)[0] not in {"", _OWNER_VALUE, "MultiSelectModel"}
           for index in range(values)):
        raise OSError("The Explorer verb contains settings not owned by FileTree")
    if children > 1 or (children and registry.EnumKey(key, 0) != "command"):
        raise OSError("The Explorer verb contains subkeys not owned by FileTree")
    if children:
        with registry.OpenKey(key, "command") as child:
            subkeys, entries, _modified = registry.QueryInfoKey(child)
            if subkeys or entries > 1 or (entries and registry.EnumValue(child, 0)[0] != ""):
                raise OSError("The Explorer command contains settings not owned by FileTree")


def _remove() -> None:
    registry = _registry()
    try:
        key = registry.OpenKey(registry.HKEY_CURRENT_USER, VERB_KEY, 0, registry.KEY_READ | registry.KEY_WRITE)
    except FileNotFoundError:
        return
    with key:
        _owned(key)
        _validate_shape(key)
        if registry.QueryInfoKey(key)[0]:
            registry.DeleteKey(key, "command")
    registry.DeleteKey(registry.HKEY_CURRENT_USER, VERB_KEY)


def set_enabled(enabled: bool, label: str) -> None:
    """Install/update or remove only FileTree's current-user folder verb; never needs elevation."""
    if not supported():
        raise OSError("Explorer integration is available only on Windows")
    if enabled:
        _install(label)
    else:
        _remove()
    notify = ctypes.windll.shell32.SHChangeNotify
    notify.argtypes = [wintypes.LONG, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p]
    notify.restype = None
    notify(0x08000000, 0, None, None)


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]


def show_properties(path: str, parent_handle: int = 0) -> bool:
    """Invoke the native Properties verb for one filesystem entry, without running its contents."""
    if not supported():
        return False
    info = _ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = _MASK_INVOKE_ID_LIST
    info.hwnd, info.lpVerb, info.lpFile, info.nShow = parent_handle, "properties", os.path.abspath(path), 1
    execute = ctypes.windll.shell32.ShellExecuteExW
    execute.argtypes = [ctypes.POINTER(_ShellExecuteInfo)]
    execute.restype = wintypes.BOOL
    return bool(execute(ctypes.byref(info)))
