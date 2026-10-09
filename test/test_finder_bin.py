"""Owned POSIX fixtures exercise Finder approval; fixed OS execution is always mocked."""

from dataclasses import replace
import os
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from je_file_tree.core import finder_bin as finder
from je_file_tree.core.trash_size import TrashUsage

_FIXED_RUNNER = finder._run_finder_empty


@pytest.fixture
def owned_finder(tmp_path, monkeypatch):
    if os.name != "posix":
        pytest.skip("POSIX descriptor APIs required; this does not prove native Finder")
    root, home = tmp_path / "volume", tmp_path / "home"
    root.mkdir()
    home.mkdir()
    monkeypatch.setattr(finder, "_require_mac", lambda: None)
    monkeypatch.setattr(finder, "_home", lambda: home)
    scope = home / ".Trash"
    scope.mkdir(mode=0o700)
    (scope / "payload").write_bytes(b"owned payload")
    external = root / "outside"
    external.write_bytes(b"never modified")
    def provider():
        return (str(root),)
    return provider, scope, external


def test_complete_private_inventory_and_mocked_finder_success(owned_finder, monkeypatch):
    provider, scope, external = owned_finder
    os.symlink(external, scope / "link")
    plan = finder.prepare_finder_empty(provider)
    assert plan.usage.complete and plan.usage.count == 2
    assert plan.usage.size == len(b"owned payload") + len(os.fsencode(external))
    calls = []
    def mocked_finder():
        calls.append(True)
        (scope / "payload").unlink()  # owned disposable fixture, not user Trash
        (scope / "link").unlink()
    monkeypatch.setattr(finder, "_run_finder_empty", mocked_finder)
    remaining = finder.empty_finder_bin(plan, provider)
    assert calls == [True] and remaining == TrashUsage(0, 0, True)
    assert scope.is_dir() and external.read_bytes() == b"never modified"


def test_changed_payload_or_roots_prevents_os_command(owned_finder, monkeypatch):
    provider, scope, _external = owned_finder
    plan = finder.prepare_finder_empty(provider)
    calls = []
    monkeypatch.setattr(finder, "_run_finder_empty", lambda: calls.append(True))
    (scope / "payload").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        finder.empty_finder_bin(plan, provider)
    plan = finder.prepare_finder_empty(provider)
    extra = Path(provider()[0]) / "new-mount"
    extra.mkdir()
    with pytest.raises(ValueError, match="changed"):
        finder.empty_finder_bin(plan, lambda: (*provider(), str(extra)))
    assert not calls and (scope / "payload").read_bytes() == b"changed"


def test_private_permissions_links_and_disappearing_children_disable_approval(owned_finder, monkeypatch):
    provider, scope, _external = owned_finder
    scope.chmod(0o750)
    plan = finder.prepare_finder_empty(provider)
    assert not plan.usage.complete
    with pytest.raises(ValueError, match="Complete"):
        finder.empty_finder_bin(plan, provider)
    scope.chmod(0o700)
    def changed(*_args):
        raise FileNotFoundError("owned child vanished during inventory")
    monkeypatch.setattr(finder, "_inventory", changed)
    assert not finder.prepare_finder_empty(provider).usage.complete
    scope.rename(scope.with_name("retained"))
    scope.symlink_to(scope.with_name("retained"), target_is_directory=True)
    assert not finder.prepare_finder_empty(provider).usage.complete


def test_partial_os_success_keeps_remaining_visible(owned_finder, monkeypatch):
    provider, scope, _external = owned_finder
    plan = finder.prepare_finder_empty(provider)
    monkeypatch.setattr(finder, "_run_finder_empty", lambda: None)
    with pytest.raises(OSError, match="nonempty"):
        finder.empty_finder_bin(plan, provider)
    assert (scope / "payload").read_bytes() == b"owned payload"


def test_cancel_and_bounds_never_call_os(owned_finder, monkeypatch):
    provider, scope, _external = owned_finder
    cancel = threading.Event()
    cancel.set()
    assert finder.prepare_finder_empty(lambda: pytest.fail("canceled mount query"), cancel=cancel) is None
    (scope / "second").write_bytes(b"owned second")
    monkeypatch.setattr(finder, "MAX_ENTRIES", 1)
    assert not finder.prepare_finder_empty(provider).usage.complete
    plan = finder.prepare_finder_empty(provider)
    with pytest.raises(ValueError, match="Complete"):
        finder.empty_finder_bin(replace(plan, usage=TrashUsage(0, 0, False)), provider)


def test_physical_alias_scope_is_deduplicated_before_consuming_inventory_budget(owned_finder, monkeypatch):
    provider, scope, _external = owned_finder
    alias = Path(provider()[0]) / ".Trashes" / str(os.getuid())
    alias.mkdir(mode=0o700, parents=True)
    original_stat, original_directory = finder.Path.lstat, finder._absolute_directory
    # A simulated firmlink exposes the same owned directory under two paths; this is not native APFS proof.
    def alias_stat(path, *args, **kwargs):
        return original_stat(scope if path == alias else path, *args, **kwargs)
    def alias_directory(path):
        return original_directory(scope if path == alias else path)
    monkeypatch.setattr(finder.Path, "lstat", alias_stat)
    monkeypatch.setattr(finder, "_absolute_directory", alias_directory)
    monkeypatch.setattr(finder, "MAX_ENTRIES", 1)
    plan = finder.prepare_finder_empty(provider)
    assert plan.usage.complete and plan.usage.count == 1 and len(plan.scopes) == 1


def test_fixed_osascript_uses_no_paths_shell_or_termination(monkeypatch):
    calls = []
    def command(arguments, **options):
        calls.append(arguments)
        assert "shell" not in options and "timeout" not in options
        options["stderr"].write(b"fixture automation denied")
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(finder.subprocess, "run", command)
    with pytest.raises(OSError, match="automation denied.*still be working"):
        _FIXED_RUNNER()
    assert calls == [["/usr/bin/osascript", "-e", 'tell application "Finder" to empty the trash']]


@pytest.mark.parametrize("uid", (501, None))
def test_console_query_releases_copied_value_and_refuses_unknown_user(monkeypatch, uid):
    released = []
    def query(_store, uid_pointer, _gid):
        if uid is None:
            return None
        uid_pointer._obj.value = uid
        return 12345
    def release(value):
        released.append(value)
    def library(path):
        return SimpleNamespace(SCDynamicStoreCopyConsoleUser=query) if "SystemConfiguration" in path else (
            SimpleNamespace(CFRelease=release))
    monkeypatch.setattr(finder.ctypes, "CDLL", library)
    if uid is None:
        with pytest.raises(OSError, match="console user"):
            finder._console_uid()
        assert not released
    else:
        assert finder._console_uid() == uid and released == [12345]


@pytest.mark.parametrize("uid,effective,console", ((501, 501, 501), (0, 0, 0), (501, 0, 501), (501, 501, 502)))
def test_current_user_refuses_root_elevation_or_other_console(monkeypatch, uid, effective, console):
    monkeypatch.setattr(finder.os, "getuid", lambda: uid, raising=False)
    monkeypatch.setattr(finder.os, "geteuid", lambda: effective, raising=False)
    monkeypatch.setattr(finder, "_console_uid", lambda: console)
    if uid and uid == effective == console:
        assert finder._current_user() == uid
    else:
        with pytest.raises(ValueError, match="console user"):
            finder._current_user()


def test_unknown_entry_identity_cannot_be_approved(monkeypatch):
    monkeypatch.setattr(finder.os, "getuid", lambda: 501, raising=False)
    with pytest.raises(OSError, match="identity is unavailable"):
        finder._entry(SimpleNamespace(st_uid=501, st_dev=0, st_ino=0), ("unknown",))
