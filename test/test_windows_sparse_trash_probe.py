"""Sparse diagnostic refusal, durable unknown outcomes and exact owned-volume observations."""

from contextlib import contextmanager
from dataclasses import asdict
import sys
from types import SimpleNamespace

import pytest

from je_file_tree.core.snapshot import stat_snapshot
from je_file_tree.core.trash_size import TrashUsage
from tools import windows_owned_volume as volumes
from tools import windows_sparse_trash_probe as probe


@pytest.mark.parametrize("capacity", [0, 1, 1024 * 1024 * 1024, 4096 * 1024 * 1024])
def test_unknown_fixture_capacities_never_reach_administrator_or_native_creation(capacity, monkeypatch, tmp_path):
    monkeypatch.setattr(volumes, "_administrator", lambda: pytest.fail("Invalid capacity reached native setup"))
    with pytest.raises(RuntimeError, match="capacity"), volumes.owned_ntfs_volume(capacity=capacity):
        pytest.fail("Unapproved fixture yielded")
    with pytest.raises(RuntimeError, match="capacity"):
        volumes._create(SimpleNamespace(), tmp_path / "owned.vhdx", bytes(16), capacity)


def test_foreign_diagnostic_scope_is_refused_before_bin_or_payload_access(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "verify_volume", lambda _volume: None)
    monkeypatch.setattr(probe.recovery.bins, "_row", lambda _volume: pytest.fail("Foreign bin queried"))
    with pytest.raises(RuntimeError, match="foreign"):
        probe._case(SimpleNamespace(root=tmp_path), tmp_path / "foreign", 8, lambda _value: None)


def test_existing_diagnostic_payload_is_preserved(tmp_path):
    path = tmp_path / "owned.bin"
    path.write_bytes(b"existing bytes")
    with pytest.raises(RuntimeError, match="existing"):
        probe._write_sparse(path, 8)
    assert path.read_bytes() == b"existing bytes"


@pytest.mark.parametrize("bin_count", [0, 1, 2])
def test_missing_bin_is_retained_as_unknown_and_never_authorizes_emptying(tmp_path, monkeypatch, bin_count):
    root = tmp_path / "owned-fixtures"
    root.mkdir()
    volume = SimpleNamespace(root=tmp_path)
    monkeypatch.setattr(probe, "verify_volume", lambda _volume: None)
    length = 8
    def create(path, expected):
        assert expected == length
        path.write_bytes(b"payload!")
        return {"snapshot": stat_snapshot(str(path)).hex(), "logical": expected, "sha256": "captured"}
    monkeypatch.setattr(probe, "_write_sparse", create)
    values = iter([TrashUsage(0, 0, True), TrashUsage(length if bin_count else 0, bin_count, True)])
    monkeypatch.setattr(probe.recovery.bins, "_row", lambda _volume: SimpleNamespace(trash=next(values)))
    free = iter([1000, 1050, 1100])
    monkeypatch.setattr(probe.recovery, "_free", lambda _volume: next(free))
    def trash(_volume, paths, captured):
        assert stat_snapshot(str(paths[0])) == captured[0]
        paths[0].unlink()
        return [{"success": True, "destination": None}]
    monkeypatch.setattr(probe.recovery, "_trash", trash)
    called = []
    dialog = SimpleNamespace(last_error="")
    @contextmanager
    def owned(_volume):
        yield object(), dialog, called
    monkeypatch.setattr(probe.recovery.bins, "owned_bin_dialog", owned)
    monkeypatch.setattr(probe.recovery.bins, "_settled", lambda *_args: None)
    monkeypatch.setattr(probe, "_settings", lambda _volume: {"effective_quota_bytes": None})
    monkeypatch.setattr(probe, "_inventory", lambda _volume: {"entries": []})
    monkeypatch.setattr(probe.recovery.bins, "_wait", lambda *_args: None)
    def review(*_args):
        assert bin_count == 1, "Unexpected native bin must not authorize emptying"
        called.append(str(tmp_path))
        return ["first private question", "second private question"]
    monkeypatch.setattr(probe.recovery.bins, "_review", review)
    pending = []
    if bin_count > 1:
        with pytest.raises(RuntimeError, match="Unexpected private bin"):
            probe._case(volume, root, length, pending.append)
        assert pending[0]["native_bin"] == asdict(TrashUsage(length, 2, True))
        assert not called
        return
    result = probe._case(volume, root, length, pending.append)
    assert pending[0]["phase"] == "after_trash" and result["phase"] == "observed"
    assert result["source_absent"] and result["qt_receipts"][0]["success"]
    assert result["native_empty_completed"] == bool(bin_count)
    assert result["retention"] == ("native_bin_observed" if bin_count else "unknown")
    assert result["guaranteed_recovery"] is None and result["observed_trash_free_delta"] == 50


def test_registry_lookup_reads_only_the_verified_private_volume_and_never_claims_effective_quota(monkeypatch):
    monkeypatch.setattr(probe, "verify_volume", lambda _volume: None)
    accesses = []
    @contextmanager
    def opened(hive, key, _reserved, access):
        accesses.append((hive, key, access))
        yield object()
    registry = SimpleNamespace(OpenKey=opened, HKEY_CURRENT_USER="current-user", KEY_READ=1,
                               QueryValueEx=lambda _handle, name: (51 if name == "MaxCapacity" else 0, 4))
    monkeypatch.setitem(sys.modules, "winreg", registry)
    volume = SimpleNamespace(volume_id="\\\\?\\Volume{01234567-89ab-cdef-0123-456789abcdef}\\")
    result = probe._settings(volume)
    assert accesses[0][1].endswith(r"Volume\{01234567-89ab-cdef-0123-456789abcdef}")
    assert result["key_present"] and result["effective_quota_bytes"] is None
    assert result["values"]["MaxCapacity"]["value"] == 51
    volume.volume_id = "foreign\\GUID"
    with pytest.raises(RuntimeError, match="Unknown private volume"):
        probe._settings(volume)
    assert len(accesses) == 1
