"""Cached Windows directory metadata never replaces ordinary no-follow path authority."""

from __future__ import annotations

import errno
import stat
from types import SimpleNamespace

import pytest

from je_file_tree.core import scanner
from je_file_tree.core.snapshot import pack_snapshot, unpack_snapshot


class _CachedEntry:
    name = "owned-directory"
    path = "owned-root/owned-directory"

    def __init__(self, info):
        self.info = info

    def stat(self, *, follow_symlinks):
        assert not follow_symlinks
        return self.info


def _info(attributes):
    return SimpleNamespace(st_dev=1, st_ino=123, st_size=0, st_mode=stat.S_IFDIR | 0o777,
                           st_mtime=0.0000001, st_mtime_ns=100, st_ctime_ns=100,
                           st_file_attributes=attributes, st_nlink=1)


def _node(entry, read):
    return scanner._entry_node(entry, scanner.ScanOptions(), read, lambda _e, info: info.st_size, None)


def test_cached_windows_identity_does_not_hide_full_path_attributes(monkeypatch):
    cached, authoritative = _info(0x10), _info(0x10000010)
    calls = []
    def lstat(path):
        calls.append(path)
        return authoritative
    monkeypatch.setattr(scanner, "os", SimpleNamespace(name="nt", DirEntry=_CachedEntry, lstat=lstat))
    read = scanner._FolderRead()
    node = _node(_CachedEntry(cached), read)
    assert calls == [_CachedEntry.path]
    assert unpack_snapshot(node.snapshot).attributes == 0x10000010
    assert node.snapshot == pack_snapshot(authoritative) and not read.errors


def test_cached_windows_identity_never_bypasses_a_later_path_permission_failure(monkeypatch):
    def denied(_path):
        raise PermissionError(errno.EACCES, "owned native denial")
    monkeypatch.setattr(scanner, "os", SimpleNamespace(name="nt", DirEntry=_CachedEntry, lstat=denied))
    read = scanner._FolderRead()
    assert _node(_CachedEntry(_info(0x10)), read) is None
    assert read.errors == [(_CachedEntry.path, scanner.ACCESS_DENIED)]


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_audited_adapter_metadata_is_not_requeried_or_replaced(monkeypatch, platform):
    class AuditedEntry:
        name, path = _CachedEntry.name, _CachedEntry.path

        def stat(self, *, follow_symlinks):
            assert not follow_symlinks
            return _info(0x10000010)
    def forbidden(_path):
        pytest.fail("Already audited no-follow metadata must not be replaced after raw comparison")
    monkeypatch.setattr(scanner, "os", SimpleNamespace(name=platform, DirEntry=_CachedEntry, lstat=forbidden))
    assert _node(AuditedEntry(), scanner._FolderRead()).snapshot == pack_snapshot(_info(0x10000010))
