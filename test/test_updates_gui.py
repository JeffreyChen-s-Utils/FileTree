"""Entry-point-only update scheduling, durable failed attempts and owned cancel/close lifetimes."""

import threading

import pytest

from test_gui import _wait, window as window  # noqa: PLC0414 - shared pytest fixture
from je_file_tree.gui import updates


@pytest.fixture
def notice(window, tmp_path, monkeypatch):
    monkeypatch.setattr(updates.QStandardPaths, "writableLocation", lambda _kind: str(tmp_path / "owned-data"))
    return window._updates


def test_window_construction_and_disabled_scheduling_never_access_network(window, notice, monkeypatch):
    monkeypatch.setattr(updates, "fetch_release", lambda *_args: pytest.fail("Unexpected network request"))
    notice.check()
    assert not notice._active and notice.worker is None
    assert not notice.settings.contains(updates.ENABLED_KEY)
    window._actions["check_updates"].setChecked(False)
    notice.start()
    notice.check()
    assert not notice.enabled() and not notice.timer.isActive() and notice.worker is None
    assert not notice.settings.contains(updates.ATTEMPT_KEY)


def test_attempt_is_persisted_before_request_and_second_window_is_throttled(window, notice, qapp, monkeypatch):
    calls = []

    def fetch(_version, _cancel):
        assert notice.settings.contains(updates.ATTEMPT_KEY)
        calls.append(True)
        return "9.1.2"

    monkeypatch.setattr(updates, "fetch_release", fetch)
    notice.start()
    notice.check()
    _wait(qapp, lambda: notice.worker is None)
    assert len(calls) == 1 and notice.version == "9.1.2" and not notice.label.isHidden()
    assert 'href="https://pypi.org/project/je-file-tree/9.1.2/"' in notice.label.text()
    second = updates.UpdateNotice(notice.settings, window)
    try:
        second.start()
        second.check()
        notice.check()
        assert second.worker is None and notice.worker is None and len(calls) == 1
        window.change_language("zh-TW")
        assert "已推出" in notice.label.text()
    finally:
        second.shutdown()


def test_failed_attempt_remains_throttled_and_preserves_observed_error(notice, qapp, monkeypatch):
    def fail(_version, _cancel):
        raise TimeoutError("owned simulated timeout")

    monkeypatch.setattr(updates, "fetch_release", fail)
    notice.start()
    notice.check()
    _wait(qapp, lambda: notice.worker is None)
    assert notice.last_error == "owned simulated timeout" and notice.label.isHidden()
    notice.check()
    assert notice.worker is None


@pytest.mark.parametrize("closing", [False, True])
def test_disabling_or_closing_cancels_owned_request_and_discards_late_notice(
        window, notice, qapp, monkeypatch, closing):
    entered = threading.Event()

    def delayed(_version, cancel):
        entered.set()
        assert cancel.wait(5)
        return "9.9.9"

    monkeypatch.setattr(updates, "fetch_release", delayed)
    notice.start()
    notice.check()
    cancelled = notice.worker.cancel
    _wait(qapp, entered.is_set)
    if closing:
        window.close()
        _wait(qapp, lambda: window._close_ready)
    else:
        window._actions["check_updates"].setChecked(False)
    _wait(qapp, lambda: notice.worker is None)
    assert cancelled.is_set()
    assert not notice.version and notice.label.isHidden()
