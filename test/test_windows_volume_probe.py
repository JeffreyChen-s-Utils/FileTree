"""Privileged private-volume tooling refuses existing/ambiguous scopes before native commands."""

import ctypes
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from je_file_tree.core import virtual_disk_info as native
from tools import windows_owned_volume as volumes
from tools import windows_bin_probe as bins
from tools import validate_windows_volume as probe
from tools.volume_evidence import ledger_record
from tools import windows_compaction_probe as compaction


def test_existing_image_is_preserved_before_native_creation(tmp_path):
    path = tmp_path / "owned.vhdx"
    path.write_bytes(b"unrelated existing bytes")
    with pytest.raises(RuntimeError, match="existing"):
        volumes._create(SimpleNamespace(CreateVirtualDisk=lambda *_args: pytest.fail("Existing image opened")),
                        path, bytes(16))
    assert path.read_bytes() == b"unrelated existing bytes"


@pytest.mark.parametrize("physical,label", [(r"\\.\PhysicalDrive0", "FT-0123456789ab"),
                                           (r"\\.\C:", "FT-0123456789ab"),
                                           (r"\\.\PhysicalDrive1\extra", "FT-0123456789ab"),
                                           (r"\\.\PhysicalDrive1", "FT-invalid; Remove-Item")])
def test_unknown_device_and_label_never_start_formatting(monkeypatch, physical, label):
    monkeypatch.setattr(volumes.subprocess, "run", lambda *_args, **_kw: pytest.fail("Formatting was started"))
    with pytest.raises(RuntimeError):
        volumes._initialize(physical, label)


@pytest.mark.parametrize("value", [r"\\.\PhysicalDrive0", r"\\.\C:", "unknown"])
def test_ambiguous_native_device_mappings_are_refused(value):
    def physical(_handle, _size, buffer):
        buffer.value = value
        return 0
    with pytest.raises(RuntimeError):
        volumes._physical(SimpleNamespace(GetVirtualDiskPhysicalPath=physical), ctypes.c_void_p(1))


def test_exact_native_physical_mapping_is_accepted():
    def physical(_handle, _size, buffer):
        buffer.value = r"\\.\PhysicalDrive12"
        return 0
    assert volumes._physical(SimpleNamespace(GetVirtualDiskPhysicalPath=physical), ctypes.c_void_p(1)) == (
        r"\\.\PhysicalDrive12")


@pytest.mark.parametrize("change", ["scope", "root_id", "image_id", "arrival"])
def test_cleanup_preserves_foreign_or_changed_scratch(tmp_path, change):
    owned = tmp_path / ("foreign" if change == "scope" else "filetree-owned-ntfs-fixture")
    owned.mkdir()
    image = owned / "owned.vhdx"
    image.write_bytes(b"retained fixture")
    root_id, image_id = owned.stat(), image.stat()
    directory = (root_id.st_dev, root_id.st_ino + (change == "root_id"))
    identity = (image_id.st_dev, image_id.st_ino + (change == "image_id"))
    if change == "arrival":
        (owned / "arrival").write_bytes(b"foreign arrival")
    with pytest.raises(RuntimeError):
        volumes._cleanup(owned.resolve(), image, directory, identity)
    assert image.read_bytes() == b"retained fixture" and owned.exists()


def test_successful_cleanup_removes_only_the_captured_owned_image(tmp_path):
    owned = tmp_path / "filetree-owned-ntfs-fixture"
    owned.mkdir()
    image = owned / "owned.vhdx"
    image.write_bytes(b"owned disposable fixture")
    root_id, image_id = owned.stat(), image.stat()
    volumes._cleanup(owned.resolve(), image, (root_id.st_dev, root_id.st_ino), (image_id.st_dev, image_id.st_ino))
    assert not owned.exists()


def test_detachment_failure_closes_handle_and_retains_fixture(tmp_path, monkeypatch):
    owned = tmp_path / "filetree-owned-ntfs-fixture"
    owned.mkdir()
    monkeypatch.setattr(volumes, "_administrator", lambda: None)
    monkeypatch.setattr(volumes, "_enable_volume_privilege", lambda: None)
    monkeypatch.setattr(volumes.tempfile, "mkdtemp", lambda **_kw: str(owned))
    closed = []
    library = SimpleNamespace(AttachVirtualDisk=lambda *_args: 0, DetachVirtualDisk=lambda *_args: 5)
    monkeypatch.setattr(volumes, "_library", lambda: library)
    def create(_library, path, identity, capacity=volumes._CAPACITY):
        path.write_bytes(b"owned fresh fixture")
        library.identity = identity
        return ctypes.c_void_p(123)
    monkeypatch.setattr(volumes, "_create", create)
    monkeypatch.setattr(native, "_query", lambda *_args: native._Info(2, native._Value(
        guid=native._Guid.from_buffer_copy(library.identity))))
    monkeypatch.setattr(native, "_kernel", lambda: SimpleNamespace(CloseHandle=lambda h: closed.append(h.value)))
    monkeypatch.setattr(volumes, "_physical", lambda *_args: r"\\.\PhysicalDrive9")
    monkeypatch.setattr(volumes, "_initialize", lambda *_args:
                        dict(root="Z:\\", volume_id="owned-guid", label="FT-0123456789ab"))
    monkeypatch.setattr(volumes, "verify_volume", lambda _volume: None)
    with pytest.raises(OSError, match="retained scratch"), volumes.owned_ntfs_volume() as volume:
        assert volume.image == owned / "owned.vhdx"
    assert closed == [123] and (owned / "owned.vhdx").read_bytes() == b"owned fresh fixture"


def test_nonwindows_rejects_before_native_library_or_scratch(monkeypatch):
    monkeypatch.setattr(volumes, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(volumes, "_library", lambda: pytest.fail("Non-Windows native library loaded"))
    monkeypatch.setattr(volumes.tempfile, "mkdtemp", lambda **_kw: pytest.fail("Non-Windows scratch created"))
    with pytest.raises(RuntimeError, match="Native Windows"), volumes.owned_ntfs_volume():
        pytest.fail("Non-Windows volume created")


def test_private_format_script_refuses_host_and_nonempty_disks():
    script = Path(volumes.__file__).with_name("initialize_owned_ntfs.ps1").read_text(encoding="utf-8")
    assert "Get-Disk -Number $DiskNumber" in script
    assert "$disk.IsBoot -or $disk.IsSystem" in script and "$disk.PartitionStyle -ne 'RAW'" in script
    assert "$disk.NumberOfPartitions -ne 0" in script and "$disk.Size -ne $ExpectedCapacity" in script
    assert "[ValidateSet(536870912,2147483648)][long]$ExpectedCapacity = 536870912" in script
    assert "Clear-Disk" not in script and "Remove-Partition" not in script


@pytest.mark.parametrize("tuple_result", [False, True])
def test_private_bin_fixture_reuses_bool_and_tuple_qt_receipts(tmp_path, monkeypatch, tuple_result):
    from je_file_tree.gui import file_actions
    (tmp_path / "owned-bin-fixtures").mkdir()
    volume = SimpleNamespace(root=tmp_path)
    monkeypatch.setattr(bins, "verify_volume", lambda _volume: None)
    calls = []
    def moved(path):
        source = Path(path)
        assert source.parent == tmp_path / "owned-bin-fixtures"
        assert source.name == "owned.bin" and source.read_bytes().startswith(b"owned bin payload")
        calls.append(path)
        source.unlink()
        return (True, str(tmp_path / "owned-trash")) if tuple_result else True
    monkeypatch.setattr(file_actions.QFile, "moveToTrash", moved)
    bins._trash(volume, "owned.bin")
    assert calls == [str(tmp_path / "owned-bin-fixtures" / "owned.bin")]


def test_phase_json_serializes_real_unsafe_coverage_counts_and_preserves_unknowns(tmp_path):
    from je_file_tree.core.capacity import capacity_ledger
    from je_file_tree.core.scanner import scan, ScanOptions
    output = tmp_path / "native-evidence.json"
    (tmp_path / "omitted").mkdir()
    ledger = capacity_ledger(scan(tmp_path, options=ScanOptions(exclude=("omitted",))).root)
    assert ledger.coverage.unsafe
    probe._save(output, {"phase": "capacity_and_savings", "ledger": ledger_record(ledger)})
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["phase"] == "capacity_and_savings"
    assert evidence["ledger"]["coverage"]["unsafe_folders"] == len(ledger.coverage.unsafe)
    assert "unsafe" not in evidence["ledger"]["coverage"]
    assert evidence["ledger"]["metadata_bytes"] is None
    with pytest.raises(TypeError):
        probe._save(output, {"unknown": object()})


def test_fresh_unknown_disk_format_never_reaches_native_creation(tmp_path):
    library = SimpleNamespace(CreateVirtualDisk=lambda *_args: pytest.fail("Unsupported native format"))
    with pytest.raises(RuntimeError, match="unsupported"):
        volumes._create(library, tmp_path / "owned.qcow2", bytes(16))


def test_detached_hook_refuses_replacement_and_preserves_both_owned_original_and_arrival(tmp_path):
    owned = tmp_path / "filetree-owned-ntfs-detached"
    owned.mkdir()
    image = owned / "owned.vhdx"
    image.write_bytes(b"owned original fixture")
    directory_id = (owned.stat().st_dev, owned.stat().st_ino)
    image_id = (image.stat().st_dev, image.stat().st_ino)
    original = tmp_path / "retained-original.vhdx"
    image.rename(original)
    image.write_bytes(b"foreign arrival")
    with pytest.raises(RuntimeError, match="identity changed"):
        volumes._after_detach(owned, image, (directory_id, image_id), None,
                             lambda _volume: pytest.fail("Replaced image reached callback"))
    assert image.read_bytes() == b"foreign arrival" and original.read_bytes() == b"owned original fixture"


def test_detached_hook_pins_captured_image_and_retains_it_on_hook_failure(tmp_path, monkeypatch):
    owned = tmp_path / "filetree-owned-ntfs-hook"
    owned.mkdir()
    image = owned / "owned.vhdx"
    image.write_bytes(b"owned fixture")
    identities = ((owned.stat().st_dev, owned.stat().st_ino), (image.stat().st_dev, image.stat().st_ino))
    entered = []
    from contextlib import contextmanager
    @contextmanager
    def pin(path):
        assert path == str(image)
        entered.append("pinned")
        yield
        entered.append("released")
    monkeypatch.setattr(volumes, "_pinned_file", pin)
    monkeypatch.setattr(native, "inspect_virtual_disk", lambda _disk:
                        SimpleNamespace(identifier=bytes(range(16)), dynamic=True, loaded=False))
    volume = volumes.OwnedVolume(image, bytes(16), "owned-device", tmp_path, "owned-guid", "owned-label",
                                ctypes.c_void_p(), bytes(16))
    def fail(_volume):
        assert entered == ["pinned"]
        assert _volume.identifier == bytes(range(16))
        assert _volume.creation_identifier == bytes(16)
        assert _volume.image == image
        assert (image.stat().st_dev, image.stat().st_ino) == identities[1]
        raise RuntimeError("owned guest proof failed")
    with pytest.raises(RuntimeError, match="guest proof"):
        volumes._after_detach(owned, image, identities, volume, fail)
    assert image.read_bytes() == b"owned fixture"


def test_guest_verification_requires_exact_namespace_before_any_payload_read(tmp_path, monkeypatch):
    from contextlib import nullcontext
    root = tmp_path / "owned-guest-preservation"
    root.mkdir()
    (root / "arrival.bin").write_bytes(b"owned changed fixture")
    volume = SimpleNamespace(root=tmp_path)
    monkeypatch.setattr(compaction, "_readonly_guest", lambda _volume: nullcontext(volume))
    monkeypatch.setattr(compaction, "_hash", lambda _path: pytest.fail("Changed namespace hashed"))
    with pytest.raises(RuntimeError, match="namespace changed"):
        compaction.verify_guest(volume, {"expected.bin": {}})


@pytest.mark.parametrize("failure", ["image_stat", "detached_hook"])
def test_owned_context_closes_created_handle_and_retains_image_on_observation_or_hook_failure(
        tmp_path, monkeypatch, failure):
    owned = tmp_path / "filetree-owned-ntfs-handle"
    owned.mkdir()
    image = owned / "owned.vhdx"
    monkeypatch.setattr(volumes, "_administrator", lambda: None)
    monkeypatch.setattr(volumes, "_enable_volume_privilege", lambda: None)
    monkeypatch.setattr(volumes.tempfile, "mkdtemp", lambda **_kwargs: str(owned))
    closed, detached = [], []
    def detach(*_args):
        detached.append(True)
        return 0
    library = SimpleNamespace(AttachVirtualDisk=lambda *_args: 0, DetachVirtualDisk=detach)
    monkeypatch.setattr(volumes, "_library", lambda: library)
    def create(_library, path, identity, capacity=volumes._CAPACITY):
        path.write_bytes(b"owned fresh fixture")
        library.identity = identity
        return ctypes.c_void_p(123)
    monkeypatch.setattr(volumes, "_create", create)
    monkeypatch.setattr(native, "_query", lambda *_args: native._Info(2, native._Value(
        guid=native._Guid.from_buffer_copy(library.identity))))
    monkeypatch.setattr(native, "_kernel", lambda: SimpleNamespace(
        CloseHandle=lambda handle: closed.append(handle.value)))
    monkeypatch.setattr(volumes, "_physical", lambda *_args: r"\\.\PhysicalDrive9")
    monkeypatch.setattr(volumes, "_initialize", lambda *_args:
                        dict(root="Z:\\", volume_id="owned-guid", label="FT-0123456789ab"))
    monkeypatch.setattr(volumes, "verify_volume", lambda _volume: None)
    monkeypatch.setattr(native, "inspect_virtual_disk", lambda _disk:
                        SimpleNamespace(identifier=bytes(range(16)), dynamic=True, loaded=False))
    lstat = Path.lstat
    def fail_stat(path):
        if path == image:
            raise OSError("owned image observation failed")
        return lstat(path)
    if failure == "image_stat":
        monkeypatch.setattr(Path, "lstat", fail_stat)
    def hook(_volume):
        assert closed == [123] and detached == [True]
        raise OSError("owned hook failed; retain possible attachment")
    with pytest.raises(OSError), volumes.owned_ntfs_volume(after_detach=hook):
        assert failure == "detached_hook"
    assert closed == [123] and image.read_bytes() == b"owned fresh fixture"
    assert detached == ([True] if failure == "detached_hook" else [])
