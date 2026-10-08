"""Native proof gates reject offscreen and incomplete results before claiming desktop evidence."""

from types import SimpleNamespace

import pytest

from tools import validate_background as probe


def test_background_probe_requires_native_rendering_before_creating_evidence(qapp, monkeypatch, tmp_path):
    target = tmp_path / "evidence"
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--evidence", str(target)])
    monkeypatch.setattr(probe, "QApplication", SimpleNamespace(instance=lambda: SimpleNamespace(
        platformName=lambda: "offscreen")))
    with pytest.raises(RuntimeError, match="Native desktop"):
        probe.main()
    assert not target.exists()


def test_native_notification_requirement_refuses_unsupported_platform_before_dispatch(monkeypatch):
    monkeypatch.setattr(probe, "QSystemTrayIcon", SimpleNamespace(supportsMessages=lambda: False))
    with pytest.raises(RuntimeError, match="unsupported"):
        probe._notification(None, None, None, required=True)
    assert probe._notification(None, None, None, required=False) == {"supported": False, "display_verified": False}
