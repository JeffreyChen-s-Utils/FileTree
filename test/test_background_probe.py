"""Native proof gates reject offscreen and incomplete results before claiming desktop evidence."""

from types import SimpleNamespace
import json

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


@pytest.mark.parametrize("fails", [False, True])
def test_native_probe_persists_phase_before_call_and_never_completes_failed_session(monkeypatch, tmp_path, fails):
    target = tmp_path / "evidence"
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--evidence", str(target)])
    monkeypatch.setattr(probe, "QApplication", SimpleNamespace(instance=lambda: SimpleNamespace(
        platformName=lambda: "cocoa")))
    timers = []
    monkeypatch.setattr(probe.faulthandler, "dump_traceback_later", lambda seconds, repeat:
                        timers.append((seconds, repeat)))
    monkeypatch.setattr(probe.faulthandler, "cancel_dump_traceback_later", lambda: timers.append("cancelled"))

    def session(app, owned, args, retain):
        assert owned.is_dir()
        assert json.loads((target / "background.json").read_text(encoding="utf-8"))["phase"] == "started"
        retain("notification", {"source_preserved": True})
        saved = json.loads((target / "background.json").read_text(encoding="utf-8"))
        assert saved["phase"] == "notification" and saved["session"]["source_preserved"]
        assert "owned_fixture_cleanup" not in saved
        if fails:
            raise RuntimeError("native dispatch refused")
        return {"source_preserved": True, "quit_joined": True}

    monkeypatch.setattr(probe, "_session", session)
    if fails:
        with pytest.raises(RuntimeError, match="native dispatch refused"):
            probe.main()
    else:
        probe.main()
    saved = json.loads((target / "background.json").read_text(encoding="utf-8"))
    assert saved["last_native_phase"] == "notification"
    assert saved["real_login_launch_verified"] is False
    assert timers == [(60, True), "cancelled"]
    if fails:
        assert saved["phase"] == "failed" and saved["error"] == "native dispatch refused"
        assert "owned_fixture_cleanup" not in saved
    else:
        assert saved["phase"] == "complete" and saved["owned_fixture_cleanup"]
        assert saved["session"]["quit_joined"]


@pytest.mark.parametrize("failure", ["record", "quit", "none"])
def test_native_probe_join_and_history_restoration_survive_diagnostic_or_quit_errors(monkeypatch, failure):
    original = probe.history.history_folder
    monkeypatch.setattr(probe.history, "history_folder", lambda: None)
    calls = []

    def retain(phase, proof):
        calls.append(phase)
        if failure == "record":
            raise OSError("phase write refused")

    def quit_application():
        calls.append("quit")
        if failure == "quit":
            raise RuntimeError("native quit refused")

    if failure != "none":
        with pytest.raises((OSError, RuntimeError), match="refused"):
            probe._join(SimpleNamespace(quit_application=quit_application), original, retain, {})
    else:
        probe._join(SimpleNamespace(quit_application=quit_application), original, retain, {})
    assert calls == ["joining", "quit"]
    assert probe.history.history_folder is original
