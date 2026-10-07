"""No-follow, snapshot-checked copy and comparison streams, with exclusive destination creation."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import os
import stat
import sys
import threading
from typing import BinaryIO

from je_file_tree.core.compression_ops import _kernel, _pin
from je_file_tree.core.copy_platform import (
    copy_xattrs, mac_copy, mac_xattrs, windows_copy, windows_directory_times, windows_streams,
)
from je_file_tree.core.no_replace import anchored_directory, directory_stamps
from je_file_tree.core.mounts import descriptor_mount
from je_file_tree.core.snapshot import pack_snapshot, stable_snapshot, stat_snapshot, unpack_snapshot

HASH_LIMIT = 64 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
_UNAVAILABLE = 0x400 | 0x1000 | 0x40000 | 0x400000
_ORDINARY_MODE = 0o777
CopyVolume = tuple[int, int | None]


def copy_volume(descriptor: int | None, device: int) -> CopyVolume:
    """Capture the destination device and checked Linux mount ID; other POSIX mount IDs stay unknown."""
    return device, descriptor_mount(descriptor) if sys.platform.startswith("linux") else None


def check_volume(descriptor: int | None, volume: CopyVolume | None) -> None:
    """Reject another filesystem or Linux same-device bind at an anchored destination boundary."""
    if descriptor is not None and volume is not None:
        if os.fstat(descriptor).st_dev != volume[0]:
            raise ValueError("Unexpected destination filesystem boundary")
        if sys.platform.startswith("linux") and descriptor_mount(descriptor) != volume[1]:
            raise ValueError("Unexpected destination mount boundary")


def check_cancel(cancel: threading.Event | None) -> None:
    """Copy/verification cancellation preserves both the original and any partial destination."""
    if cancel is not None and cancel.is_set():
        raise InterruptedError("Copy/verification stopped; original preserved")


def check_file(path: str, expected: bytes) -> None:
    """Require the complete recorded regular-file metadata and no known unavailable/reparse state."""
    current = stat_snapshot(path)
    info = unpack_snapshot(current)
    if (not stat.S_ISREG(info.mode) or info.is_link or info.attributes & _UNAVAILABLE
            or not info.device or not info.inode or stable_snapshot(current) != stable_snapshot(expected)):
        raise ValueError("File changed, linked or unavailable")


@contextmanager
def opened_file(path: str, expected: bytes, *, volume: CopyVolume | None = None) -> Iterator[BinaryIO]:
    """Anchor parents, reject links, compare descriptor/path metadata before and after payload reads."""
    check_file(path, expected)
    with anchored_directory(directory_stamps(os.path.dirname(path))) as parent, _pinned_file(path):
        check_volume(parent, volume)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path if parent is None else os.path.basename(path), flags, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as stream:
            check_volume(stream.fileno(), volume)
            initial = pack_snapshot(os.fstat(stream.fileno()))
            _descriptor(expected, initial)
            check_file(path, expected)
            yield stream
            if stable_snapshot(pack_snapshot(os.fstat(stream.fileno()))) != stable_snapshot(initial):
                raise ValueError("Opened file changed during read")
            check_file(path, expected)


@contextmanager
def _pinned_file(path: str) -> Iterator[None]:
    if os.name == "nt":
        with _pin(_kernel(), path):
            yield
    else:
        yield


def _descriptor(expected: bytes, current: bytes) -> None:
    before, after = unpack_snapshot(expected), unpack_snapshot(current)
    comparable = replace(after, changed_ns=before.changed_ns) if os.name == "nt" else after
    if comparable != before:
        raise ValueError("Opened identity/metadata differs from reviewed file")


def _write(source: BinaryIO, target: BinaryIO, cancel: threading.Event | None) -> None:
    remaining = os.fstat(source.fileno()).st_size
    while True:
        check_cancel(cancel)
        block = source.read(min(CHUNK_BYTES, remaining + 1))
        if not block:
            break
        if len(block) > remaining:
            raise ValueError("Source grew during copy")
        target.write(block)
        remaining -= len(block)


def copy_file(path: str, target: str, expected: bytes, cancel: threading.Event | None,
               *, volume: CopyVolume | None = None) -> None:
    """Copy one ordinary file exclusively, preserve native metadata where supported and flush contents."""
    check_cancel(cancel)
    check_file(path, expected)
    with anchored_directory(directory_stamps(os.path.dirname(target))) as parent:
        check_volume(parent, volume)
        if os.name == "nt":
            with anchored_directory(directory_stamps(os.path.dirname(path))):
                windows_copy(path, target, cancel)
            check_file(path, expected)
        else:
            with opened_file(path, expected) as source:
                descriptor = os.open(os.path.basename(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=parent)
                with os.fdopen(descriptor, "wb") as output:
                    if sys.platform == "darwin":
                        mac_copy(source.fileno(), output.fileno(), cancel)
                    else:
                        _write(source, output, cancel)
                        output.flush()
                        copy_xattrs(source.fileno(), output.fileno())
                        info = os.fstat(source.fileno())
                        os.fchmod(output.fileno(), stat.S_IMODE(info.st_mode) & _ORDINARY_MODE)
                        os.utime(output.fileno(), ns=(info.st_atime_ns, info.st_mtime_ns))
                    output.flush()
                    os.fsync(output.fileno())
    check_cancel(cancel)


def _hash(stream: BinaryIO, cancel: threading.Event | None) -> bytes:
    digest = hashlib.sha256()
    before = pack_snapshot(os.fstat(stream.fileno()))
    remaining = unpack_snapshot(before).size
    while True:
        check_cancel(cancel)
        block = stream.read(min(CHUNK_BYTES, remaining + 1))
        if not block:
            break
        if len(block) > remaining:
            raise ValueError("Stream grew during comparison")
        digest.update(block)
        remaining -= len(block)
    if stable_snapshot(pack_snapshot(os.fstat(stream.fileno()))) != stable_snapshot(before):
        raise ValueError("Stream metadata changed during comparison")
    return digest.digest()


def compare_file(path: str, target: str, expected: bytes, cancel: threading.Event | None,
                  *, volume: CopyVolume | None = None) -> None:
    """Compare recorded lengths and hash every main stream smaller than 64 MiB; verify Windows ADS too."""
    check_cancel(cancel)
    with anchored_directory(directory_stamps(os.path.dirname(target))) as parent:
        check_volume(parent, volume)
    check_file(path, expected)
    destination = stat_snapshot(target)
    check_file(target, destination)
    size = unpack_snapshot(expected).size
    if unpack_snapshot(destination).size != size:
        raise ValueError("Copied file length differs")
    if size < HASH_LIMIT:
        with opened_file(path, expected) as source, opened_file(target, destination, volume=volume) as copied:
            if _hash(source, cancel) != _hash(copied, cancel):
                raise ValueError("Copied file hash differs")
    if os.name != "nt":
        with opened_file(path, expected) as source, opened_file(target, destination, volume=volume) as copied:
            compare_metadata(source.fileno(), copied.fileno())
    if os.name == "nt":
        _compare_streams(path, target, expected, destination, cancel)
    check_file(path, expected)
    check_file(target, destination)


def _compare_streams(path: str, target: str, expected: bytes, destination: bytes,
                     cancel: threading.Event | None) -> None:
    with (anchored_directory(directory_stamps(os.path.dirname(path))),
          anchored_directory(directory_stamps(os.path.dirname(target))), _pinned_file(path), _pinned_file(target)):
        streams = windows_streams(path)
        if streams != windows_streams(target):
            raise ValueError("Windows data-stream names/lengths differ")
        for name, size in streams:
            if name == "::$DATA" or size >= HASH_LIMIT:
                continue
            check_cancel(cancel)
            with open(path + name, "rb") as source, open(target + name, "rb") as copied:
                if _hash(source, cancel) != _hash(copied, cancel):
                    raise ValueError("Windows alternate data-stream hash differs")
        check_file(path, expected)
        check_file(target, destination)


def copy_directory_metadata(path: str, target: str, cancel: threading.Event | None,
                             *, volume: CopyVolume | None = None) -> None:
    """Apply directory metadata after children; strictly copy POSIX xattrs, never follow directory links."""
    check_cancel(cancel)
    with (anchored_directory(directory_stamps(path)) as source,
          anchored_directory(directory_stamps(target)) as destination):
        check_volume(destination, volume)
        if os.name == "nt":
            info = os.lstat(path)
            windows_directory_times(target, info.st_atime_ns, info.st_mtime_ns)
        elif sys.platform == "darwin":
            mac_copy(source, destination, cancel, metadata=True)
        else:
            info = os.fstat(source)
            copy_xattrs(source, destination)
            os.fchmod(destination, stat.S_IMODE(info.st_mode) & _ORDINARY_MODE)
            os.utime(destination, ns=(info.st_atime_ns, info.st_mtime_ns))


def compare_metadata(source: int, target: int) -> None:
    """Compare POSIX extended attributes strictly; large macOS resource forks are explicitly length-only."""
    if sys.platform == "darwin":
        if mac_xattrs(source, HASH_LIMIT) != mac_xattrs(target, HASH_LIMIT):
            raise ValueError("Native extended attributes/resource forks differ")
    elif hasattr(os, "listxattr"):
        names = sorted(os.listxattr(source))
        if names != sorted(os.listxattr(target)):
            raise ValueError("Extended attribute names differ")
        for name in names:
            if os.getxattr(source, name) != os.getxattr(target, name):
                raise ValueError("Extended attribute contents differ")
