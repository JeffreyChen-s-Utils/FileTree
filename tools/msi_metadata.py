"""Read an MSI's release identity through native read-only database APIs; never install or launch it."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import ctypes
import functools
from pathlib import Path
import sys
from typing import Any

_PROPERTIES = ("ProductCode", "UpgradeCode", "ProductVersion", "ProductName", "Manufacturer", "ALLUSERS")
_STRING_CHARS = 512
_TEMPLATE_PROPERTY = 7
_STRING_TYPE = 30


@functools.cache
def _kernel() -> Any:
    if sys.platform != "win32":
        raise OSError("MSI release metadata requires Windows")
    kernel = ctypes.WinDLL("msi.dll", winmode=0x800)
    handle, pointer = ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)
    kernel.MsiOpenDatabaseW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, pointer]
    kernel.MsiDatabaseOpenViewW.argtypes = [handle, ctypes.c_wchar_p, pointer]
    kernel.MsiViewExecute.argtypes = [handle, handle]
    kernel.MsiCreateRecord.argtypes, kernel.MsiCreateRecord.restype = [ctypes.c_uint32], handle
    kernel.MsiRecordSetStringW.argtypes = [handle, ctypes.c_uint32, ctypes.c_wchar_p]
    kernel.MsiViewFetch.argtypes = [handle, pointer]
    kernel.MsiRecordGetStringW.argtypes = [handle, ctypes.c_uint32, ctypes.c_wchar_p, pointer]
    kernel.MsiGetSummaryInformationW.argtypes = [handle, ctypes.c_wchar_p, ctypes.c_uint32, pointer]
    kernel.MsiSummaryInfoGetPropertyW.argtypes = [handle, ctypes.c_uint32, pointer,
                                                ctypes.POINTER(ctypes.c_int32), ctypes.c_void_p,
                                                ctypes.c_wchar_p, pointer]
    kernel.MsiViewClose.argtypes = kernel.MsiCloseHandle.argtypes = [handle]
    for name in ("MsiOpenDatabaseW", "MsiDatabaseOpenViewW", "MsiViewExecute", "MsiViewFetch",
                 "MsiRecordGetStringW", "MsiRecordSetStringW", "MsiGetSummaryInformationW",
                 "MsiSummaryInfoGetPropertyW",
                 "MsiViewClose", "MsiCloseHandle"):
        getattr(kernel, name).restype = ctypes.c_uint32
    return kernel


def _success(code: int) -> None:
    if code:
        raise OSError(code, "Native read-only MSI metadata failed")


@contextmanager
def _opened(kernel: Any, operation: Any, *arguments: Any) -> Iterator[int]:
    result = ctypes.c_uint32()
    _success(operation(*arguments, ctypes.byref(result)))
    if not result.value:
        raise ValueError("Missing native MSI metadata handle")
    try:
        yield result.value
    finally:
        _success(kernel.MsiCloseHandle(result.value))


@contextmanager
def _parameters(kernel: Any, name: str) -> Iterator[int]:
    handle = kernel.MsiCreateRecord(1)
    if not handle:
        raise ValueError("Missing MSI parameter record")
    try:
        _success(kernel.MsiRecordSetStringW(handle, 1, name))
        yield handle
    finally:
        _success(kernel.MsiCloseHandle(handle))


def _property(kernel: Any, database: int, name: str) -> str:
    # Only fixed property names enter the query; no command or package action is executed.
    if name not in _PROPERTIES:
        raise ValueError("Unsupported MSI release property")
    query = "SELECT `Value` FROM `Property` WHERE `Property` = ?"
    with (_opened(kernel, kernel.MsiDatabaseOpenViewW, database, query) as view,
          _parameters(kernel, name) as parameters):
        _success(kernel.MsiViewExecute(view, parameters))
        try:
            with _opened(kernel, kernel.MsiViewFetch, view) as record:
                buffer, length = ctypes.create_unicode_buffer(_STRING_CHARS), ctypes.c_uint32(_STRING_CHARS)
                _success(kernel.MsiRecordGetStringW(record, 1, buffer, ctypes.byref(length)))
                return buffer.value
        finally:
            _success(kernel.MsiViewClose(view))


def _template(kernel: Any, database: int) -> str:
    with _opened(kernel, kernel.MsiGetSummaryInformationW, database, None, 0) as summary:
        kind, number = ctypes.c_uint32(), ctypes.c_int32()
        buffer, length = ctypes.create_unicode_buffer(_STRING_CHARS), ctypes.c_uint32(_STRING_CHARS)
        _success(kernel.MsiSummaryInfoGetPropertyW(summary, _TEMPLATE_PROPERTY, ctypes.byref(kind),
                                                  ctypes.byref(number), None, buffer, ctypes.byref(length)))
        if kind.value != _STRING_TYPE:
            raise ValueError("Unsupported MSI platform summary type")
        return buffer.value


def read_properties(path: Path) -> dict[str, str]:
    """Read fixed identity/version/scope properties and platform summary without installing the MSI.

    All native handles close on failure; missing, unbounded or unsupported metadata fails visibly.
    The caller must capture/verify the ordinary artifact and its hash around these observations.
    """
    kernel = _kernel()
    # NULL persistence is MSIDBOPEN_READONLY; no install session/custom actions are created.
    with _opened(kernel, kernel.MsiOpenDatabaseW, str(path.absolute()), None) as database:
        result = {name: _property(kernel, database, name) for name in _PROPERTIES}
        result["Template"] = _template(kernel, database)
        return result
