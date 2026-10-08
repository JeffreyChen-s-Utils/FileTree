"""Explicit experimental NTFS metadata tree; native ACL snapshots remain the authority, no elevation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import os
import stat
import sys
import threading
import time
from types import SimpleNamespace
from typing import cast

from je_file_tree.core import mft
from je_file_tree.core.allocation import allocation_for
from je_file_tree.core.exclusions import exclusion_test
from je_file_tree.core.hard_links import account_hard_links
from je_file_tree.core.mft_reader import NTFSReader
from je_file_tree.core.mounts import MountSurvey, mount_points
from je_file_tree.core.no_replace import anchored_directory, directory_stamps
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.priority import background_priority
from je_file_tree.core.scanner import (ACCESS_DENIED, HIDDEN_OMITTED, NOT_SCANNED, PARTIAL_FOLDER,
                                      ProgressCallback, ScanCancelledError, ScanOptions, ScanProgress,
                                      ScanResult, _add_up, _FolderRead, _record_entries)
from je_file_tree.core.snapshot import unpack_snapshot
from je_file_tree.core.windows_directory import WindowsEntry, directory_entries

_UNAVAILABLE = 0x400 | 0x1000 | 0x40000 | 0x400000
_DOS_NAMESPACE = 2
_LOG = logging.getLogger(__name__)
_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mode", "st_nlink", "st_mtime_ns", "st_ctime_ns",
                "st_mtime", "st_ctime", "st_atime", "st_file_attributes", "st_reparse_tag", "st_uid", "st_gid")


class _CallbackError(Exception):
    def __init__(self, error: Exception) -> None:
        super().__init__(str(error))
        self.error = error


def _notify(callback: ProgressCallback, progress: ScanProgress) -> None:
    try:
        callback(progress)
    except (OSError, ValueError) as error:
        raise _CallbackError(error) from error


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise mft.MFTParseError(detail)


def _audit(native: NTFSReader, info: os.stat_result, visible: WindowsEntry,
           parent: int, check: Callable[[], None]) -> SimpleNamespace:
    record = native.record(info.st_ino & ((1 << 48) - 1))
    _require(record.in_use and not record.base_reference and record.reference == info.st_ino,
             "Native path differs from live sequence-qualified MFT identity")
    _require(record.links == info.st_nlink and record.is_dir == stat.S_ISDIR(info.st_mode),
             "Native path differs from MFT link count/type")
    attributes = native.attributes(record, check)
    _require(all(item.resident and item.value is not None for item in attributes
                 if item.kind in (mft.FILE_NAME, mft.STANDARD_INFORMATION)),
             "MFT name/standard metadata must be resident and bounded")
    names = [mft.parse_file_name(item.value) for item in attributes if item.kind == mft.FILE_NAME]
    _require(any(item.name == visible.name and item.parent == parent and item.namespace != _DOS_NAMESPACE
                 for item in names),
             "MFT name/parent lacks native directory visibility")
    standards = [mft.parse_standard_information(item.value) for item in attributes
                 if item.kind == mft.STANDARD_INFORMATION]
    _require(len(standards) == 1, "Missing or ambiguous MFT standard metadata")
    standard = standards[0]
    created = getattr(info, "st_birthtime_ns", info.st_ctime_ns)
    _require((standard.modified_ns, standard.created_ns) == (info.st_mtime_ns, created),
             "Native path differs from MFT modification/creation dates")
    result = SimpleNamespace(**{name: getattr(info, name, 0) for name in _STAT_FIELDS})
    result.st_birthtime = getattr(info, "st_birthtime", info.st_ctime)
    result.st_mtime_ns, result.st_ctime_ns, result.st_nlink = standard.modified_ns, created, record.links
    if not record.is_dir:
        heads = [item for item in attributes if item.kind == mft.DATA and not item.name and not item.lowest_vcn]
        _require(len(heads) == 1 and heads[0].size == info.st_size,
                 "Native path differs from MFT unnamed data size")
        result.st_size = heads[0].size
    _require(all(item.value is None for item in attributes if item.kind == mft.DATA),
             "MFT DATA payload must not enter a scanned node")
    return result


class _Entry:
    def __init__(self, path: str, visible: WindowsEntry, native: NTFSReader,
                 parent: int, check: Callable[[], None]) -> None:
        self.name, self.path = visible.name, os.path.join(path, visible.name)
        self._check = check
        self.error, self.info = None, None
        try:
            info = os.lstat(self.path)  # Ordinary no-follow path permission/identity remains mandatory.
        except OSError as error:
            self.error = error
            return
        listed = visible.file_id, visible.attributes, visible.times[2]
        observed = info.st_ino, info.st_file_attributes, info.st_mtime_ns
        _require(listed == observed,
                 f"Native directory entry changed before ordinary path metadata: {visible.name!r}; "
                 f"listing={listed}, path={observed}")
        if not stat.S_ISDIR(info.st_mode) and not info.st_file_attributes & _UNAVAILABLE:
            _require(visible.size == info.st_size, "Native directory size changed before path metadata")
        self.info = (info if info.st_file_attributes & _UNAVAILABLE
                     else _audit(native, info, visible, parent, check))

    def stat(self, *, follow_symlinks: bool = False) -> os.stat_result:
        self._check()
        if follow_symlinks:
            raise ValueError("Experimental NTFS entries never follow payload links")
        if self.error is not None:
            raise self.error
        return cast(os.stat_result, self.info)

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        return os.path.isdir(self.path) if follow_symlinks else stat.S_ISDIR(self.stat().st_mode)


@dataclass
class _Tree:
    root: Node
    cancel: threading.Event | None
    pause: threading.Event | None
    folders: list[Node] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    files: int = 0
    size: int = 0

    def check(self) -> None:
        while True:
            if self.cancel is not None and self.cancel.is_set():
                _add_up(self.folders)
                raise ScanCancelledError(ScanResult(self.root, self.errors, backend="mft"))
            if self.pause is None or not self.pause.is_set():
                return
            time.sleep(0.05)


def _read(folder: Node, path: str, native: NTFSReader, tree: _Tree,
          options: ScanOptions, boundaries: MountSurvey) -> _FolderRead:
    read = _FolderRead()
    expected = unpack_snapshot(cast(bytes, folder.snapshot))
    try:
        with anchored_directory(directory_stamps(path)):
            listing = [_Entry(path, item, native, expected.inode, tree.check)
                       for item in directory_entries(path, expected, check=tree.check)]
            _record_entries(folder, listing, options,
                            allocation_for(path, exact_windows=options.exact_windows_allocation),
                            exclusion_test(options.exclude), boundaries, read)
    except ScanCancelledError:
        _merge_read(tree, read)
        _add_up(tree.folders)
        raise
    except PermissionError:
        folder.error = ACCESS_DENIED
        read.errors.append((path, ACCESS_DENIED))
        return read
    folder.error = (HIDDEN_OMITTED if all(reason == HIDDEN_OMITTED for _, reason in read.errors)
                    else PARTIAL_FOLDER) if read.errors else None
    return read


def _merge_read(tree: _Tree, read: _FolderRead) -> None:
    tree.folders.extend(node for node, _path in read.subfolders)
    tree.errors.extend(read.errors)
    tree.files += read.files
    tree.size += read.size


def _walk(tree: _Tree, native: NTFSReader, options: ScanOptions,
          progress: ProgressCallback | None, interval: float) -> None:
    pending, last = [(tree.root, tree.root.name)], time.monotonic()
    boundaries = MountSurvey(tree.root.name, cast(bytes, tree.root.snapshot), mount_points())
    while pending:
        tree.check()
        give_way()
        folder, path = pending.pop()
        read = _read(folder, path, native, tree, options, boundaries)
        pending.extend(read.subfolders)
        _merge_read(tree, read)
        if progress is not None and time.monotonic() - last >= interval:
            _notify(progress, ScanProgress(tree.files, len(tree.folders) - 1, tree.size, path))
            last = time.monotonic()
    native.verify()
    boundaries.verify(mount_points())


def build(root: Node, options: ScanOptions, *, progress: ProgressCallback | None = None,
          cancel: threading.Event | None = None, pause: threading.Event | None = None,
          interval: float = 0.1) -> ScanResult | None:
    """Stage an opt-in ACL-aware tree, returning None for unsupported/raw errors before publication.

    No elevation or privilege changes occur. Ordinary no-follow per-path metadata is mandatory;
    live raw names/parents/sequences/dates/sizes must agree before entering the same Node helpers.
    Allocation/owner/options retain ordinary rules. Raw reads are serial on this calling worker;
    workers is not a speed claim. Cancellation retains a sorted partial tree and closes own handles.
    Caller adopts only success/partial cancellation into its one published root; parse fallback
    discards the candidate. This audit implementation remains off by default pending native baselines.
    """
    if sys.platform != "win32":
        return None
    candidate = Node(root.name, True, children=[], error=NOT_SCANNED, snapshot=root.snapshot)
    tree = _Tree(candidate, cancel, pause, [candidate])
    started = time.monotonic()
    tree.check()
    try:
        with (anchored_directory(directory_stamps(root.name)), NTFSReader(root.name) as native,
              background_priority(options.gentle) as warnings):
            _walk(tree, native, options, progress, interval)
            _add_up(tree.folders)
            tree.check()
            accounting = account_hard_links(candidate, cancel=cancel) if options.count_hard_links else None
            tree.check()
    except _CallbackError as failure:
        raise failure.error from None
    except (OSError, ValueError) as error:
        _LOG.debug("Discarded experimental NTFS candidate: %s", str(error)[:2048])
        return None  # A discarded candidate supplies no coverage or operation authority.
    if progress is not None:
        progress(ScanProgress(tree.files, len(tree.folders) - 1, tree.size, root.name))
    return ScanResult(candidate, tree.errors, time.monotonic() - started, sorted(set(warnings)), accounting, "mft")
