"""Archive inventories never extract, mutate source trees or turn member names into disk actions."""

from __future__ import annotations

import hashlib
import io
import os
import stat
import threading
import struct
import zlib
import zipfile
from pathlib import Path

import pytest

from je_file_tree.core import archives
from je_file_tree.core.archives import ArchiveCancelledError, ArchiveError, ArchiveMember, read_archive
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.snapshot import Snapshot, unpack_snapshot


def _zip(tmp_path: Path):
    target = tmp_path / "測試.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("文件/大檔案.txt", b"x" * 9000)
        archive.writestr("文件/小檔案.txt", b"x" * 10)
        archive.writestr("empty/", b"")
    root = scan(tmp_path).root
    return root, next(node for node in root.iter_files() if node.name.endswith(".zip"))


def test_zip_inventory_is_virtual_and_never_extracts(tmp_path, monkeypatch):
    root, node = _zip(tmp_path)
    before = node.size, node.allocated, root.size, root.file_count, list(node.children)
    digest = hashlib.sha256(Path(node.path).read_bytes()).digest()
    def forbid(*_args, **_kwargs):
        raise AssertionError("No extraction or member-content reads are allowed")
    monkeypatch.setattr(zipfile.ZipFile, "extractall", forbid)
    monkeypatch.setattr(zipfile.ZipFile, "extract", forbid)
    monkeypatch.setattr(zipfile.ZipFile, "open", forbid)
    result = read_archive(node)
    assert (result.files, result.size, result.rejected) == (2, 9010, 0)
    folder = next(child for child in result.children if child.name == "文件")
    assert (folder.size, folder.file_count, folder.parent) == (9010, 2, node)
    assert all(child.parent is folder for child in folder.children)
    assert before == (node.size, node.allocated, root.size, root.file_count, list(node.children))
    assert digest == hashlib.sha256(Path(node.path).read_bytes()).digest()
    assert list(tmp_path.iterdir()) == [Path(node.path)]


def test_unsafe_names_links_and_conflicts_stay_outside_inventory(tmp_path):
    _, node = _zip(tmp_path)
    members = [ArchiveMember(name, 1) for name in ("../escape", "/absolute", "C:/drive", "a//b", "x\x00y")]
    members += [ArchiveMember("link", 3, is_link=True), ArchiveMember("ok", 7), ArchiveMember("ok/child", 3),
                ArchiveMember("ok", 7), ArchiveMember("too-big", 2**63), ArchiveMember("negative", -1)]
    result = read_archive(node, reader=lambda _stream: iter(members))
    assert (result.files, result.size, result.rejected) == (1, 7, 10)
    assert [child.name for child in result.children] == ["ok"]


def test_cancellation_limits_corruption_and_changed_snapshots(tmp_path, monkeypatch):
    _, node = _zip(tmp_path)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ArchiveCancelledError):
        read_archive(node, cancel=cancel)
    reader = archives.MetadataReader(io.BytesIO(b"x" * 20), None)
    monkeypatch.setattr(reader, "_remaining", 10)
    with pytest.raises(ArchiveError, match="budget"):
        reader.read()
    monkeypatch.setattr(archives, "MAX_MEMBERS", 2)
    with pytest.raises(ArchiveError, match="members"):
        read_archive(node, reader=lambda _stream: (ArchiveMember(f"{n}", 1) for n in range(3)))
    Path(node.path).write_bytes(b"not the original archive")
    with pytest.raises(OSError, match="changed"):
        read_archive(node)
    node = next(scan(tmp_path).root.iter_files())
    with pytest.raises(ArchiveError):
        read_archive(node)


def test_cloud_links_and_mid_read_changes_are_refused(tmp_path, monkeypatch):
    _, node = _zip(tmp_path)
    original = node.snapshot
    snap = unpack_snapshot(original)
    cloud = Snapshot(snap.device, snap.inode, snap.size, snap.modified_ns, snap.changed_ns,
                     snap.mode, 0x1000, snap.links)
    monkeypatch.setattr("je_file_tree.core.duplicates.unpack_snapshot", lambda _data: cloud)
    with pytest.raises(OSError, match="safely"):
        read_archive(node)
    monkeypatch.undo()
    def changed(_stream):
        with open(node.path, "ab") as target:
            target.write(b"changed")
        yield ArchiveMember("entry", 1)
    with pytest.raises(OSError, match="changed"):
        read_archive(node, reader=changed)


def test_real_seven_zip_and_missing_rar_tool(tmp_path, monkeypatch):
    import py7zr
    from je_file_tree.archive_formats import rar_members, seven_zip_members
    target = tmp_path / "archive.7z"
    with py7zr.SevenZipFile(target, "w") as archive:
        archive.writestr(b"contents" * 10, "folder/data.txt")
    node = next(scan(tmp_path, options=ScanOptions(workers=1)).root.iter_files())
    result = read_archive(node, reader=seven_zip_members)
    assert (result.files, result.size) == (1, 80)
    monkeypatch.setattr(py7zr.SevenZipFile, "extractall", lambda *_args: pytest.fail("extraction forbidden"))
    assert read_archive(node, reader=seven_zip_members).size == 80
    monkeypatch.setattr("je_file_tree.archive_formats.shutil.which", lambda _program: None)
    with pytest.raises(ArchiveError, match="unrar or bsdtar"):
        read_archive(node, reader=rar_members)


def test_zip_link_and_unusually_deep_names_are_omitted(tmp_path):
    target = tmp_path / "links.zip"
    with zipfile.ZipFile(target, "w") as archive:
        link = zipfile.ZipInfo("link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "../../escape")
        archive.writestr("/".join("d" for _ in range(130)) + "/deep", b"x")
    result = read_archive(next(scan(tmp_path).root.iter_files()))
    assert result.children == []
    assert result.rejected == 2


def test_symlink_source_is_refused_when_supported(tmp_path):
    _, node = _zip(tmp_path)
    link = tmp_path / "symlink.zip"
    try:
        os.symlink(node.path, link)
    except OSError:
        pytest.skip("symlink creation requires developer mode or administrator rights")
    linked = next(n for n in scan(tmp_path).root.iter_files() if n.name == link.name)
    with pytest.raises(OSError):
        read_archive(linked)


def test_actual_rar_header_inventory_never_runs_backend_or_extracts(tmp_path, monkeypatch):
    import rarfile
    from je_file_tree.archive_formats import rar_members
    def block(kind, flags, payload):
        data = struct.pack("<BHH", kind, flags, len(payload) + 7) + payload
        return struct.pack("<H", zlib.crc32(data) & 0xFFFF) + data
    content, name = b"own stored RAR data", b"folder/data.txt"
    date = (40 << 25) | (1 << 21) | (1 << 16)
    metadata = struct.pack("<LLBLLBBHL", len(content), len(content), 3,
                           zlib.crc32(content), date, 20, 0x30, len(name), stat.S_IFREG | 0o600) + name
    target = tmp_path / "own.rar"
    target.write_bytes(b"Rar!\x1a\x07\x00" + block(0x73, 0, b"\x00" * 6)
                       + block(0x74, 0x8000, metadata) + content + block(0x7B, 0, b""))
    monkeypatch.setattr("je_file_tree.archive_formats.shutil.which", lambda _program: "fixture-backend")
    def forbid(*_args, **_kwargs):
        pytest.fail("Metadata inventory cannot run external programs or extract")
    monkeypatch.setattr(rarfile, "tool_setup", forbid)
    monkeypatch.setattr(rarfile.RarFile, "open", forbid)
    monkeypatch.setattr(rarfile.RarFile, "extractall", forbid)
    result = read_archive(next(scan(tmp_path).root.iter_files()), reader=rar_members)
    assert result.files == 1
    assert result.size == len(content)
    assert result.children[0].children[0].name == "data.txt"


def test_encrypted_seven_zip_header_is_unavailable(tmp_path):
    import py7zr
    from je_file_tree.archive_formats import seven_zip_members
    target = tmp_path / "encrypted.7z"
    with py7zr.SevenZipFile(target, "w", password=os.urandom(16).hex(), header_encryption=True) as archive:
        archive.writestr(b"own fixture", "data.txt")
    with pytest.raises(ArchiveError):
        read_archive(next(scan(tmp_path).root.iter_files()), reader=seven_zip_members)
