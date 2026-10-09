"""Private recovery evidence preserves changed sources, exact drive scope and raw unknown attribution."""

from contextlib import contextmanager
import os
from types import SimpleNamespace

import pytest

from je_file_tree.core.snapshot import stat_snapshot
from tools import windows_recovery_probe as recovery


def test_foreign_source_scope_is_refused_before_bin_or_payload_access(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "verify_volume", lambda _volume: None)
    monkeypatch.setattr(recovery.bins, "_row", lambda _volume: pytest.fail("Foreign scope queried bin"))
    volume = SimpleNamespace(root=tmp_path)
    with pytest.raises(RuntimeError, match="foreign/linked"):
        recovery._case(volume, tmp_path / "foreign", ("payload",))


def test_changed_recovery_payload_never_reaches_native_trash(tmp_path, monkeypatch):
    path = tmp_path / "owned.bin"
    path.write_bytes(b"owned original")
    captured = stat_snapshot(str(path))
    path.write_bytes(b"owned changed original")
    monkeypatch.setattr(recovery, "verify_volume", lambda _volume: None)
    monkeypatch.setattr(recovery, "trash_receipt", lambda _path: pytest.fail("Changed source reached Trash"))
    with pytest.raises(RuntimeError, match="changed"):
        recovery._trash(SimpleNamespace(root=tmp_path), [path], [captured])
    assert path.read_bytes() == b"owned changed original"


def test_trash_destination_outside_private_volume_is_refused(tmp_path, monkeypatch):
    root = tmp_path / "owned-volume"
    root.mkdir()
    path = root / "owned.bin"
    path.write_bytes(b"owned payload")
    captured = stat_snapshot(str(path))
    monkeypatch.setattr(recovery, "verify_volume", lambda _volume: None)
    def trash(_path):
        path.rename(tmp_path / "retained.bin")
        return SimpleNamespace(success=True, destination=str(tmp_path / "retained.bin"))
    monkeypatch.setattr(recovery, "trash_receipt", trash)
    with pytest.raises(RuntimeError, match="escaped private"):
        recovery._trash(SimpleNamespace(root=root), [path], [captured])
    assert (tmp_path / "retained.bin").read_bytes() == b"owned payload"


@pytest.mark.parametrize("bin_count", [0, 1])
def test_case_records_raw_deltas_separately_and_rechecks_remaining_alias(tmp_path, monkeypatch, bin_count):
    root = tmp_path / "owned-fixtures"
    root.mkdir()
    payload, keeper = root / "owned.bin", root / "alias.bin"
    payload.write_bytes(b"owned hard-link payload")
    os.link(payload, keeper)
    volume = SimpleNamespace(root=tmp_path)
    monkeypatch.setattr(recovery, "verify_volume", lambda _volume: None)
    free = iter([1000, 500, 1500])
    monkeypatch.setattr(recovery, "_free", lambda _volume: next(free))
    empty = SimpleNamespace(complete=True, count=0, size=0)
    from je_file_tree.core.trash_size import TrashUsage
    values = iter([TrashUsage(0, 0, True), TrashUsage(payload.stat().st_size, bin_count, True), TrashUsage(0, 0, True)])
    monkeypatch.setattr(recovery.bins, "_row", lambda _volume: SimpleNamespace(trash=next(values)))
    def trash(*_args):
        payload.unlink()
        return [{"source": str(payload), "success": True, "destination": None}]
    monkeypatch.setattr(recovery, "_trash", trash)
    dialog = SimpleNamespace(last_error="", model=SimpleNamespace(rows=lambda: [SimpleNamespace(trash=empty)]))
    @contextmanager
    def owned(_volume):
        yield object(), dialog, [str(tmp_path)]
    monkeypatch.setattr(recovery.bins, "owned_bin_dialog", owned)
    monkeypatch.setattr(recovery.bins, "_settled", lambda *_args: None)
    def review(*_args):
        assert bin_count == 1, "Incomplete bin must not reach permanent native emptying"
        return ["private first", "private second"]
    monkeypatch.setattr(recovery.bins, "_review", review)
    monkeypatch.setattr(recovery.bins, "_wait", lambda _app, predicate: predicate())
    pending = []
    if not bin_count:
        with pytest.raises(RuntimeError, match="Native bin count differs"):
            recovery._case(volume, root, (payload.name,), keeper, pending.append)
        assert pending[0]["phase"] == "after_trash" and not pending[0]["native_empty_completed"]
        assert pending[0]["bin_after_trash"]["count"] == 0 and pending[0]["trash_receipts"][0]["success"]
        return
    result = recovery._case(volume, root, (payload.name,), keeper, pending.append)
    assert pending[0]["phase"] == "after_trash" and result["native_empty_completed"]
    assert result["estimate"]["recoverable_max"] == 0
    assert result["observed_net_free_delta"] == 500
    assert result["observed_empty_free_delta"] == 1000
    assert result["guaranteed_file_data_recovery"] is None and result["directory_metadata_bytes"] is None
    assert result["remaining_alias_before"]["links"] == 2 and result["remaining_alias_after"]["links"] == 1
    assert result["remaining_alias_before"]["sha256"] == result["remaining_alias_after"]["sha256"]
