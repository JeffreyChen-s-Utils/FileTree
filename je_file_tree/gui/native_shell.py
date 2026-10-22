"""Shared Unicode Shell structure and thread-owned administrator launch."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


class ShellExecuteInfo(ctypes.Structure):
    """Windows SHELLEXECUTEINFOW, including pointer-sized handles on 64-bit hosts."""

    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]


def launch_elevated(program: str, parameters: str, folder: str) -> bool:
    """Join the runas launch in this thread's STA; never wait for or retain the new process."""
    ole = ctypes.windll.ole32
    initialise, uninitialise = ole.CoInitializeEx, ole.CoUninitialize
    initialise.argtypes, initialise.restype = [ctypes.c_void_p, wintypes.DWORD], ctypes.c_long
    uninitialise.argtypes, uninitialise.restype = [], None
    # STA + disable legacy OLE1 DDE. S_FALSE also increments this thread's COM reference count.
    if initialise(None, 0x06) not in (0, 1):
        return False
    try:
        info = ShellExecuteInfo()
        info.cbSize, info.fMask = ctypes.sizeof(info), 0x00000100  # SEE_MASK_NOASYNC
        info.lpVerb, info.lpFile = "runas", program
        info.lpParameters, info.lpDirectory, info.nShow = parameters, folder, 1
        execute = ctypes.windll.shell32.ShellExecuteExW
        execute.argtypes, execute.restype = [ctypes.POINTER(ShellExecuteInfo)], wintypes.BOOL
        return bool(execute(ctypes.byref(info)))
    finally:
        uninitialise()
