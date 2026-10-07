"""Recognize Windows-managed space by anchored paths; FileTree must never move these entries itself."""

from __future__ import annotations

import ntpath
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass

_DRIVE_LENGTH = 2


@dataclass(frozen=True, slots=True)
class SystemFile:
    """Stable explanation and Windows settings/tool keys, with no executable user input."""

    kind: str
    tool: str


def system_file(path: str, *, platform: str = sys.platform,
                environ: Mapping[str, str] | None = None) -> SystemFile | None:
    """Recognize only drive-root/installed-Windows namespaces, never arbitrary matching basenames."""
    if platform != 'win32':
        return None
    environ = os.environ if environ is None else environ
    target = ntpath.normcase(ntpath.normpath(path))
    if target.startswith('\\\\?\\'):
        target = target[4:]
    drive, tail = ntpath.splitdrive(target)
    if len(drive) != _DRIVE_LENGTH or drive[1] != ':' or not tail.startswith('\\'):
        return None
    windows = environ.get('WINDIR') or environ.get('SystemRoot', '')
    windows = ntpath.normcase(ntpath.normpath(windows)) if windows else ''
    return _volume_file(target, drive, tail, windows) or _windows_file(target, windows, environ)


def _volume_file(target: str, drive: str, tail: str, windows: str) -> SystemFile | None:
    root_entries = (('pagefile.sys', 'pagefile', 'memory'), ('swapfile.sys', 'swapfile', 'memory'),
                    ('Windows.old', 'old', 'cleanup'), ('$Recycle.Bin', 'recycle', 'storage'),
                    ('System Volume Information', 'restore', 'restore'))
    for name, kind, tool in root_entries:
        if _inside(target, drive + '\\' + name.lower()):
            return SystemFile(kind, tool)
    if windows and ntpath.splitdrive(windows)[0] == drive and tail == '\\hiberfil.sys':
        return SystemFile('hibernate', 'power')
    return None


def _windows_file(target: str, windows: str, environ: Mapping[str, str]) -> SystemFile | None:
    namespaces = (('WinSxS', 'winsxs'), ('SoftwareDistribution\\Download', 'updates'),
                  ('ServiceProfiles\\NetworkService\\AppData\\Local\\Microsoft\\Windows\\'
                   'DeliveryOptimization\\Cache', 'delivery'),
                  ('SoftwareDistribution\\DeliveryOptimization', 'delivery'))
    for relative, kind in namespaces:
        if windows and _inside(target, ntpath.join(windows, relative).lower()):
            return SystemFile(kind, 'cleanup')
    program_data = environ.get('ProgramData', '')
    if program_data and _inside(target, ntpath.normcase(ntpath.join(
            program_data, 'Microsoft', 'Windows', 'DeliveryOptimization', 'Cache'))):
        return SystemFile('delivery', 'cleanup')
    return None


def _inside(path: str, namespace: str) -> bool:
    return path == namespace or path.startswith(namespace.rstrip('\\') + '\\')
