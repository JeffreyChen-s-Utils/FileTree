"""The native probe requires a disposable guest and retains ambiguous mount state."""

from types import SimpleNamespace
import json

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


def _simulated_guest(tmp_path, monkeypatch):
    output, cleaned = tmp_path / "proof.json", []
    monkeypatch.setattr(probe, "sys", SimpleNamespace(platform="freebsd14", argv=[
        "probe", "--disposable-vm", "--output", str(output)]))
    monkeypatch.setattr(probe.os, "getuid", lambda: 0, raising=False)
    monkeypatch.setenv("FILETREE_DISPOSABLE_FREEBSD_VM", "1")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    owner = SimpleNamespace(root=tmp_path / "new-owned", cleanup=lambda: cleaned.append(True))
    monkeypatch.setattr(probe, "OwnedNullFS", lambda: owner)
    monkeypatch.setattr(probe, "static_proof", lambda owned: {"literal": "卷 空白"})
    monkeypatch.setattr(probe, "live_proof", lambda owned, *, after_open: {"after_open": after_open})
    return output, cleaned


def test_phase_writer_uses_real_atomic_utf8_contract_and_finishes_cleanup(tmp_path, monkeypatch):
    output, cleaned = _simulated_guest(tmp_path, monkeypatch)
    assert probe.main() == 0
    proof = json.loads(output.read_text(encoding="utf-8"))
    assert proof["phase"] == "complete" and proof["static"]["literal"] == "卷 空白"
    assert proof["cleanup_verified"] and proof["source_preserved"] and proof["underlying_preserved"]
    assert cleaned == [True]


def test_initial_proof_write_error_still_attempts_owned_cleanup(tmp_path, monkeypatch):
    _output, cleaned = _simulated_guest(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise OSError("owned evidence unavailable")

    monkeypatch.setattr(probe, "_atomic_file", fail)
    with pytest.raises(OSError, match="evidence unavailable"):
        probe.main()
    assert cleaned == [True]
