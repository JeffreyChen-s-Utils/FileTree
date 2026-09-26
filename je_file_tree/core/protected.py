"""Places whose moving to the Recycle Bin can break the system or programs: FileTree asks twice first.

The list is per platform and read from the environment (``%WINDIR%``, ``%ProgramFiles%``, the home
folder…), so it follows the machine rather than guessing drive letters. A place protects either
itself and everything inside it (the Windows folder, installed programs, programs' settings) or
only itself (a user's profile folder: its documents may go, the folder itself should not). Temporary
folders and caches are *free* even inside a protected place (``C:\\Windows\\Temp``, ``~/Library/Caches``):
they are what a clean-up is for. The most specific place that covers a path decides.
"""

from __future__ import annotations

import ntpath
import os
import posixpath
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import ModuleType

SYSTEM, PROGRAMS, SETTINGS, PROFILE = "system", "programs", "settings", "profile"
REASONS = (SYSTEM, PROGRAMS, SETTINGS, PROFILE)
FREE = "free"  # a place inside a protected one that may go all the same

_WINDOWS: tuple[tuple[str, str, bool], ...] = (  # (environment variable, reason, everything inside too)
    ("WINDIR", SYSTEM, True),
    ("ProgramFiles", PROGRAMS, True),
    ("ProgramFiles(x86)", PROGRAMS, True),
    ("ProgramW6432", PROGRAMS, True),
    ("ProgramData", SETTINGS, True),
    ("APPDATA", SETTINGS, True),  # Roaming: programs' settings
    ("LOCALAPPDATA", SETTINGS, False),  # Local: itself only, its caches may go
    ("USERPROFILE", PROFILE, False),
    ("TEMP", FREE, True),
    ("TMP", FREE, True),
)
_LINUX_SYSTEM = ("/bin", "/boot", "/etc", "/lib", "/lib32", "/lib64", "/sbin", "/usr", "/var", "/snap")
_MAC_SYSTEM = ("/System", "/Library", "/bin", "/sbin", "/usr", "/private", "/etc", "/var")


@dataclass(frozen=True, slots=True)
class Protection:
    """A place: its path, why it is protected (one of ``REASONS``, or ``FREE``) and whether its inside is too."""

    path: str
    reason: str
    inside: bool = True


def protected_places(platform: str = sys.platform, environ: Mapping[str, str] | None = None,
                     home: str | None = None) -> list[Protection]:
    """The places of this machine (or of ``platform`` with the given environment and home, for tests)."""
    environ = os.environ if environ is None else environ
    if platform == "win32":
        return _windows_places(environ)
    home = home if home is not None else os.path.expanduser("~")
    if platform == "darwin":
        return [*(Protection(place, SYSTEM) for place in _MAC_SYSTEM), Protection("/Applications", PROGRAMS),
                Protection(_under(home, "Library"), SETTINGS), Protection(_under(home, "Library/Caches"), FREE),
                Protection("/private/tmp", FREE), Protection("/private/var/folders", FREE),
                Protection(home, PROFILE, inside=False), Protection("/Users", PROFILE, inside=False)]
    return [*(Protection(place, SYSTEM) for place in _LINUX_SYSTEM), Protection("/opt", PROGRAMS),
            Protection(_under(home, ".config"), SETTINGS), Protection(_under(home, ".local/share"), SETTINGS, False),
            Protection("/tmp", FREE), Protection("/var/tmp", FREE),  # noqa: S108 - paths compared, never written
            Protection(home, PROFILE, inside=False), Protection("/home", PROFILE, inside=False)]


def protection_of(path: str, places: Iterable[Protection], platform: str = sys.platform) -> Protection | None:
    """The protection that covers ``path`` (the most specific place decides), or None when it is free to move."""
    paths = ntpath if platform == "win32" else posixpath
    target = _normal(paths, path)
    found: Protection | None = None
    found_length = -1
    for place in places:
        where = _normal(paths, place.path)
        covered = target == where or (place.inside and target.startswith(where.rstrip(paths.sep) + paths.sep))
        if covered and len(where) > found_length:
            found, found_length = place, len(where)
    return None if found is None or found.reason == FREE else found


def _windows_places(environ: Mapping[str, str]) -> list[Protection]:
    places = [Protection(environ[name], reason, inside) for name, reason, inside in _WINDOWS if environ.get(name)]
    if environ.get("WINDIR"):
        places.append(Protection(ntpath.join(environ["WINDIR"], "Temp"), FREE))
    if environ.get("USERPROFILE"):
        places.append(Protection(ntpath.join(environ["USERPROFILE"], "AppData"), SETTINGS, inside=False))
    if environ.get("SystemDrive"):
        places.append(Protection(ntpath.join(environ["SystemDrive"] + "\\", "Users"), PROFILE, inside=False))
    return places


def _under(home: str, folder: str) -> str:
    return str(PurePosixPath(home, folder))


def _normal(paths: ModuleType, path: str) -> str:
    """``path`` in one spelling: separators, case where the file system ignores it, no trailing separator."""
    return paths.normcase(paths.normpath(path))
