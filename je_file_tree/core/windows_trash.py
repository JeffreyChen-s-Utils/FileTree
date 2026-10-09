"""Refuse known unsafe or unverified Windows Qt recycling before source dispatch."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import re
import stat
import sys
import threading

from je_file_tree.core.compression import file_system
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.node import Node
from je_file_tree.core.snapshot import unpack_snapshot
from je_file_tree.core.trash_size import _windows_usage

_MIB = 1024 * 1024
_HEADROOM = _MIB
_FIXED_DRIVE = 3
_BUFFER = 1024
_DWORD_MAX = (1 << 32) - 1
_POLICY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
_VOLUME_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume"
_GUID = re.compile(r"\\\\\?\\Volume(\{[0-9a-fA-F-]{36}\})\\\Z")


@dataclass(frozen=True, slots=True)
class RecyclePolicy:
    """Observed current-user volume preferences; these are refusal limits, never guaranteed OS quota."""

    root: str
    volume_id: str
    maximum: int
    disabled: bool


def _volume(path: str) -> tuple[str, str]:
    kernel = ctypes.WinDLL("kernel32.dll", winmode=0x800, use_last_error=True)
    kernel.GetVolumePathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetVolumeNameForVolumeMountPointW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    kernel.GetDriveTypeW.restype = ctypes.c_uint32
    root, identifier = ctypes.create_unicode_buffer(_BUFFER), ctypes.create_unicode_buffer(_BUFFER)
    if not kernel.GetVolumePathNameW(path, root, len(root)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not re.fullmatch(r"[A-Za-z]:\\", root.value) or kernel.GetDriveTypeW(root.value) != _FIXED_DRIVE:
        raise ValueError("Windows recycling requires a verified local fixed drive")
    if file_system(root.value) != "NTFS":
        raise ValueError("Windows recycling requires a verified NTFS scope")
    if not kernel.GetVolumeNameForVolumeMountPointW(root.value, identifier, len(identifier)):
        raise ctypes.WinError(ctypes.get_last_error())
    match = _GUID.fullmatch(identifier.value)
    if match is None:
        raise ValueError("Windows recycling volume identity is unavailable")
    return root.value, match[1]


def _dword(registry, handle, name: str) -> int:
    value, kind = registry.QueryValueEx(handle, name)
    if (kind != registry.REG_DWORD or not isinstance(value, int) or isinstance(value, bool) or
            not 0 <= value <= _DWORD_MAX):
        raise ValueError("Windows recycling preference has an unsupported format")
    return value


def observed_policy(path: str) -> RecyclePolicy:
    """Read fixed-drive/GUID and current-user preferences; never create keys or infer absent limits."""
    import winreg  # noqa: PLC0415 - native provider is Windows-only

    root, identifier = _volume(path)
    disabled = False
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, _POLICY_KEY, 0, winreg.KEY_READ) as handle:
                value = _dword(winreg, handle, "NoRecycleFiles")
                if value not in (0, 1):
                    raise ValueError("Unknown Windows recycling policy")
                disabled |= bool(value)
        except FileNotFoundError:
            # An absent disabling policy is distinct from an absent per-volume capacity proof.
            continue
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _VOLUME_KEY + "\\" + identifier, 0, winreg.KEY_READ) as handle:
        maximum = _dword(winreg, handle, "MaxCapacity")
        nuke = _dword(winreg, handle, "NukeOnDelete")
    if nuke not in (0, 1) or maximum <= 0:
        raise ValueError("Windows recycling preferences are unknown")
    return RecyclePolicy(root, identifier, maximum * _MIB, disabled or bool(nuke))


def _source_reason(node: Node, cancel: threading.Event | None) -> str | None:
    if node.path is None or node.snapshot is None or node.is_link or node.size < 0:
        return "recycle_unverified"
    coverage = coverage_of(node, cancel=cancel)
    if coverage is None:
        return "cancelled"
    if not coverage.complete or not coverage.can_clean(node):
        return "recycle_unverified"
    try:
        captured = unpack_snapshot(node.snapshot)
    except ValueError:
        return "recycle_unverified"
    if not node.is_dir and (not stat.S_ISREG(captured.mode) or captured.size != node.size):
        return "recycle_unverified"
    return None


def _policy_reason(path: str, size: int) -> str | None:
    try:
        policy = observed_policy(path)
        if policy.disabled:
            return "recycle_disabled"
        usage = _windows_usage(policy.root)
        if not usage.complete or usage.size < 0 or usage.count < 0:
            return "recycle_unverified"
        if size + usage.size + _HEADROOM > policy.maximum:
            return "recycle_capacity"
        if policy != observed_policy(path):
            return "recycle_unverified"
    except (OSError, ValueError):
        return "recycle_unverified"
    return None


def recycle_reason(node: Node, cancel: threading.Event | None = None) -> str | None:
    """Veto unsafe Windows Qt Trash; passing is observational and never grants source authority.

    Native Qt 6.11.2 CI reported success/source disappearance for 64 MiB sparse files outside
    the observed small-volume limit with no bin payload. Refuse unknown/disabled policy, incomplete
    named sizes, or a selection plus existing native bin bytes and headroom beyond the observed
    preference. A fresh repeated policy/volume check rejects changed settings. OS preferences and
    concurrent arrivals are not transactionally locked; this is no guarantee of reversible retention.
    Caller must separately revalidate exact source snapshots and obtain ordinary Trash approval.
    """
    if sys.platform != "win32":
        return None
    if cancel is not None and cancel.is_set():
        return "cancelled"
    reason = _source_reason(node, cancel)
    if reason is not None:
        return reason
    reason = _policy_reason(node.path, node.size)
    return "cancelled" if cancel is not None and cancel.is_set() else reason
