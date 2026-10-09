"""Pause preserves the current scan and never prevents cancellation or worker shutdown."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_gui import _wait
from je_file_tree.core import scanner
from je_file_tree.core.scanner import ScanCancelledError, ScanOptions, scan
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.scan_bar import ScanBar
from je_file_tree.gui.scan_worker import ScanWorker, wait_for


@pytest.mark.parametrize("workers", [1, 4])
def test_pause_finishes_current_folder_then_resumes_the_same_tree(tmp_path, monkeypatch, workers) -> None:
    (tmp_path / "root-file").write_bytes(b"root")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/file").write_bytes(b"nested")
    pause, reached, updated = threading.Event(), threading.Event(), threading.Event()
    original = scanner._read_folder
    reads = []

    def read(folder, path, options, allocation, excluded, boundaries):
        result = original(folder, path, options, allocation, excluded, boundaries)
        reads.append(path)
        if path == str(tmp_path):
            pause.set()
            reached.set()
        return result

    monkeypatch.setattr(scanner, "_read_folder", read)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(scan, tmp_path, options=ScanOptions(workers=workers), pause=pause,
                             progress=lambda counts: updated.set(), progress_interval=.02)
        try:
            assert reached.wait(5) and updated.wait(5)
            assert reads == [str(tmp_path)] and not future.done()
        finally:
            pause.clear()
        result = future.result(timeout=5)
    assert result.root.file_count == 2 and result.root.size == 10


def test_cancel_before_any_reads_works_while_paused(tmp_path) -> None:
    (tmp_path / "file").write_bytes(b"file")
    pause, cancel = threading.Event(), threading.Event()
    pause.set()
    with pytest.raises(ScanCancelledError) as stopped:
        scan(tmp_path, pause=pause, cancel=cancel, progress=lambda _counts: cancel.set(), progress_interval=.02)
    assert stopped.value.partial.root.file_count == 0
    assert stopped.value.partial.root.error == scanner.NOT_SCANNED


def test_qt_paused_worker_can_be_cancelled_and_joined(qapp, tmp_path) -> None:
    worker = ScanWorker(str(tmp_path), ScanOptions(workers=2))
    outcomes = []
    roots = []
    worker.cancelled.connect(outcomes.append)
    worker.started.connect(roots.append)
    assert worker.set_paused(True)
    worker.start()
    _wait(qapp, lambda: bool(roots))
    worker.cancel()
    wait_for(worker)
    _wait(qapp, lambda: bool(outcomes))
    assert not worker.set_paused(True) and outcomes[0].partial
    worker.deleteLater()


def test_pause_bar_resets_and_disables_pause_during_final_analysis(qapp) -> None:
    bar = ScanBar()
    requests = []
    bar.pause_requested.connect(requests.append)
    bar.start()
    bar._pause.click()
    assert requests == [True] and bar._pause.text() == tr("scan_resume")
    bar.analysing()
    assert not bar._pause.isEnabled() and bar._counts.text() == tr("scan_analysing")
    bar.start()
    assert not bar._pause.isChecked() and bar._pause.isEnabled()
    bar.stopping()
    assert not bar._pause.isEnabled()
    bar.deleteLater()
