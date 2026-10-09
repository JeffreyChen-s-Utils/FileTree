"""Persisted concurrency applies to new scan options, with a measured fallback and explicit cancel."""

import pytest

from test_gui import window as window  # noqa: PLC0414 - explicit fixture re-export
from je_file_tree.gui import main_window as main


@pytest.mark.parametrize("value", (None, "invalid", -1, 0, 33, True, 4.5))
def test_invalid_saved_concurrency_uses_default(window, value):
    window.settings.setValue(main.SCAN_WORKERS_KEY, value)
    assert main.read_workers(window.settings) == main.DEFAULT_WORKERS
    assert window._scan_options().workers == main.DEFAULT_WORKERS


def test_options_save_and_decline_leave_current_worker_unchanged(window, monkeypatch):
    observed = []
    def choose(_parent, _title, prompt, value, minimum, maximum, step):
        observed.append((value, minimum, maximum, step))
        assert "Running scans" in prompt
        return 8, True
    monkeypatch.setattr(main.QInputDialog, "getInt", choose)
    original = window._scan_options()
    worker = main.ScanWorker("owned-unstarted", original, window)
    window._worker = worker
    try:
        window.configure_workers()
        assert observed == [(main.DEFAULT_WORKERS, 1, 32, 1)]
        assert window._scan_options().workers == 8
        assert worker._options is original and original.workers == main.DEFAULT_WORKERS
        monkeypatch.setattr(main.QInputDialog, "getInt", lambda *_args: (4, False))
        window.configure_workers()
        assert window._scan_options().workers == 8
    finally:
        window._worker = None
        worker.deleteLater()
