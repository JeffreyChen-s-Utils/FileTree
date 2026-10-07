"""Scoped captured duplicate-backup retirement and cleanup of newly owned temporary aliases."""

from collections.abc import Iterator
from contextlib import contextmanager
import ctypes
from dataclasses import replace
import os
import re
import threading
from typing import BinaryIO

from je_file_tree.core.compression_ops import _kernel
from je_file_tree.core.copy_io import _descriptor, check_cancel, check_file, check_volume, opened_file
from je_file_tree.core.duplicate_links import LinkPair, _attributes, _digests, _streams
from je_file_tree.core.no_replace import anchored_directory
from je_file_tree.core.snapshot import pack_snapshot, stable_snapshot, unpack_snapshot

if os.name == "nt":
    import msvcrt

_OWNED = re.compile(r"\.filetree-(?:link-[0-9a-f]{32}\.tmp|copy-[0-9a-f]{32}\.bak)\Z")
_MIN_ALIAS_NAMES = 2


@contextmanager
def _windows_stream(path: str, *, deleting: bool = False) -> Iterator[BinaryIO]:
    kernel = _kernel()
    handle = kernel.CreateFileW(path, 0x80000000 | (0x10000 if deleting else 0),
                                1 if deleting else 5, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except OSError:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "rb") as stream:
        yield stream  # The CRT descriptor owns and closes the native handle, including on exceptions.


@contextmanager
def _named_read(path: str, mode: str) -> Iterator[BinaryIO]:
    if mode != "rb" or os.name != "nt":
        raise ValueError("Native named-stream reads require Windows read-only mode")
    with _windows_stream(path) as stream:
        yield stream


@contextmanager
def _retiring(path: str, expected: bytes, parent: int | None) -> Iterator[BinaryIO]:
    if not _OWNED.fullmatch(os.path.basename(path)):
        raise ValueError("Only a captured operation-owned duplicate artifact may be retired")
    check_file(path, expected)
    if os.name == "nt":
        with _windows_stream(path, deleting=True) as stream:
            _descriptor(expected, pack_snapshot(os.fstat(stream.fileno())))
            check_file(path, expected)
            yield stream
    else:
        if parent is None:
            raise ValueError("Owned artifact retirement requires an anchored POSIX parent")
        descriptor = os.open(os.path.basename(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as stream:
            _descriptor(expected, pack_snapshot(os.fstat(stream.fileno())))
            check_file(path, expected)
            yield stream


def _retire(stream: BinaryIO, path: str, expected: bytes, parent: int | None) -> None:
    _descriptor(expected, pack_snapshot(os.fstat(stream.fileno())))
    check_file(path, expected)
    if os.name == "nt":
        kernel = _kernel()
        kernel.SetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.c_int32,
                                                     ctypes.c_void_p, ctypes.c_uint32]
        kernel.SetFileInformationByHandle.restype = ctypes.c_int32
        disposition = ctypes.c_ubyte(1)  # FILE_DISPOSITION_INFO has one BOOLEAN; FileDispositionInfo = 4.
        handle = msvcrt.get_osfhandle(stream.fileno())
        if not kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.unlink(os.path.basename(path), dir_fd=parent)


def _remove_alias(pair: LinkPair, path: str, expected: bytes) -> None:
    _artifact(pair, path, "link")
    if unpack_snapshot(expected).links < _MIN_ALIAS_NAMES:
        raise ValueError("Temporary alias may be the last name; retained rather than deleted")
    check_file(pair.keeper_path, expected)
    with anchored_directory(pair.copy_parents) as parent, _retiring(path, expected, parent) as stream:
        check_volume(parent, pair.volume)
        _retire(stream, path, expected, parent)
    if os.path.lexists(path):
        raise OSError("Native temporary-alias cleanup is unconfirmed; retained path: " + path)


def _retire_backup(pair: LinkPair, backup: str, expected: bytes, keeper: bytes,
                   cancel: threading.Event | None) -> None:
    _artifact(pair, backup, "copy")
    original, observed = unpack_snapshot(pair.copy_snapshot), unpack_snapshot(expected)
    if replace(observed, changed_ns=original.changed_ns) != original:
        raise ValueError("Backup differs from the captured extra-copy identity/metadata")
    with (anchored_directory(pair.copy_parents) as parent,
          opened_file(pair.keeper_path, keeper, volume=pair.volume) as source,
          _retiring(backup, expected, parent) as old):
        check_volume(parent, pair.volume)
        before = pack_snapshot(os.fstat(old.fileno()))
        digest, original, size = _digests(source, cancel)
        other, original_other, length = _digests(old, cancel)
        if digest != other or original != pair.digest or original_other != pair.digest or size != length:
            raise ValueError("Captured backup differs from the kept full payload; backup retained")
        _attributes(source.fileno(), old.fileno())
        if os.name == "nt":
            _streams(replace(pair, copy_path=backup), cancel, opener=_named_read)
        if stable_snapshot(pack_snapshot(os.fstat(old.fileno()))) != stable_snapshot(before):
            raise ValueError("Captured backup changed during final retirement verification")
        check_cancel(cancel)
        check_file(pair.copy_path, keeper)
        _retire(old, backup, expected, parent)
    if os.path.lexists(backup):
        raise OSError("Native old-copy retirement is unconfirmed; retained path: " + backup)


def _artifact(pair: LinkPair, path: str, kind: str) -> None:
    if (not pair.copy_parents or os.path.dirname(path) != pair.copy_parents[-1].path
            or not _OWNED.fullmatch(os.path.basename(path))
            or not os.path.basename(path).startswith(".filetree-" + kind + "-")):
        raise ValueError("Retirement requires the captured operation artifact in its approved parent")
