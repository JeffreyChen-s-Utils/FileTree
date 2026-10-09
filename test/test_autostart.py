"""Native registration contracts with owned fixtures; never modify the host login configuration."""

from contextlib import contextmanager
import os
import plistlib
import sys
from types import SimpleNamespace

import pytest

from je_file_tree.gui import autostart, startup_posix, startup_windows


def test_launcher_is_absolute_background_only_without_shell_or_current_folder(monkeypatch, tmp_path):
    program = tmp_path / "File Tree.exe"
    assert autostart.launch_arguments(is_compiled=True, executable="unused", program_path=str(program)) == (
        str(program), "--background")
    arguments = autostart.launch_arguments(is_compiled=False, executable=sys.executable, program_path="unused")
    assert arguments[-1] == "--background" and arguments[-2].endswith("launcher.py")
    assert all(os.path.isabs(path) for path in arguments[:-1])
    monkeypatch.setattr(autostart, "launch_arguments", lambda **_kw: pytest.fail("Unexpected launch construction"))
    with pytest.raises(ValueError, match="boolean"):
        autostart.set_enabled("yes")


def test_appimage_registration_uses_the_original_program_outside_the_temporary_mount(monkeypatch, tmp_path):
    original = tmp_path / "FileTree.AppImage"
    original.write_bytes(b"owned original program fixture")
    original.chmod(0o755)
    monkeypatch.setattr(autostart, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("APPIMAGE", str(original))
    real = os.lstat
    def ordinary(path, *arguments, **keywords):
        info = real(path, *arguments, **keywords)
        if os.name == "nt" and str(path) == str(original):
            values = list(info)
            values[0] = 0o100755
            return os.stat_result(values)
        return info
    monkeypatch.setattr(autostart.os, "lstat", ordinary)
    arguments = autostart.launch_arguments(is_compiled=True, executable="unused",
                                           program_path=str(tmp_path / "temporary-mount/FileTree"))
    assert arguments == (str(original), "--background")
    monkeypatch.setenv("APPIMAGE", "relative.AppImage")
    with pytest.raises(ValueError, match="absolute"):
        autostart.launch_arguments(is_compiled=True, executable="unused", program_path="unused")
    monkeypatch.setenv("APPIMAGE", str(tmp_path))
    with pytest.raises(ValueError, match="ordinary"):
        autostart.launch_arguments(is_compiled=True, executable="unused", program_path="unused")


def test_appimage_environment_does_not_change_source_or_other_platform_startup(monkeypatch, tmp_path):
    monkeypatch.setenv("APPIMAGE", "relative invalid program")
    monkeypatch.setattr(autostart, "sys", SimpleNamespace(platform="darwin"))
    program = str(tmp_path / "FileTree.app/Contents/MacOS/FileTree")
    assert autostart.launch_arguments(is_compiled=True, executable="unused", program_path=program) == (
        program, "--background")
    monkeypatch.setattr(autostart, "sys", SimpleNamespace(platform="linux"))
    assert autostart.launch_arguments(is_compiled=False, executable=sys.executable,
                                     program_path="unused")[-2].endswith("launcher.py")


@pytest.mark.parametrize("arguments", [("relative", "--background"), ("/abs", "--remove"),
                                      ("/abs\nother", "--background"), ("/abs", "--background", "--background")])
def test_invalid_arguments_never_become_registrations(arguments):
    with pytest.raises(ValueError):
        autostart.validate_arguments(arguments)


def test_windows_native_length_and_literal_chinese_spaces(tmp_path):
    arguments = (str(tmp_path / "保留 FileTree.exe"), "--background")
    command = autostart.windows_command(arguments)
    assert command.endswith('" --background')
    with pytest.raises(ValueError, match="260"):
        autostart.windows_command((str(tmp_path / ("字" * 261)), "--background"))


def test_desktop_and_launch_agent_have_fixed_nonrespawning_metadata(tmp_path, monkeypatch):
    arguments = (str(tmp_path / 'file $`"\\ tree'), "--background")
    desktop = autostart.desktop_entry(arguments)
    assert b"Terminal=false\n" in desktop and b"TryExec=" not in desktop
    monkeypatch.setattr(startup_posix.sys, "platform", "linux")
    startup_posix._owned(desktop)
    with pytest.raises(OSError):
        startup_posix._owned(desktop + b"Hidden=true\n")
    with pytest.raises(ValueError, match="percent"):
        autostart.desktop_entry((str(tmp_path / "%x"), "--background"))
    agent = autostart.launch_agent(arguments)
    metadata = plistlib.loads(agent)
    assert metadata["ProgramArguments"] == list(arguments)
    assert metadata["RunAtLoad"] is True and "KeepAlive" not in metadata and "WorkingDirectory" not in metadata
    monkeypatch.setattr(startup_posix.sys, "platform", "darwin")
    startup_posix._owned(agent)
    metadata["KeepAlive"] = True
    with pytest.raises(OSError):
        startup_posix._owned(plistlib.dumps(metadata))


class _Key:
    def __init__(self, registry, path):
        self.registry, self.path = registry, path

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Registry:
    HKEY_CURRENT_USER, REG_SZ, KEY_READ, KEY_WRITE = "HKCU", 1, 1, 2

    def __init__(self):
        self.keys, self.events = {}, []

    def OpenKey(self, _root, path, *_args):  # noqa: N802 - winreg fixture API
        if path not in self.keys:
            raise FileNotFoundError(path)
        return _Key(self, path)

    def CreateKeyEx(self, _root, path, *_args):  # noqa: N802
        self.keys.setdefault(path, {})
        return _Key(self, path)

    def QueryValueEx(self, key, name):  # noqa: N802
        if name not in self.keys[key.path]:
            raise FileNotFoundError(name)
        return self.keys[key.path][name]

    def SetValueEx(self, key, name, _reserved, kind, value):  # noqa: N802
        self.events.append(("set", key.path, name))
        self.keys[key.path][name] = (value, kind)

    def DeleteValue(self, key, name):  # noqa: N802
        self.events.append(("remove", key.path, name))
        del self.keys[key.path][name]

    def FlushKey(self, key):  # noqa: N802
        self.events.append(("flush", key.path))

    def QueryInfoKey(self, key):  # noqa: N802
        return 0, len(self.keys[key.path]), 0

    def EnumValue(self, key, index):  # noqa: N802
        name, (value, kind) = list(self.keys[key.path].items())[index]
        return name, value, kind


@pytest.fixture
def registry(monkeypatch):
    registry = _Registry()
    monkeypatch.setattr(startup_windows, "_registry", lambda: registry)

    @contextmanager
    def claim():
        if startup_windows.RECEIPT_KEY not in registry.keys:
            registry.keys[startup_windows.RECEIPT_KEY] = {"Owner": (autostart.OWNER, registry.REG_SZ)}
        key = registry.OpenKey(registry.HKEY_CURRENT_USER, startup_windows.RECEIPT_KEY)
        startup_windows._receipt(key)
        yield key

    monkeypatch.setattr(startup_windows, "_claim", claim)
    return registry


def test_windows_install_receipt_is_durable_before_run_and_remove_keeps_other_values(registry, tmp_path):
    arguments = (str(tmp_path / "FileTree.exe"), "--background")
    registry.keys[startup_windows.RUN_KEY] = {"Other": ("keep", registry.REG_SZ)}
    assert not startup_windows.inspect().installed
    assert startup_windows.apply(True, arguments).installed
    assert registry.events.index(("flush", startup_windows.RECEIPT_KEY)) < registry.events.index(
        ("set", startup_windows.RUN_KEY, startup_windows.VALUE))
    assert not startup_windows.apply(False, arguments).installed
    assert registry.keys[startup_windows.RUN_KEY] == {"Other": ("keep", registry.REG_SZ)}
    assert registry.keys[startup_windows.RECEIPT_KEY]["Owner"][0] == autostart.OWNER
    assert startup_windows.apply(True, arguments).installed


@pytest.mark.parametrize("collision", ["foreign", "changed", "unknown_receipt"])
def test_windows_foreign_or_changed_entry_is_never_overwritten_or_removed(registry, tmp_path, collision):
    arguments = (str(tmp_path / "FileTree.exe"), "--background")
    if collision == "foreign":
        registry.keys[startup_windows.RUN_KEY] = {startup_windows.VALUE: ("foreign", registry.REG_SZ)}
    else:
        startup_windows.apply(True, arguments)
        if collision == "changed":
            registry.keys[startup_windows.RUN_KEY][startup_windows.VALUE] = ("changed", registry.REG_SZ)
        else:
            registry.keys[startup_windows.RECEIPT_KEY]["Unknown"] = ("keep", registry.REG_SZ)
    captured = {path: dict(values) for path, values in registry.keys.items()}
    with pytest.raises(OSError):
        startup_windows.apply(True, arguments)
    with pytest.raises(OSError):
        startup_windows.apply(False, arguments)
    assert registry.keys == captured


def test_windows_changed_program_requires_explicit_removal(registry, tmp_path):
    old = (str(tmp_path / "Old.exe"), "--background")
    new = (str(tmp_path / "New.exe"), "--background")
    startup_windows.apply(True, old)
    with pytest.raises(OSError, match="Remove"):
        startup_windows.apply(True, new)
    assert not startup_windows.apply(False, new).installed
    assert startup_windows.apply(True, new).installed


@pytest.mark.skipif(os.name == "nt", reason="Native descriptor-relative POSIX registration")
@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_posix_private_native_install_remove_and_foreign_collision(tmp_path, monkeypatch, platform):
    monkeypatch.setattr(startup_posix.sys, "platform", platform)
    target = tmp_path / "config" / "autostart" / ("owned.plist" if platform == "darwin" else "owned.desktop")
    monkeypatch.setattr(startup_posix, "_target", lambda: target)
    arguments = (str(tmp_path / "CJK 保留 program"), "--background")
    assert not startup_posix.inspect().installed and not target.parent.exists()
    assert startup_posix.apply(True, arguments).installed
    assert target.stat().st_mode & 0o777 == 0o600
    assert startup_posix.apply(True, arguments).installed
    assert not startup_posix.apply(False, arguments).installed
    target.write_text("foreign entry", encoding="utf-8")
    for enabled in (True, False):
        with pytest.raises(OSError):
            startup_posix.apply(enabled, arguments)
    assert target.read_text(encoding="utf-8") == "foreign entry"


@pytest.mark.skipif(os.name == "nt", reason="Native POSIX startup path guards")
def test_posix_linked_parent_and_hardlinked_entry_refused(tmp_path, monkeypatch):
    owned = tmp_path / "owned"
    owned.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(owned, target_is_directory=True)
    monkeypatch.setattr(startup_posix, "_target", lambda: alias / "entry.desktop")
    arguments = (str(tmp_path / "program"), "--background")
    with pytest.raises(OSError):
        startup_posix.apply(True, arguments)
    assert list(owned.iterdir()) == []
    target = owned / "entry.desktop"
    monkeypatch.setattr(startup_posix, "_target", lambda: target)
    startup_posix.apply(True, arguments)
    os.link(target, owned / "alias.desktop")
    with pytest.raises(OSError):
        startup_posix.apply(False, arguments)
    assert target.exists()


@pytest.mark.skipif(os.name == "nt", reason="Native exclusive POSIX startup publication")
def test_posix_arrival_during_publication_is_retained(tmp_path, monkeypatch):
    target = tmp_path / "entry.desktop"
    monkeypatch.setattr(startup_posix, "_target", lambda: target)
    link = startup_posix.os.link

    def arrival(source, destination, **kwargs):
        target.write_text("arrival", encoding="utf-8")
        link(source, destination, **kwargs)

    monkeypatch.setattr(startup_posix.os, "link", arrival)
    with pytest.raises(FileExistsError):
        startup_posix.apply(True, (str(tmp_path / "program"), "--background"))
    assert target.read_text(encoding="utf-8") == "arrival"
    assert list(tmp_path.iterdir()) == [target]
