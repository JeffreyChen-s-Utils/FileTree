"""Exclusive native file copies preserve platform metadata; Windows stream queries never read payloads."""

import ctypes
import errno
import os
import stat
import threading

from je_file_tree.core.compression_ops import _kernel, _pin

_PROGRESS_STOP = 2
_COPY_FAIL_EXISTS_AND_LINK = 1 | 0x800
_STREAM_NAME_LENGTH = 296
_STREAM_LIMIT = 1024
_HANDLE_EOF = 38
_MAC_ALL, _MAC_METADATA, _MAC_STATUS_CALLBACK = 15, 7, 6
_FILETIME_EPOCH_NS = 11_644_473_600 * 1_000_000_000
_FILETIME_INTERVAL_NS = 100
_ATTRIBUTE_NAMES_LIMIT = 64 * 1024
_VOLUME_PATH_LIMIT = 32768
_NAMED_STREAMS = 0x40000


class _StreamData(ctypes.Structure):
    _fields_ = [("size", ctypes.c_longlong), ("name", ctypes.c_wchar * _STREAM_NAME_LENGTH)]


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


def _filetime(nanoseconds: int) -> _FileTime:
    value = (nanoseconds + _FILETIME_EPOCH_NS) // _FILETIME_INTERVAL_NS
    if value < 0:
        raise ValueError("Timestamp predates native Windows epoch")
    return _FileTime(value & 0xFFFFFFFF, value >> 32)


def windows_directory_times(path: str, accessed_ns: int, modified_ns: int) -> None:
    """Set timestamps on a no-follow directory handle, including platforms without os.utime no-follow."""
    kernel = _kernel()
    kernel.SetFileTime.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.POINTER(_FileTime), ctypes.POINTER(_FileTime)]
    kernel.SetFileTime.restype = ctypes.c_int
    handle = kernel.CreateFileW(path, 0x100, 3, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        accessed, modified = _filetime(accessed_ns), _filetime(modified_ns)
        if not kernel.SetFileTime(handle, None, ctypes.byref(accessed), ctypes.byref(modified)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


def windows_streams(path: str) -> tuple[tuple[str, int], ...]:
    """Return bounded native data-stream names/sizes; unsupported/failed enumeration is never empty success."""
    if not _named_streams(path):
        info = os.lstat(path)
        return (("::$DATA", info.st_size),) if stat.S_ISREG(info.st_mode) else ()
    kernel = _kernel()
    kernel.FindFirstStreamW.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(_StreamData), ctypes.c_uint32]
    kernel.FindFirstStreamW.restype = ctypes.c_void_p
    kernel.FindNextStreamW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_StreamData)]
    kernel.FindNextStreamW.restype = ctypes.c_int
    kernel.FindClose.argtypes, kernel.FindClose.restype = [ctypes.c_void_p], ctypes.c_int
    data = _StreamData()
    handle = kernel.FindFirstStreamW(path, 0, ctypes.byref(data), 0)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error == _HANDLE_EOF:
            return ()
        raise ctypes.WinError(error)
    streams = []
    try:
        while True:
            name = data.name
            if (not name.startswith(":") or not name.endswith(":$DATA") or data.size < 0
                    or any(char in name[1:-len(":$DATA")] for char in ":/\\\0")):
                raise ValueError("Unrecognized Windows data stream")
            streams.append((name, data.size))
            if len(streams) > _STREAM_LIMIT:
                raise ValueError("Windows stream inventory exceeds limit")
            if not kernel.FindNextStreamW(handle, ctypes.byref(data)):
                error = ctypes.get_last_error()
                if error != _HANDLE_EOF:
                    raise ctypes.WinError(error)
                break
    finally:
        kernel.FindClose(handle)
    return tuple(sorted(streams))


def _named_streams(path: str) -> bool:
    kernel = _kernel()
    kernel.GetVolumePathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    kernel.GetVolumePathNameW.restype = ctypes.c_int
    kernel.GetVolumeInformationW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32,
                                            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
                                            ctypes.c_void_p, ctypes.c_uint32]
    kernel.GetVolumeInformationW.restype = ctypes.c_int
    root, flags = ctypes.create_unicode_buffer(_VOLUME_PATH_LIMIT), ctypes.c_uint32()
    if not kernel.GetVolumePathNameW(path, root, len(root)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.GetVolumeInformationW(root.value, None, 0, None, None, ctypes.byref(flags), None, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(flags.value & _NAMED_STREAMS)


def windows_copy(source: str, destination: str, cancel: threading.Event | None) -> None:
    """Native exclusive copy includes ADS; stopping retains the partial destination and never deletes source."""
    kernel = _kernel()
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_uint32, *([ctypes.c_longlong] * 4),
                                      ctypes.c_uint32, ctypes.c_uint32, *([ctypes.c_void_p] * 3))

    @callback_type
    def progress(*_values: object) -> int:
        return _PROGRESS_STOP if cancel is not None and cancel.is_set() else 0

    kernel.CopyFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, callback_type,
                                   ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    kernel.CopyFileExW.restype = ctypes.c_int
    with _pin(kernel, source):
        if not kernel.CopyFileExW(source, destination, progress, None, None, _COPY_FAIL_EXISTS_AND_LINK):
            raise ctypes.WinError(ctypes.get_last_error())


def mac_copy(source_fd: int, target_fd: int, cancel: threading.Event | None, *, metadata: bool = False) -> None:
    """Descriptor-only fcopyfile copies native metadata/resource forks; callbacks stop without unlinking."""
    library = ctypes.CDLL(None, use_errno=True)
    for symbol in ("copyfile_state_alloc", "copyfile_state_free", "copyfile_state_set", "fcopyfile"):
        if not hasattr(library, symbol):
            raise OSError(errno.ENOSYS, "Native metadata copy unavailable")
    library.copyfile_state_alloc.argtypes, library.copyfile_state_alloc.restype = [], ctypes.c_void_p
    library.copyfile_state_free.argtypes, library.copyfile_state_free.restype = [ctypes.c_void_p], ctypes.c_int
    library.copyfile_state_set.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    library.copyfile_state_set.restype = ctypes.c_int
    library.fcopyfile.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    library.fcopyfile.restype = ctypes.c_int
    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                     ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p)

    @callback_type
    def progress(*_values: object) -> int:
        return _PROGRESS_STOP if cancel is not None and cancel.is_set() else 0

    state = library.copyfile_state_alloc()
    if not state:
        raise OSError(errno.ENOMEM, "Native copy state unavailable")
    try:
        if library.copyfile_state_set(state, _MAC_STATUS_CALLBACK, ctypes.cast(progress, ctypes.c_void_p)):
            raise OSError(ctypes.get_errno(), "Native copy callback unavailable")
        flags = _MAC_METADATA if metadata else _MAC_ALL
        if library.fcopyfile(source_fd, target_fd, state, flags):
            raise OSError(ctypes.get_errno(), "Native copy failed or stopped")
    finally:
        library.copyfile_state_free(state)


def copy_xattrs(source_fd: int, target_fd: int) -> None:
    """Copy every readable POSIX extended attribute strictly; failure prevents original retirement."""
    if hasattr(os, "listxattr"):
        for name in os.listxattr(source_fd):
            os.setxattr(target_fd, name, os.getxattr(source_fd, name))


def mac_xattrs(descriptor: int, hash_limit: int) -> tuple[tuple[bytes, int, bytes | None], ...]:
    """Compare native attribute names/lengths and bounded values; large resource forks stay length-only."""
    library = ctypes.CDLL(None, use_errno=True)
    if not hasattr(library, "flistxattr") or not hasattr(library, "fgetxattr"):
        raise OSError(errno.ENOSYS, "Native attribute verification unavailable")
    library.flistxattr.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    library.flistxattr.restype = ctypes.c_ssize_t
    library.fgetxattr.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.c_uint32, ctypes.c_int]
    library.fgetxattr.restype = ctypes.c_ssize_t
    size = library.flistxattr(descriptor, None, 0, 0)
    if not 0 <= size <= _ATTRIBUTE_NAMES_LIMIT:
        raise OSError("Native attribute inventory failed or exceeds limit")
    names = ctypes.create_string_buffer(size)
    if library.flistxattr(descriptor, names, size, 0) != size:
        raise OSError("Native attribute names changed")
    result = []
    for name in sorted(names.raw.split(b"\0")):
        if not name:
            continue
        length = library.fgetxattr(descriptor, name, None, 0, 0, 0)
        if length < 0:
            raise OSError("Native attribute length unavailable")
        value = None
        if length < hash_limit:
            buffer = ctypes.create_string_buffer(length)
            if library.fgetxattr(descriptor, name, buffer, length, 0, 0) != length:
                raise OSError("Native attribute changed during verification")
            value = buffer.raw
        result.append((name, length, value))
    return tuple(result)
