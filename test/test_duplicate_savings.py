"""Duplicate extra-copy estimates use allocation and leave external hard-link data allocated."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace

from je_file_tree.core.duplicates import DuplicateGroup, estimate_duplicate_savings, find_duplicates
from je_file_tree.core.node import Node
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import pack_snapshot


def test_hard_link_name_outside_scan_keeps_extra_copy_allocation(tmp_path: Path) -> None:
    folder = tmp_path / "scan"
    folder.mkdir()
    (folder / "keep").write_bytes(b"data" * 4096)
    (folder / "extra").write_bytes(b"data" * 4096)
    os.utime(folder / "keep", (1_600_000_000, 1_600_000_000))
    os.link(folder / "extra", tmp_path / "outside")
    root = scan(folder).root
    groups = find_duplicates(root, min_size=1).groups
    value = estimate_duplicate_savings(groups, root)
    assert value.total.logical == 16384 and value.total.allocated > 0
    assert value.total.recoverable_max == 0
    assert value.groups[0].allocated == value.total.allocated


def test_special_files_distinguish_logical_allocated_and_recoverable(tmp_path: Path) -> None:
    root = scan(tmp_path).root
    groups = []
    for inode, attributes, allocated in [(2, 0x800, 4096), (4, 0x200, 8192), (6, 0x400000, 0)]:
        nodes = []
        for index in range(2):
            info = SimpleNamespace(st_dev=1, st_ino=inode + index, st_size=1 << 20, st_mode=0o100644,
                                   st_mtime_ns=1, st_ctime_ns=1, st_nlink=1, st_file_attributes=attributes)
            nodes.append(Node(str(index), False, size=info.st_size, allocated=allocated, parent=root,
                              snapshot=pack_snapshot(info)))
        groups.append(DuplicateGroup(1 << 20, nodes))
    value = estimate_duplicate_savings(groups, root, limit=2)
    assert value.total.logical == 3 << 20 and value.total.allocated == 12288
    assert value.total.recoverable_min == 0 and value.total.recoverable_max == 12288
    assert len(value.groups) == 2 and value.total.uncertain
    groups[0].files[1].snapshot = None
    assert estimate_duplicate_savings(groups, root).total.recoverable_max is None
    cancel = threading.Event()
    cancel.set()
    assert estimate_duplicate_savings(groups, root, cancel=cancel) is None
