"""Read-only bounded discovery uses fresh backing-file fixtures and never starts guests or opens data."""

import builtins
from dataclasses import replace
import os
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import virtual_disks as disks
from je_file_tree.core import virtual_disk_sources as sources
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot, stable_snapshot


def test_recorded_formats_deduplicated_provider_and_external_metadata_never_read_payloads(tmp_path, monkeypatch):
    root_path = tmp_path / "scan"
    root_path.mkdir()
    for kind in sorted(disks.FORMATS):
        (root_path / ("owned." + kind.upper())).write_bytes(b"owned arbitrary backing bytes")
    (root_path / "ignore.zip").write_bytes(b"not a virtual-disk candidate")
    external = tmp_path / "external.vhdx"
    external.write_bytes(b"owned external")
    root = scan(root_path).root
    names = {node.path: stat_snapshot(node.path) for node in root.iter_files()}
    providers = [sources.DiskRegistration("Owned distro", str(root_path / "owned.VHDX"), "wsl", "Owned distro"),
                 sources.DiskRegistration("Owned Docker", str(external), "docker")]

    def no_payload(*_args, **_kwargs):
        raise AssertionError("Discovery may not open headers, guest data or command scripts")

    monkeypatch.setattr(builtins, "open", no_payload)
    result = disks.find_virtual_disks(root, registrations=providers)
    assert result.count == 6 and len(result.rows) == 6 and not result.issues and not result.incomplete
    registered = next(row for row in result.rows if row.source == "wsl")
    assert registered.node in root.children and registered.distro == "Owned distro"
    outside = next(row for row in result.rows if row.source == "docker")
    assert outside.node is None and outside.size == len(b"owned external") and outside.snapshot is not None
    assert all(row.guest_used is None and row.virtual_size is None for row in result.rows)
    assert names == {node.path: stat_snapshot(node.path) for node in root.iter_files()}


def test_missing_linked_and_cloud_provider_files_remain_visible_as_unknown(tmp_path, monkeypatch):
    (tmp_path / "regular").write_bytes(b"owned data")
    root = scan(tmp_path).root
    missing = sources.DiskRegistration("Missing", str(tmp_path / "missing.vhdx"), "wsl", "Missing")
    unavailable = sources.DiskRegistration("Unavailable", str(tmp_path / "regular"), "docker")
    native = disks.os.lstat

    def cloud(path):
        actual = native(path)
        if str(path) == unavailable.path:
            return SimpleNamespace(st_mode=actual.st_mode, st_nlink=1, st_ino=actual.st_ino,
                                   st_file_attributes=0x40000)
        return actual

    monkeypatch.setattr(disks.os, "lstat", cloud)
    monkeypatch.setattr(disks, "file_allocation", lambda *_args:
                        (_ for _ in ()).throw(AssertionError("Unavailable placeholders must not be queried")))
    result = disks.find_virtual_disks(root, registrations=[missing, unavailable])
    assert result.count == 2 and result.issues == 2 and result.incomplete
    assert all(row.issue and row.snapshot is None and row.size is None for row in result.rows)


def test_largest_heap_is_bounded_with_full_counts_and_incomplete_scan_coverage(monkeypatch):
    limit = disks.MAX_DISKS
    root = Node(os.path.abspath("owned-virtual-fixture"), True, children=[])
    root.children = [Node(f"disk{number}.vdi", False, size=number, allocated=number,
                          parent=root) for number in range(limit + 5)]
    root.children.append(Node("excluded", True, error="excluded", parent=root))
    observed, native = [], disks._add

    def bounded(rows, row, count):
        native(rows, row, count)
        observed.append(len(rows))

    monkeypatch.setattr(disks, "_add", bounded)
    result = disks.find_virtual_disks(root, registrations=[])
    assert result.count == limit + 5 and len(result.rows) == max(observed) == limit
    assert min(row.allocated for row in result.rows) == 5 and result.incomplete
    assert result.issues == limit + 10, "unknown scan records plus five omitted rows"


def test_cancellation_before_and_after_last_provider_read_never_publishes_inventory(tmp_path, monkeypatch):
    root = scan(tmp_path).root
    cancel = threading.Event()
    cancel.set()
    assert disks.find_virtual_disks(root, registrations=[], cancel=cancel) is None
    cancel.clear()
    source = sources.DiskRegistration("Owned", str(tmp_path / "owned.vhdx"), "wsl", "Owned")
    native = disks._external

    def finish(source):
        result = native(source)
        cancel.set()
        return result

    monkeypatch.setattr(disks, "_external", finish)
    assert disks.find_virtual_disks(root, registrations=[source], cancel=cancel) is None


def test_recorded_hard_links_and_links_are_not_compaction_authority(tmp_path):
    first, second = tmp_path / "first.vhdx", tmp_path / "second.vhdx"
    first.write_bytes(b"owned backing bytes")
    os.link(first, second)
    result = disks.find_virtual_disks(scan(tmp_path).root, registrations=[])
    assert result.count == 2 and all(row.issue == "duplicate_hard_links" for row in result.rows)
    assert all(unpack_snapshot(row.snapshot).links == 2 for row in result.rows)
    assert stable_snapshot(result.rows[0].snapshot) == stable_snapshot(result.rows[1].snapshot)


@pytest.mark.parametrize("field,value", [("Version", None), ("BasePath", "relative"),
                                         ("VhdFileName", "../escaped.vhdx"), ("VhdFileName", "base:ads.vhdx"),
                                         ("DistributionName", "bad\nname")])
def test_wsl_registrations_refuse_unknown_or_nonliteral_fields(tmp_path, monkeypatch, field, value):
    values = {"Version": 2, "BasePath": str(tmp_path), "DistributionName": "Owned distro"}
    values[field] = value
    monkeypatch.setattr(sources, "_value", lambda _key, name: values.get(name))
    with pytest.raises(ValueError):
        sources._registration(object())


def test_wsl_literal_cjk_name_optional_filename_and_nonwindows_provider_inventory(tmp_path, monkeypatch):
    values = {"Version": 2, "BasePath": str(tmp_path), "DistributionName": "自建發行版本"}
    monkeypatch.setattr(sources, "_value", lambda _key, name: values.get(name))
    source = sources._registration(object())
    assert source.distro == "自建發行版本" and source.path == str(tmp_path / "ext4.vhdx")
    values["VhdFileName"] = "owned-other.vhdx"
    assert sources._registration(object()).path == str(tmp_path / "owned-other.vhdx")
    values["Version"] = 1
    assert sources._registration(object()) is None
    monkeypatch.setattr(sources, "sys", SimpleNamespace(platform="linux"))
    assert sources.registered_disks().rows == ()


def test_provider_failures_omissions_and_input_bound_remain_explicit(tmp_path, monkeypatch):
    root = scan(tmp_path).root
    monkeypatch.setattr(disks, "registered_disks", lambda **_kwargs: sources.DiskRegistrations((), 3))
    result = disks.find_virtual_disks(root)
    assert result.count == 0 and result.issues == 3 and result.incomplete
    source = sources.DiskRegistration("Owned", str(tmp_path / "owned.vhdx"), "docker")
    with pytest.raises(ValueError, match="1,000"):
        disks.find_virtual_disks(root, registrations=[replace(source, name=str(n))
                                                      for n in range(disks.MAX_DISKS + 1)])


def test_wsl_registry_cap_malformed_entry_and_cancel_close_handles(tmp_path, monkeypatch):
    closed = []

    class Key:
        def __init__(self, name):
            self.name = name
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            closed.append(self.name)

    registry = SimpleNamespace(HKEY_CURRENT_USER=object(), KEY_READ=1,
                               OpenKey=lambda _parent, name, *_args: Key(name),
                               QueryInfoKey=lambda _key: (5, 0, 0), EnumKey=lambda _key, number: str(number))
    monkeypatch.setattr(sources, "winreg", registry, raising=False)
    monkeypatch.setattr(sources, "_REGISTRY_LIMIT", 3)

    def value(key, field):
        return {"Version": None if key.name == "2" else 2, "BasePath": str(tmp_path),
                "DistributionName": "Owned " + key.name}.get(field)

    monkeypatch.setattr(sources, "_value", value)
    result = sources._wsl(None)
    assert len(result.rows) == 2 and result.issues == 3
    assert closed == ["0", "1", "2", sources._WSL]
    closed.clear()
    cancel = threading.Event()
    cancel.set()
    assert sources._wsl(cancel) is None and closed == [sources._WSL]


def test_docker_defaults_are_inferred_only_when_present_and_do_not_launch_guests(tmp_path, monkeypatch):
    path = tmp_path / "Docker" / "wsl" / "disk" / "docker_data.vhdx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"owned arbitrary backing file")
    monkeypatch.setattr(sources, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sources, "_wsl", lambda _cancel: sources.DiskRegistrations(()))
    before = stat_snapshot(path)
    result = sources.registered_disks()
    assert result.rows == (sources.DiskRegistration("Docker Desktop", str(path), "docker"),)
    assert not result.issues and stat_snapshot(path) == before
