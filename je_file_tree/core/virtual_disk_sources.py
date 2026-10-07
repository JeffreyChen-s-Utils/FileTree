"""Current-user WSL registrations and bounded default Docker backing-file metadata, without launches."""

from dataclasses import dataclass
import os
import sys
import threading

from je_file_tree.core.pacing import give_way

if sys.platform == "win32":
    import winreg

_WSL = r"Software\Microsoft\Windows\CurrentVersion\Lxss"
_REGISTRY_LIMIT = 256
_FIELD_LIMIT = 4096
_WSL2 = 2
_FIRST_PRINTABLE = 32


@dataclass(frozen=True, slots=True)
class DiskRegistration:
    """A provider-reported/inferred exact path; it is not proof of file type, ownership or stopped state."""

    name: str
    path: str
    source: str
    distro: str | None = None


@dataclass(frozen=True, slots=True)
class DiskRegistrations:
    """Bounded current-user provider paths and missing/denied/malformed source count."""

    rows: tuple[DiskRegistration, ...]
    issues: int = 0


def _text(value: object) -> str:
    return value if isinstance(value, str) and len(value) <= _FIELD_LIMIT and not any(
        ord(character) < _FIRST_PRINTABLE for character in value) else ""


def _value(key, name: str) -> object:
    try:
        return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return None  # Optional provider fields remain unknown, never executable commands.


def _registration(key) -> DiskRegistration | None:
    version = _value(key, "Version")
    if type(version) is not int or version not in (1, _WSL2):
        raise ValueError("WSL registration version is unknown")
    if version != _WSL2:
        return None
    name, base = _text(_value(key, "DistributionName")), _text(_value(key, "BasePath"))
    if not name or not base or not os.path.isabs(base):
        raise ValueError("WSL registration has no absolute backing-file location/name")
    filename = _text(_value(key, "VhdFileName")) or "ext4.vhdx"
    if (os.path.basename(filename) != filename or ":" in filename
            or not filename.lower().endswith(".vhdx")):
        raise ValueError("WSL backing-file name is not a literal VHDX basename")
    return DiskRegistration(name, os.path.normpath(os.path.join(base, filename)), "wsl", name)


def _wsl(cancel: threading.Event | None) -> DiskRegistrations | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WSL, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return DiskRegistrations(())
    except OSError:
        return DiskRegistrations((), 1)
    rows, issues = [], 0
    with key:
        try:
            count = winreg.QueryInfoKey(key)[0]
            issues += max(0, count - _REGISTRY_LIMIT)
            for number in range(min(count, _REGISTRY_LIMIT)):
                if cancel is not None and cancel.is_set():
                    return None
                give_way()
                try:
                    with winreg.OpenKey(key, winreg.EnumKey(key, number), 0, winreg.KEY_READ) as child:
                        if row := _registration(child):
                            rows.append(row)
                except (OSError, ValueError):
                    issues += 1
        except OSError:
            issues += 1
    return DiskRegistrations(tuple(rows), issues)


def registered_disks(*, cancel: threading.Event | None = None) -> DiskRegistrations | None:
    """Read HKCU WSL2 paths and existing default Docker WSL disk candidates; never start a guest.

    Registry enumeration is bounded at 256 registrations, with omissions/errors counted. Default
    Docker paths are inferred labels, not installation/stopped-state proof; custom locations remain
    discoverable when their folder is scanned. No settings, virtual-disk contents, shell or external
    command is read/executed. Non-Windows has no implicit provider locations. Cancellation returns None.
    """
    if cancel is not None and cancel.is_set():
        return None
    if sys.platform != "win32":
        return DiskRegistrations(())
    result = _wsl(cancel)
    if result is None:
        return None
    rows, issues = list(result.rows), result.issues
    local = os.environ.get("LOCALAPPDATA", "")
    if local and os.path.isabs(local):
        for relative in ("data/ext4.vhdx", "disk/docker_data.vhdx", "data/docker_data.vhdx"):
            path = os.path.normpath(os.path.join(local, "Docker", "wsl", relative))
            try:
                os.lstat(path)
                rows.append(DiskRegistration("Docker Desktop", path, "docker"))
            except FileNotFoundError:
                continue  # An absent inferred default is not an installed provider or an inventory failure.
            except OSError:
                issues += 1
    return None if cancel is not None and cancel.is_set() else DiskRegistrations(tuple(rows), issues)
