"""Existing read-only USN journals, with one recursive overlapped notification handle as fallback."""

from collections.abc import Callable
import ctypes
import logging
import ntpath
import struct
import threading

from je_file_tree.core.change_watch import ChangeBatch, POLL_SECONDS, WatchFile, WatchFolder, changed, check_folder
from je_file_tree.core.compression_ops import _kernel
from je_file_tree.core.windows_allocation import _FileID, _Identity
from je_file_tree.core.windows_trash import _volume

_BUFFER = 32768
_NOTIFY = struct.Struct("III")
_USN = struct.Struct("<IHHQQqqIIIIHH")
_JOURNAL = struct.Struct("<QqqqqQQ")
_READ = struct.Struct("<qIIQQQ")
_QUERY_USN, _READ_USN = 0x900F4, 0x900BB
_PENDING, _CANCELED, _ENUM_LOST = 997, 995, 1022
_TIMEOUT, _WAIT_MS = 258, 250
_MAJOR_V2 = 2
_CURSOR_BYTES = 8
_HARD_LINK_CHANGE = 0x10000
_RENAME_DELETE = 0x200 | 0x1000 | 0x2000
_LOG = logging.getLogger(__name__)


class _Overlapped(ctypes.Structure):
    _fields_ = [("internal", ctypes.c_size_t), ("internal_high", ctypes.c_size_t),
                ("offset", ctypes.c_uint32), ("offset_high", ctypes.c_uint32), ("event", ctypes.c_void_p)]


def _parent(root: str, name: str, scopes: set[str]) -> str:
    if (not name or ntpath.isabs(name) or ntpath.splitdrive(name)[0] or "\0" in name
            or any(part in ("", ".", "..") for part in name.replace("/", "\\").split("\\"))):
        raise ValueError("Unsafe Windows notification name")
    parent = ntpath.dirname(ntpath.join(root, name))
    while parent not in scopes:
        next_parent = ntpath.dirname(parent)
        if parent in (next_parent, root):
            return root
        parent = next_parent
    return parent


def parse_notifications(payload: bytes, root: str, scopes: set[str]) -> ChangeBatch:
    """Validate native chained records and map names only to already captured folder parents."""
    if not payload:
        return changed(set(), full=True, reason="notification_lost")
    if len(payload) > _BUFFER:
        raise ValueError("Oversized Windows notification buffer")
    offset, paths = 0, set()
    while offset < len(payload):
        if len(payload) - offset < _NOTIFY.size:
            raise ValueError("Truncated Windows notification")
        next_offset, action, length = _NOTIFY.unpack_from(payload, offset)
        end = offset + _NOTIFY.size + length
        if action not in (1, 2, 3, 4, 5) or length % 2 or not length or end > len(payload):
            raise ValueError("Invalid Windows notification record")
        name = payload[offset + _NOTIFY.size:end].decode("utf-16-le")
        paths.add(_parent(root, name, scopes))
        if not next_offset:
            return changed(paths)
        if next_offset % 4 or next_offset < _NOTIFY.size + length or offset + next_offset >= len(payload):
            raise ValueError("Invalid Windows notification offset")
        offset += next_offset
    raise ValueError("Unterminated Windows notification chain")


def parse_usn(payload: bytes, scopes: dict[int, str], root: str, start: int,
              shared: dict[int, tuple[str, ...]] | None = None) -> tuple[int, ChangeBatch]:
    """Accept bounded V2 records/cursors; unknown volume parents are outside the captured map."""
    if not _CURSOR_BYTES <= len(payload) <= _BUFFER:
        raise ValueError("Invalid USN reply size")
    next_usn, = struct.unpack_from("<q", payload)
    if next_usn < start:
        raise ValueError("USN cursor moved backwards")
    offset, paths = _CURSOR_BYTES, set()
    while offset < len(payload):
        if len(payload) - offset < _USN.size:
            raise ValueError("Truncated USN record")
        size, major, _minor, inode, parent, usn, _time, reason, _source, _security, attributes, length, name_at = (
            _USN.unpack_from(payload, offset))
        if (major != _MAJOR_V2 or size < _USN.size or size % 8 or offset + size > len(payload)
                or not start <= usn < next_usn or length % 2 or not length or name_at < _USN.size
                or name_at + length > size):
            raise ValueError("Unsupported or corrupt USN record")
        name = payload[offset + name_at:offset + name_at + length].decode("utf-16-le")
        if "\0" in name or "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError("Invalid USN filename")
        if reason & _HARD_LINK_CHANGE:
            return next_usn, changed(set(), full=True, reason="hard_links_changed")
        if parent in scopes:
            paths.add(scopes[parent])
        if shared is not None and inode in shared:
            paths.update(shared[inode])
        if inode in scopes and attributes & 0x10:
            path = scopes[inode]
            if path == root and reason & _RENAME_DELETE:
                return next_usn, changed(set(), full=True, reason="root_changed")
            paths.add(ntpath.dirname(path) if reason & _RENAME_DELETE else path)
        offset += size
    return next_usn, changed(paths)


def _apis():
    kernel = _kernel()
    kernel.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                       ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    kernel.DeviceIoControl.restype = ctypes.c_int
    kernel.GetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Identity)]
    kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateEventW.restype = ctypes.c_void_p
    kernel.ReadDirectoryChangesW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                            ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p,
                                            ctypes.POINTER(_Overlapped), ctypes.c_void_p]
    kernel.ReadDirectoryChangesW.restype = ctypes.c_int
    kernel.GetOverlappedResult.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Overlapped), ctypes.c_void_p, ctypes.c_int]
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    kernel.CancelIoEx.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Overlapped)]
    kernel.ResetEvent.argtypes = [ctypes.c_void_p]
    return kernel


def _control(kernel, handle, code: int, data: bytes = b"") -> bytes:
    output, length = ctypes.create_string_buffer(_BUFFER), ctypes.c_uint32()
    request = ctypes.create_string_buffer(data) if data else None
    if not kernel.DeviceIoControl(handle, code, request, len(data), output, len(output), ctypes.byref(length), None):
        raise ctypes.WinError(ctypes.get_last_error())
    return output.raw[:length.value]


def _journal(kernel, handle) -> tuple[int, int, int]:
    data = _control(kernel, handle, _QUERY_USN)
    if len(data) < _JOURNAL.size:
        raise ValueError("Incomplete USN journal metadata")
    identifier, first, next_usn, lowest, _max, _capacity, _delta = _JOURNAL.unpack_from(data)
    if not identifier or min(first, next_usn, lowest) < 0 or next_usn < max(first, lowest):
        raise ValueError("Invalid USN journal metadata")
    return identifier, max(first, lowest), next_usn


def _watch_usn(kernel, folders, on_change, cancel, ready, shared) -> None:
    root, identifier = _volume(folders[0].path)
    scopes = {folder.inode: folder.path for folder in folders}
    aliases = {file.inode: file.parents for file in shared}
    if any(item.inode >= 1 << 64 for group in (folders, shared) for item in group):
        raise ValueError("USN V2 folder IDs unavailable")
    handle = kernel.CreateFileW("\\\\?\\Volume" + identifier, 0x80000000, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        journal, _first, cursor = _journal(kernel, handle)
        if ready:
            ready("usn")
        while not cancel.is_set():
            check_folder(folders[0])
            if _volume(folders[0].path) != (root, identifier):
                raise ValueError("Watched NTFS volume changed")
            current, first, next_usn = _journal(kernel, handle)
            if current != journal or not first <= cursor <= next_usn:
                on_change(changed(set(), full=True, reason="journal_changed"))
                return
            payload = _control(kernel, handle, _READ_USN, _READ.pack(cursor, 0xFFFFFFFF, 0, 0, 0, journal))
            cursor, batch = parse_usn(payload, scopes, folders[0].path, cursor, aliases)
            if (batch.folders or batch.full) and not cancel.is_set():
                on_change(batch)
            if batch.full or cancel.wait(POLL_SECONDS):
                return
    finally:
        kernel.CloseHandle(handle)


def _checked_handle(kernel, folder: WatchFolder):
    check_folder(folder)
    handle = kernel.CreateFileW(folder.path, 1, 7, None, 3, 0x42200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        identity, file_id = _Identity(), _FileID()
        if (not kernel.GetFileInformationByHandle(handle, ctypes.byref(identity))
                or not kernel.GetFileInformationByHandleEx(handle, 18, ctypes.byref(file_id), ctypes.sizeof(file_id))):
            raise ctypes.WinError(ctypes.get_last_error())
        legacy = (identity.device, (identity.inode_high << 32) | identity.inode_low)
        extended = (file_id.device, int.from_bytes(file_id.inode, "little"))
        if (not identity.attributes & 0x10 or identity.attributes & 0x400
                or (folder.device, folder.inode) not in (legacy, extended)):
            raise ValueError("Notification handle differs from captured ordinary folder")
        check_folder(folder)
        return handle
    except (OSError, ValueError):
        kernel.CloseHandle(handle)
        raise


def _completion(kernel, handle, overlap: _Overlapped, cancel: threading.Event) -> int:
    length = ctypes.c_uint32()
    while not cancel.is_set():
        state = kernel.WaitForSingleObject(overlap.event, _WAIT_MS)
        if state == _TIMEOUT:
            continue
        if state != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.GetOverlappedResult(handle, ctypes.byref(overlap), ctypes.byref(length), False):
            raise ctypes.WinError(ctypes.get_last_error())
        return length.value
    return 0


def _notification(kernel, handle, overlap: _Overlapped, cancel: threading.Event,
                  armed: Callable[[], None] | None = None) -> bytes:
    buffer = ctypes.create_string_buffer(_BUFFER)
    kernel.ResetEvent(overlap.event)
    if (not kernel.ReadDirectoryChangesW(handle, buffer, len(buffer), True, 0x15F, None, ctypes.byref(overlap), None)
            and ctypes.get_last_error() != _PENDING):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if armed:
            armed()
        length = _completion(kernel, handle, overlap, cancel)
        return buffer.raw[:length]
    finally:
        # Buffer/OVERLAPPED storage must remain alive until kernel I/O has actually completed.
        kernel.CancelIoEx(handle, ctypes.byref(overlap))
        remaining = ctypes.c_uint32()
        if not kernel.GetOverlappedResult(handle, ctypes.byref(overlap), ctypes.byref(remaining), True):
            error = ctypes.get_last_error()
            if error not in (_CANCELED, _ENUM_LOST):
                raise ctypes.WinError(error)


def _watch_notifications(kernel, folders, on_change, cancel, ready) -> None:
    handle = _checked_handle(kernel, folders[0])
    event = kernel.CreateEventW(None, True, False, None)
    if not event:
        kernel.CloseHandle(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        overlap = _Overlapped(event=event)
        scopes = {folder.path for folder in folders}
        first = True
        while not cancel.is_set():
            check_folder(folders[0])
            try:
                armed = (lambda: ready("directory_changes")) if first and ready else None
                payload = _notification(kernel, handle, overlap, cancel, armed)
                first = False
                batch = parse_notifications(payload, folders[0].path, scopes)
            except OSError as error:
                if error.winerror != _ENUM_LOST:
                    raise
                batch = changed(set(), full=True, reason="notification_lost")
            if not cancel.is_set():
                on_change(batch)
            if batch.full:
                return
    finally:
        kernel.CloseHandle(event)
        kernel.CloseHandle(handle)


def watch_windows(folders: tuple[WatchFolder, ...], on_change: Callable[[ChangeBatch], None],
                  cancel: threading.Event, ready: Callable[[str], None] | None,
                  shared: tuple[WatchFile, ...] = ()) -> None:
    """Use an existing journal when accessible; fallback is native, recursive, read-only and cancelable."""
    kernel = _apis()
    announced = False

    def initialized(backend: str) -> None:
        nonlocal announced
        announced = True
        if ready:
            ready(backend)

    try:
        _watch_usn(kernel, folders, on_change, cancel, initialized, shared)
    except (OSError, ValueError, UnicodeError) as error:
        _LOG.debug("USN feed unavailable; using recursive notifications: %s", error)
        if not cancel.is_set():
            if announced:
                on_change(changed(set(), full=True, reason="backend_changed"))
            if shared and _volume(folders[0].path)[0] != folders[0].path:
                raise ValueError("External hard-link changes require an accessible USN journal") from error
            _watch_notifications(kernel, folders, on_change, cancel, ready)
