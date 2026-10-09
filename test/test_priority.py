"""Priority is applied to disposable workers, with explicit best-effort failures."""

import sys
import threading
from contextlib import contextmanager

import pytest

from je_file_tree import cli
from je_file_tree.core import priority, scanner
from je_file_tree.core.scanner import ScanOptions, scan


def test_disabled_priority_never_calls_platform_apis(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(priority, "_windows_mode", calls.append)
    with priority.background_priority(False) as warnings:
        assert warnings == []
    assert calls == []


def test_windows_background_mode_restores_after_worker_failure(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    calls = []
    monkeypatch.setattr(priority, "_windows_mode", calls.append)
    with pytest.raises(RuntimeError), priority.background_priority(True):
        raise RuntimeError("worker failure")
    assert calls == [priority._BACKGROUND_BEGIN, priority._BACKGROUND_END]


def test_priority_failures_are_reported_without_claiming_success(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")

    def denied(mode):
        raise OSError("priority unavailable")

    monkeypatch.setattr(priority, "_windows_mode", denied)
    with priority.background_priority(True) as warnings:
        assert warnings == ["priority unavailable"]


def test_each_crawler_thread_changes_priority_and_keeps_readable_results(tmp_path, monkeypatch) -> None:
    (tmp_path / "file").write_bytes(b"bytes")
    calls = []

    @contextmanager
    def unavailable(enabled):
        calls.append((enabled, threading.get_ident()))
        yield ["priority unavailable"]

    monkeypatch.setattr(scanner, "background_priority", unavailable)
    result = scan(tmp_path, options=ScanOptions(workers=3, gentle=True))
    assert len(calls) == 3 and all(enabled and tid != threading.get_ident() for enabled, tid in calls)
    assert result.root.size == 5 and not result.errors and result.warnings == ["priority unavailable"]


def test_cli_gentle_option_passes_through() -> None:
    assert cli._parser().parse_args(["scan", ".", "--gentle"]).gentle
    assert not cli._parser().parse_args(["scan", "."]).gentle


@pytest.mark.skipif(sys.platform != "win32", reason="Windows background mode")
def test_real_windows_background_mode_succeeds_on_a_disposable_thread() -> None:
    warnings = []

    def worker():
        with priority.background_priority(True) as result:
            pass
        warnings.extend(result)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert warnings == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux thread priority")
def test_real_linux_priority_targets_worker_without_lowering_calling_thread() -> None:
    import os  # noqa: PLC0415 - platform-specific test

    before = os.getpriority(os.PRIO_PROCESS, threading.get_native_id())
    observed = []

    def worker():
        with priority.background_priority(True) as warnings:
            observed.append((os.getpriority(os.PRIO_PROCESS, threading.get_native_id()), warnings.copy()))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert observed[0][0] >= priority._NICE
    assert os.getpriority(os.PRIO_PROCESS, threading.get_native_id()) == before
