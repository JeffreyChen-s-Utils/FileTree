"""Native evidence refuses wrong platforms and incomplete extended-attribute payloads."""

import hashlib

import pytest

from tools import validate_macos_sources as probe


def test_native_probe_refuses_other_platforms_before_creating_fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.sys, "platform", "linux")
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--evidence", str(tmp_path / "evidence")])
    with pytest.raises(ValueError, match="Native macOS"):
        probe.main()
    assert not (tmp_path / "evidence").exists()


def test_native_probe_refuses_overridden_rendering_before_creating_fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(probe.sys, "platform", "darwin")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--evidence", str(tmp_path / "evidence")])
    with pytest.raises(ValueError, match="Native cocoa"):
        probe.main()
    assert not (tmp_path / "evidence").exists()


def test_resource_fork_evidence_hashes_complete_bytes_and_refuses_length_only(tmp_path, monkeypatch):
    source = tmp_path / "owned.bin"
    source.write_bytes(b"kept payload")
    value = b"owned resource fork"
    monkeypatch.setattr(probe, "mac_xattrs",
                        lambda *_args, **_kwargs: ((b"com.apple.ResourceFork", len(value), value),))
    before = source.stat()
    proof = probe._proof(source)
    assert proof["sha256"] == hashlib.sha256(b"kept payload").hexdigest()
    assert proof["identity"] == [before.st_dev, before.st_ino]
    assert proof["attributes"]["com.apple.ResourceFork"]["sha256"] == hashlib.sha256(value).hexdigest()
    monkeypatch.setattr(probe, "mac_xattrs", lambda *_args, **_kwargs: ((b"com.apple.ResourceFork", len(value), None),))
    with pytest.raises(RuntimeError, match="Incomplete attribute"):
        probe._proof(source)
    assert source.read_bytes() == b"kept payload" and source.stat().st_ino == before.st_ino
