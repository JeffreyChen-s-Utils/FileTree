"""Real platform diagnostics and bounded, cancellable partial-visibility cases."""

import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from je_file_tree.core import lock_holders
from je_file_tree.core.lock_holders import Holder, LockReport, find_holders
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan


@pytest.mark.skipif(sys.platform != "win32" and not sys.platform.startswith("linux"), reason="platform API")
def test_real_open_file_reports_this_process(tmp_path: Path) -> None:
    path = tmp_path / "held.txt"
    path.write_bytes(b"held")
    root = scan(tmp_path).root
    with path.open("rb"):
        report = find_holders(root.children[0])
    assert report.error is None
    assert os.getpid() in {holder.pid for holder in report.holders}


def test_directory_query_is_bounded_and_cancelled(tmp_path: Path, monkeypatch) -> None:
    root = Node(str(tmp_path), True, children=[])
    for index in range(300):
        root.children.append(Node(str(index), False, parent=root))
    paths, incomplete = lock_holders._paths(root, None)
    assert len(paths) == 256 and incomplete
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(lock_holders, "_windows", lambda paths: pytest.fail("must not call API"))
    assert find_holders(root, cancel=cancel).incomplete


def test_proc_matches_identity_and_discloses_missing_process(tmp_path: Path) -> None:
    path = tmp_path / "held"
    path.write_bytes(b"data")
    process = tmp_path / "123"
    process.mkdir()
    (process / "comm").write_text("editor", encoding="utf-8")
    descriptors = process / "fd"
    descriptors.mkdir()
    os.link(path, descriptors / "4")
    (tmp_path / "456").mkdir()  # A process that exited before its fd directory could be read.
    report = lock_holders._linux([str(path)], None, proc=tmp_path)
    assert report.holders == [Holder(123, "editor")]
    assert report.incomplete


def test_api_failure_does_not_claim_no_holders(tmp_path: Path, monkeypatch) -> None:
    node = Node(str(tmp_path / "file"), False)
    monkeypatch.setattr(lock_holders.sys, "platform", "win32")

    def denied(paths):
        raise OSError(5, "denied")

    monkeypatch.setattr(lock_holders, "_windows", denied)
    report = find_holders(node)
    assert report.incomplete and "denied" in report.error


def test_restart_manager_retries_a_changing_list() -> None:
    def get_list(handle, needed, count, buffer, reboot):
        needed._obj.value = 1
        return 234

    report = lock_holders._processes(SimpleNamespace(RmGetList=get_list), lock_holders.wintypes.DWORD())
    assert report == LockReport(incomplete=True, error="process_list_changed")
