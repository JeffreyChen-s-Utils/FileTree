"""Read-only filesystem owner identities; Windows capture is optional because it adds metadata calls."""

from __future__ import annotations

import ctypes
import functools
import os
import stat
import sys
from typing import Any

from je_file_tree.core.snapshot import pack_snapshot

OwnerID = int | bytes
_ELSEWHERE = 0x1000 | 0x40000 | 0x400000
_SID_HEADER = 8
_SID_SUBAUTHORITIES = 15
_SID_MAXIMUM = _SID_HEADER + _SID_SUBAUTHORITIES * 4


@functools.lru_cache(maxsize=4096)
def _shared(key: OwnerID) -> OwnerID:
    # One owner slot measured +8 bytes/entry versus +28 for a copied SID snapshot suffix.
    return key


def file_owner(path: str, info: os.stat_result, *, windows: bool = False) -> OwnerID | None:
    """Capture POSIX uid from the existing stat, or an opted-in Windows owner SID; failures stay unknown.

    Regular files only, with no content reads or privilege changes. Windows skips cloud/offline data
    and rechecks no-follow metadata after the path-based security query; this is not a transaction.
    Native queries measured 0.452 s / 9,616 files versus a 0.234 s scan before integration, so Windows
    capture stays off by default. Names resolve once per displayed owner on the analysis worker.
    """
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_reparse_tag", 0) in (0xA0000003, 0xA000000C):
        return None
    if sys.platform != "win32":
        uid = getattr(info, "st_uid", None)
        return _shared(uid) if type(uid) is int and uid >= 0 else None
    if not windows or getattr(info, "st_file_attributes", 0) & _ELSEWHERE:
        return None
    try:
        owner = _named_owner(path)
        if owner is not None and pack_snapshot(os.lstat(path)) == pack_snapshot(info):
            return _shared(owner)
    except OSError:
        return None  # Recorded files remain readable; the Users view counts their owner as unknown.
    return None


def _named_owner(path: str) -> bytes | None:
    api, kernel = _windows_api()
    sid, descriptor = ctypes.c_void_p(), ctypes.c_void_p()
    code = api.GetNamedSecurityInfoW(path, 1, 1, ctypes.byref(sid), None, None, None, ctypes.byref(descriptor))
    try:
        if code or not sid.value or not api.IsValidSid(sid):
            return None
        length = api.GetLengthSid(sid)
        return ctypes.string_at(sid, length) if _SID_HEADER <= length <= _SID_MAXIMUM else None
    finally:
        if descriptor.value:
            kernel.LocalFree(descriptor)


def owner_identifier(owner: OwnerID | None) -> str:
    """Stable uid/SID identifier; None is an unavailable owner, never the current process user."""
    if owner is None:
        return ""
    if isinstance(owner, int):
        return f"uid:{owner}"
    if (len(owner) < _SID_HEADER or owner[0] != 1 or owner[1] > _SID_SUBAUTHORITIES
            or len(owner) != _SID_HEADER + owner[1] * 4):
        raise ValueError("Invalid recorded owner SID")
    authority = "0x" + owner[2:8].hex() if any(owner[2:4]) else str(int.from_bytes(owner[2:8], "big"))
    parts = [int.from_bytes(owner[index:index + 4], "little") for index in range(8, len(owner), 4)]
    return "-".join(str(part) for part in ("S", 1, authority, *parts))


def owner_name(owner: OwnerID | None) -> str:
    """Resolve a known identity read-only; unavailable account names fall back to the raw uid/SID."""
    identifier = owner_identifier(owner)
    if owner is None:
        return ""
    if isinstance(owner, int):
        try:
            import pwd  # noqa: PLC0415 - unavailable on Windows; identity still has a fallback.
            return pwd.getpwuid(owner).pw_name or identifier
        except (ImportError, KeyError, OSError):
            return identifier  # Identity is still known even when the account catalogue is unavailable.
    if sys.platform != "win32":
        return identifier
    api, _kernel = _windows_api()
    sid = ctypes.create_string_buffer(owner)
    name, domain = ctypes.create_unicode_buffer(1024), ctypes.create_unicode_buffer(1024)
    name_size, domain_size, kind = ctypes.c_ulong(1024), ctypes.c_ulong(1024), ctypes.c_ulong()
    found = api.LookupAccountSidW(None, sid, name, ctypes.byref(name_size), domain, ctypes.byref(domain_size),
                                  ctypes.byref(kind))
    if not found or not name.value:
        return identifier
    return f"{domain.value}\\{name.value}" if domain.value else name.value


@functools.cache
def _windows_api() -> tuple[Any, Any]:
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetNamedSecurityInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.c_ulong] + [
        ctypes.POINTER(ctypes.c_void_p)] * 5
    api.GetNamedSecurityInfoW.restype = ctypes.c_ulong
    api.IsValidSid.argtypes, api.IsValidSid.restype = [ctypes.c_void_p], ctypes.c_int
    api.GetLengthSid.argtypes, api.GetLengthSid.restype = [ctypes.c_void_p], ctypes.c_ulong
    api.LookupAccountSidW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_wchar_p,
                                    ctypes.POINTER(ctypes.c_ulong), ctypes.c_wchar_p,
                                    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong)]
    api.LookupAccountSidW.restype = ctypes.c_int
    kernel.LocalFree.argtypes, kernel.LocalFree.restype = [ctypes.c_void_p], ctypes.c_void_p
    return api, kernel
