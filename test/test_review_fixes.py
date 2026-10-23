"""Regression coverage for worker failures, local path authority and Explorer quoting."""

import contextlib
import ctypes
import ntpath
import threading
from types import SimpleNamespace

import pytest

from je_file_tree import cli
from je_file_tree.core import compression_ops as compression
from je_file_tree.core import scanner
from je_file_tree.core import virtual_disk_compaction as compaction


@pytest.mark.parametrize("stage", ["priority_enter", "priority_exit", "take", "yield", "read", "merge", "warnings"])
def test_worker_captures_every_failure_and_releases_taken_work(tmp_path, monkeypatch, stage):
    root = scanner.scan(tmp_path).root
    crawler = scanner._Crawler(root, str(tmp_path), scanner.ScanOptions(workers=1))
    failure = RuntimeError("owned worker failure")

    def fail(*_args):
        raise failure

    @contextlib.contextmanager
    def priority(_gentle):
        if stage == "priority_enter":
            raise failure
        yield []
        if stage == "priority_exit":
            raise failure

    class Warnings(list):
        def extend(self, _values):
            raise failure

    monkeypatch.setattr(scanner, "background_priority", priority)
    if stage == "warnings":
        crawler.warnings = Warnings()
    targets = {"take": (crawler, "_take"), "yield": (scanner, "give_way"),
               "read": (scanner, "_read_folder"), "merge": (crawler, "_finish")}
    if stage in targets:
        monkeypatch.setattr(*targets[stage], fail)
    crawler._work()
    assert crawler._failure is failure
    assert crawler._busy == 0 and crawler._done.is_set() and crawler._stopped


def test_scan_failure_wins_over_cancel_and_joins_workers(tmp_path, monkeypatch):
    cancel = threading.Event()
    failure = RuntimeError("owned failed merge")

    def fail(*_args):
        cancel.set()
        raise failure

    monkeypatch.setattr(scanner._Crawler, "_finish", fail)
    with pytest.raises(RuntimeError) as caught:
        scanner.scan(tmp_path, options=scanner.ScanOptions(workers=4), cancel=cancel)
    assert caught.value is failure
    assert not any(thread.name.startswith("file-tree-scan-") for thread in threading.enumerate())


def test_first_failure_survives_priority_cleanup_failure(tmp_path, monkeypatch):
    first = RuntimeError("owned read failure")
    second = RuntimeError("owned priority cleanup failure")

    @contextlib.contextmanager
    def priority(_gentle):
        try:
            yield []
        finally:
            raise second

    def fail(*_args):
        raise first

    monkeypatch.setattr(scanner, "background_priority", priority)
    monkeypatch.setattr(scanner, "_read_folder", fail)
    with pytest.raises(RuntimeError) as caught:
        scanner.scan(tmp_path, options=scanner.ScanOptions(workers=1))
    assert caught.value is first


def test_simultaneous_failures_finish_all_workers(tmp_path, monkeypatch):
    for name in ("left", "right"):
        (tmp_path / name).mkdir()
    barrier = threading.Barrier(2, timeout=5)
    original = scanner._read_folder
    failures = []

    def read(folder, *args):
        if folder.parent is not None:
            error = RuntimeError(folder.name)
            failures.append(error)
            barrier.wait()
            raise error
        return original(folder, *args)

    monkeypatch.setattr(scanner, "_read_folder", read)
    with pytest.raises(RuntimeError) as caught:
        scanner.scan(tmp_path, options=scanner.ScanOptions(workers=2))
    assert len(failures) == 2 and caught.value in failures
    assert not any(thread.name.startswith("file-tree-scan-") for thread in threading.enumerate())


@pytest.mark.parametrize("stage", ["scan", "analysis", "cancel_analysis"])
def test_gui_unexpected_failure_emits_one_terminal_signal(qapp, tmp_path, monkeypatch, caplog, stage):
    from je_file_tree.gui import scan_worker

    result = scanner.scan(tmp_path)
    worker = scan_worker.ScanWorker(str(tmp_path), scanner.ScanOptions())
    outcomes, saves = [], []
    worker.failed.connect(lambda reason: outcomes.append(("failed", reason)))
    worker.cancelled.connect(lambda _result: outcomes.append(("cancelled", "")))
    worker.succeeded.connect(lambda _result: outcomes.append(("succeeded", "")))
    monkeypatch.setattr(worker, "_save_history", lambda _outcome: saves.append(True))

    def fail(*_args, **_kwargs):
        raise RuntimeError("owned GUI failure")

    def cancelled(*_args, **_kwargs):
        raise scanner.ScanCancelledError(result)

    monkeypatch.setattr(scan_worker, "scan", fail if stage == "scan" else
                        cancelled if stage == "cancel_analysis" else lambda *_args, **_kwargs: result)
    if stage != "scan":
        monkeypatch.setattr(scan_worker, "analyse", fail)
    worker.run()
    assert len(outcomes) == 1 and outcomes[0][0] == "failed" and "owned GUI failure" in outcomes[0][1]
    assert not saves
    assert any(record.exc_info for record in caplog.records)


def test_cli_unexpected_failure_retains_json_error_protocol(tmp_path, monkeypatch, capsys):
    import json

    def fail(*_args):
        raise RuntimeError("owned CLI failure")

    monkeypatch.setattr(cli, "_run_scan", fail)
    assert cli.main(["scan", str(tmp_path)]) == cli.IO_ERROR
    output = capsys.readouterr()
    assert not output.out
    assert json.loads(output.err) == {"kind": "error", "reason": "owned CLI failure"}


@pytest.mark.parametrize("path", [r"\\server\share\disk.vhdx", r"\\?\UNC\server\share\disk.vhdx",
                                 r"\\?\Volume{owned}\disk.vhdx", r"\\.\C:\disk.vhdx",
                                 r"relative\disk.vhdx", r"C:disk.vhdx", r"\disk.vhdx"])
def test_invalid_compaction_path_is_rejected_before_queries(tmp_path, monkeypatch, path):
    # These formerly plausible relative targets must not grant local authority.
    (tmp_path / "UNC" / "server" / "share").mkdir(parents=True)
    (tmp_path / "Volume{owned}").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compaction, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(compression, "_kernel", lambda: pytest.fail("invalid path reached native query"))
    with pytest.raises(ValueError, match="local-drive"), compaction._pin_local(path):
        pytest.fail("invalid path entered compaction")


@pytest.mark.parametrize("prefix", ["C:", "\\\\?\\C:"])
def test_pinning_keeps_the_original_namespace(monkeypatch, prefix):
    observed, queried = [], []
    kernel = SimpleNamespace(GetDriveTypeW=lambda root: queried.append(root) or 3)

    @contextlib.contextmanager
    def pin(_kernel, path):
        observed.append(path)
        yield

    monkeypatch.setattr(compression, "_kernel", lambda: kernel)
    monkeypatch.setattr(compression, "_pin", pin)
    monkeypatch.setattr(compression, "os", SimpleNamespace(path=ntpath))
    monkeypatch.setattr(compaction, "os", SimpleNamespace(name="nt"))
    with compaction._pin_local(prefix + r"\folder\disk.vhdx"):
        assert observed == [prefix + "\\", prefix + r"\folder", prefix + r"\folder\disk.vhdx"]
    assert queried == [prefix.removeprefix("\\\\?\\") + "\\"]


def test_non_windows_compaction_refuses_before_native_pinning(monkeypatch):
    monkeypatch.setattr(compaction, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(compaction, "_pinned_path", lambda _path: pytest.fail("native pin on POSIX"))
    with pytest.raises(ValueError, match="Windows"):
        compaction.prepare_compaction(SimpleNamespace(path=r"C:\owned.vhdx"))


@pytest.mark.parametrize("path", ["C:\\", "C:\\a b\\文件.txt", "C:\\trip,day1\\a.jpg"])
def test_explorer_uses_system_directory_and_roundtrips_argument(qapp, monkeypatch, path):
    from je_file_tree.gui import file_actions

    monkeypatch.setattr(file_actions, "_explorer_path", lambda: "C:\\Windows\\explorer.exe")
    command = file_actions.explorer_command(path)
    if not hasattr(ctypes, "WinDLL"):
        assert command.startswith('"C:\\Windows\\explorer.exe" /select,"')
        return
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    count = ctypes.c_int()
    arguments = shell.CommandLineToArgvW(command, ctypes.byref(count))
    try:
        assert list(arguments[:count.value]) == ["C:\\Windows\\explorer.exe", "/select," + ntpath.normpath(path)]
    finally:
        kernel.LocalFree(arguments)
