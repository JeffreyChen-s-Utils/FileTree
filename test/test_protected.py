"""Protected places: the system, programs and their settings ask twice before going to the Recycle Bin."""

from __future__ import annotations

import pytest

from je_file_tree.core.protected import PROFILE, PROGRAMS, SETTINGS, SYSTEM, protected_places, protection_of

WINDOWS_ENV = {
    "WINDIR": r"C:\Windows",
    "ProgramFiles": r"C:\Program Files",
    "ProgramFiles(x86)": r"C:\Program Files (x86)",
    "ProgramData": r"C:\ProgramData",
    "APPDATA": r"C:\Users\me\AppData\Roaming",
    "LOCALAPPDATA": r"C:\Users\me\AppData\Local",
    "USERPROFILE": r"C:\Users\me",
    "TEMP": r"C:\Users\me\AppData\Local\Temp",
    "SystemDrive": "C:",
}


def _reason(path: str, platform: str, **where: object) -> str | None:
    places = protected_places(platform, **where)  # type: ignore[arg-type]
    found = protection_of(path, places, platform)
    return None if found is None else found.reason


@pytest.mark.parametrize(("path", "reason"), [
    (r"C:\Windows", SYSTEM),
    (r"c:\windows\System32\drivers", SYSTEM),  # case does not matter on Windows
    (r"C:\Windows\Temp\setup.log", None),  # temporary files may go even inside the Windows folder
    (r"C:\Program Files\Tool", PROGRAMS),
    (r"C:\Program Files (x86)\Game\data.pak", PROGRAMS),
    (r"C:\ProgramData\App", SETTINGS),
    (r"C:\Users\me\AppData\Roaming\App", SETTINGS),
    (r"C:\Users\me\AppData\Local", SETTINGS),
    (r"C:\Users\me\AppData", SETTINGS),
    (r"C:\Users\me\AppData\Local\Google\Chrome\Cache", None),  # Local protects itself only: caches may go
    (r"C:\Users\me\AppData\Local\Temp\x.tmp", None),
    (r"C:\Users\me", PROFILE),
    (r"C:\Users", PROFILE),
    (r"C:\Users\me\Documents\old", None),  # a profile protects itself only, not the documents in it
    (r"C:\Windowsy\x", None),  # a name that merely starts like a protected one
    (r"D:\Games", None),
])
def test_windows_places(path: str, reason: str | None) -> None:
    assert _reason(path, "win32", environ=WINDOWS_ENV) == reason


@pytest.mark.parametrize(("path", "reason"), [
    ("/usr/lib/x", SYSTEM),
    ("/etc", SYSTEM),
    ("/var/log", SYSTEM),
    ("/var/tmp/x", None),  # noqa: S108 - a path compared, never written
    ("/opt/tool", PROGRAMS),
    ("/home/me/.config/app", SETTINGS),
    ("/home/me/.local/share", SETTINGS),
    ("/home/me/.local/share/Steam", None),  # .local/share protects itself only
    ("/home/me", PROFILE),
    ("/home", PROFILE),
    ("/home/me/Videos/old.mkv", None),
    ("/USR/lib", None),  # Linux is case-sensitive
])
def test_linux_places(path: str, reason: str | None) -> None:
    assert _reason(path, "linux", environ={}, home="/home/me") == reason


@pytest.mark.parametrize(("path", "reason"), [
    ("/System/Library", SYSTEM),
    ("/Applications/Tool.app", PROGRAMS),
    ("/Users/me/Library/Preferences/x.plist", SETTINGS),
    ("/Users/me/Library/Caches/x", None),
    ("/Users/me", PROFILE),
    ("/Users/me/Movies", None),
])
def test_macos_places(path: str, reason: str | None) -> None:
    assert _reason(path, "darwin", environ={}, home="/Users/me") == reason


def test_missing_variables_are_skipped() -> None:
    places = protected_places("win32", environ={"USERPROFILE": r"C:\Users\me"})
    assert {place.reason for place in places} == {PROFILE, SETTINGS}, "the profile and its AppData, nothing else"
