"""Owned HKCU Run registration with a separate strict receipt; no elevation or startup approval edits."""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes

from je_file_tree.gui.autostart import OWNER, Registration, windows_command

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RECEIPT_KEY = r"Software\JE-Chen\FileTree\Startup"
VALUE = "FileTree.BackgroundMonitor"
_CREATED = 1


def _registry():
    import winreg  # noqa: PLC0415 - Windows-only native API

    return winreg


def _value(key, name):
    try:
        return _registry().QueryValueEx(key, name)
    except FileNotFoundError:
        return None


def _command():
    registry = _registry()
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY) as key:
            return _value(key, VALUE)
    except FileNotFoundError:
        return None


def _receipt(key) -> str | None:
    registry = _registry()
    children, count, _modified = registry.QueryInfoKey(key)
    values = {registry.EnumValue(key, index)[0] for index in range(count)}
    if children or values not in ({"Owner"}, {"Owner", "Command"}) or _value(key, "Owner") != (OWNER, registry.REG_SZ):
        raise OSError("Startup receipt contains settings not owned by FileTree")
    command = _value(key, "Command")
    if command is not None and (command[1] != registry.REG_SZ or not isinstance(command[0], str) or not command[0]):
        raise OSError("Invalid FileTree startup receipt")
    return None if command is None else command[0]


def _recorded() -> str | None:
    registry = _registry()
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, RECEIPT_KEY) as key:
            return _receipt(key)
    except FileNotFoundError:
        return None


def inspect() -> Registration:
    """Recognize only the exact Run value captured in FileTree's owned receipt."""
    command, recorded = _command(), _recorded()
    if command is not None and (recorded is None or command != (recorded, _registry().REG_SZ)):
        raise OSError("The startup entry belongs to another application or was changed")
    return Registration(command is not None, "HKCU\\" + RUN_KEY + "\\" + VALUE)


@contextmanager
def _claim():
    registry = _registry()
    create = ctypes.windll.advapi32.RegCreateKeyExW
    create.argtypes = [wintypes.HKEY, wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD,
                      wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HKEY), ctypes.POINTER(wintypes.DWORD)]
    create.restype = wintypes.LONG
    handle, disposition = wintypes.HKEY(), wintypes.DWORD()
    result = create(registry.HKEY_CURRENT_USER, RECEIPT_KEY, 0, None, 0, registry.KEY_READ | registry.KEY_WRITE,
                    None, ctypes.byref(handle), ctypes.byref(disposition))
    if result:
        raise ctypes.WinError(result)
    try:
        if disposition.value == _CREATED:
            registry.SetValueEx(handle.value, "Owner", 0, registry.REG_SZ, OWNER)
        else:
            _receipt(handle.value)
        yield handle.value
    finally:
        registry.CloseKey(handle.value)


def _install(command: str) -> None:
    registry = _registry()
    captured = _command()
    inspect()
    with _claim() as receipt:
        previous = _receipt(receipt)
        if captured is not None and captured != (previous, registry.REG_SZ):
            raise OSError("Startup ownership changed before registration")
        if previous is not None and previous != command and captured is not None:
            raise OSError("Remove the previous FileTree startup entry before registering a different program")
        registry.SetValueEx(receipt, "Command", 0, registry.REG_SZ, command)
        registry.FlushKey(receipt)  # durable ownership before the executable Run value is published
        with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, RUN_KEY, 0,
                                  registry.KEY_READ | registry.KEY_WRITE) as run:
            if _value(run, VALUE) != captured:
                raise OSError("Startup entry changed before registration")
            registry.SetValueEx(run, VALUE, 0, registry.REG_SZ, command)
            registry.FlushKey(run)


def _remove() -> None:
    registry = _registry()
    state = inspect()
    recorded = _recorded()
    if state.installed:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY, 0,
                              registry.KEY_READ | registry.KEY_WRITE) as run:
            if _value(run, VALUE) != (recorded, registry.REG_SZ) or _recorded() != recorded:
                raise OSError("Startup entry changed before removal")
            registry.DeleteValue(run, VALUE)
            registry.FlushKey(run)
    # Retain the private receipt: it is inert, supports recovery after an interrupted write,
    # and avoids deleting a registry key that another process could have replaced.


def apply(enabled: bool, arguments: tuple[str, ...]) -> Registration:
    """Install/remove the fixed current-user value, refusing foreign or changed registrations."""
    if enabled:
        _install(windows_command(arguments))
    else:
        _remove()
    return inspect()
