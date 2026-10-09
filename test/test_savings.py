"""Recovery ranges account for shared names, special allocation and incomplete snapshots."""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace

from je_file_tree.core.allocation import estimate_savings
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.snapshot import pack_snapshot


def test_overlapping_selection_and_hard_links_count_allocation_once(tmp_path: Path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    first = folder / "first"
    first.write_bytes(b"data" * 4096)
    os.link(first, folder / "second")
    root = scan(tmp_path).root
    directory = root.children[0]
    one = directory.children[0]
    selected = estimate_savings([directory, one], root=root)
    assert selected.logical == first.stat().st_size * 2
    assert selected.allocated == one.allocated
    assert selected.recoverable_min == 0 and selected.recoverable_max == one.allocated
    only_one_name = estimate_savings([one], root=root)
    assert only_one_name.allocated == one.allocated
    assert only_one_name.recoverable_max == 0, "the other hard-link name still holds the file data"


def test_hard_link_outside_the_scan_cannot_be_offered_as_recoverable(tmp_path: Path) -> None:
    folder = tmp_path / "scan"
    folder.mkdir()
    file = folder / "file"
    file.write_bytes(b"data" * 4096)
    os.link(file, tmp_path / "outside")
    root = scan(folder).root
    value = estimate_savings(root.children, root=root)
    assert value.logical > 0 and value.allocated > 0
    assert value.recoverable_max == 0


def test_partial_and_unverified_selections_report_unknown(tmp_path: Path) -> None:
    (tmp_path / "cache" / "skipped").mkdir(parents=True)
    root = scan(tmp_path, options=ScanOptions(exclude=("skipped",))).root
    assert estimate_savings(root.children, root=root).recoverable_max is None
    assert estimate_savings([Node("file", False, size=10, allocated=4096)]).recoverable_max is None


def _special(attributes: int, allocated: int) -> Node:
    info = SimpleNamespace(st_dev=1, st_ino=2, st_size=1 << 20, st_mode=0o100644, st_mtime_ns=1,
                           st_ctime_ns=1, st_nlink=1, st_file_attributes=attributes)
    return Node("special", False, size=info.st_size, allocated=allocated, snapshot=pack_snapshot(info))


def test_compressed_sparse_and_cloud_files_use_allocation_not_logical_size() -> None:
    for attributes in (0x800, 0x200):
        node = _special(attributes, 4096)
        value = estimate_savings([node])
        assert value.logical == 1 << 20 and value.allocated == 4096
        assert value.recoverable_max == 4096
    for attributes in (0x1000, 0x40000, 0x400000):
        value = estimate_savings([_special(attributes, 0)])
        assert value.logical == 1 << 20 and value.allocated == 0
        assert value.recoverable_max == 0 and value.uncertain


def test_free_space_is_the_os_measurement_and_cancel_has_no_result(tmp_path: Path) -> None:
    (tmp_path / "file").write_bytes(b"data")
    root = scan(tmp_path).root
    value = estimate_savings(root.children, root=root)
    assert value.free_now is not None and 0 <= value.free_now <= shutil.disk_usage(tmp_path).total
    cancel = threading.Event()
    cancel.set()
    assert estimate_savings(root.children, cancel=cancel) is None
