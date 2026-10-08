"""Diagnostic phase persistence and failure cleanup use mocked fixtures, not native validation claims."""

from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest

from tools import validate_mft as probe


@pytest.mark.parametrize("fail", [False, True])
def test_atomic_utf8_phase_evidence_and_fixture_exit(tmp_path, monkeypatch, fail):
    output = tmp_path / "evidence.json"
    exits = []

    @contextmanager
    def owned():
        try:
            yield SimpleNamespace(root=tmp_path / "owned")
        finally:
            exits.append(True)

    def proof(_volume):
        if fail:
            raise ValueError("metadata rejected")
        return {"source_preserved": True, "scanner_enabled": False}

    monkeypatch.setattr(probe, "owned_ntfs_volume", owned)
    monkeypatch.setattr(probe, "_proof", proof)
    monkeypatch.setattr(probe.sys, "argv", ["validate_mft.py", "--output", str(output)])
    if fail:
        with pytest.raises(ValueError, match="metadata rejected"):
            probe.main()
    else:
        probe.main()
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert exits == [True]
    assert evidence["phase"] == ("failed" if fail else "complete")
    assert evidence["cleanup_verified"] is not fail
