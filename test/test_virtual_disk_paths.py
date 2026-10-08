"""Read-only path matching handles extended UNC forms without inventing device-path aliases."""

import ntpath
from types import SimpleNamespace

import pytest

from je_file_tree.core import virtual_disks as disks
from je_file_tree.core.node import Node
from je_file_tree.core.virtual_disk_sources import DiskRegistration


@pytest.mark.parametrize(("ordinary", "extended"), [
    (r"\\server\share\資料\disk.vhdx", r"\\?\UNC\SERVER\share\資料\disk.vhdx"),
    (r"C:\資料\disk.vhdx", r"\\?\C:\資料\disk.vhdx"),
])
def test_windows_extended_path_keys_match_only_corresponding_ordinary_paths(monkeypatch, ordinary, extended):
    monkeypatch.setattr(disks, "os", SimpleNamespace(path=ntpath, name="nt"))
    assert disks._key(ordinary) == disks._key(extended)


def test_volume_guid_and_device_names_remain_explicit_and_never_become_relative_names(monkeypatch):
    monkeypatch.setattr(disks, "os", SimpleNamespace(path=ntpath, name="nt"))
    device = r"\\?\Volume{01234567-89ab-cdef-0123-456789abcdef}\disk.vhdx"
    assert disks._key(device) == device.lower()
    assert disks._key(device) != disks._key(device[4:])


def test_extended_unc_provider_merges_recorded_row_without_any_external_path_query(monkeypatch):
    monkeypatch.setattr(disks, "os", SimpleNamespace(path=ntpath, name="nt",
                        lstat=lambda *_args: pytest.fail("Already recorded UNC file was queried externally")))
    root = Node(r"\\server\share\owned", True)
    file = Node("disk.vhdx", False, size=16, allocated=4096, parent=root)
    root.children = [file]
    registration = DiskRegistration("Owned provider", r"\\?\UNC\SERVER\share\owned\disk.vhdx", "wsl")
    result = disks.find_virtual_disks(root, registrations=[registration])
    assert result.count == 1 and result.rows[0].node is file
    assert result.rows[0].path == file.path and result.rows[0].source == "wsl"
    assert result.rows[0].issue == "unverified" and result.rows[0].snapshot is None
