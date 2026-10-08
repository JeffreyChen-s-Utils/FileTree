"""The native probe requires a disposable guest and retains ambiguous mount state."""

from types import SimpleNamespace

import pytest

from tools import validate_freebsd_mounts as probe


def test_wrong_platform_refuses_before_fixture_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "sys", SimpleNamespace(platform="win32", argv=[
        "probe", "--disposable-vm", "--output", str(tmp_path / "proof.json")]))
    monkeypatch.setattr(probe.tempfile, "mkdtemp", lambda **kwargs: pytest.fail("Created a host fixture"))
    with pytest.raises(RuntimeError, match="disposable native CI guest"):
        probe.main()
    assert not (tmp_path / "proof.json").exists()


def test_uncertain_mount_keeps_its_owned_scratch(tmp_path, monkeypatch):
    owned = object.__new__(probe.OwnedNullFS)
    owned.root, owned.mounted, owned.attempted = tmp_path, False, True
    monkeypatch.setattr(owned, "check", lambda: None)
    monkeypatch.setattr(probe, "mount_points", frozenset)
    with pytest.raises(RuntimeError, match="Uncertain"):
        owned.cleanup()
    assert tmp_path.is_dir()


@pytest.mark.parametrize("change", ["payload", "replacement", "arrival"])
def test_changed_underlying_fixture_or_arrival_is_retained(tmp_path, monkeypatch, change):
    monkeypatch.setattr(probe.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))
    owned = probe.OwnedNullFS()
    monkeypatch.setattr(owned, "check", lambda: None)  # Private POSIX permission bits are unavailable on Windows.
    monkeypatch.setattr(probe, "mount_points", frozenset)
    if change == "payload":
        owned.original.write_bytes(b"changed disposable payload")
    elif change == "replacement":
        owned.target.rename(tmp_path / "retained-original")
        owned.target.mkdir()
        (owned.target / "original").write_bytes(b"new disposable arrival")
    else:
        (tmp_path / "arrival").write_bytes(b"new disposable arrival")
    with pytest.raises(RuntimeError, match="changed|arrival"):
        owned.cleanup()
    assert tmp_path.is_dir() and owned.payload.is_file()
