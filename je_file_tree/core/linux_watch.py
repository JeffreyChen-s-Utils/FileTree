"""One inotify descriptor with anchored ordinary-directory watches and explicit loss reporting."""

from collections.abc import Callable
import ctypes
import os
import select
import stat
import struct
import threading

from je_file_tree.core.change_watch import ChangeBatch, POLL_SECONDS, WatchFile, WatchFolder, changed, check_folder
from je_file_tree.core.mounts import descriptor_mount
from je_file_tree.core.no_replace import anchored_directory, directory_stamps
from je_file_tree.core.pacing import give_way

_HEADER = struct.Struct("iIII")
_BUFFER = 65536
_EVENTS = 0x2 | 0x4 | 0x8 | 0x40 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800
_ONLY_DIRECTORY = 0x01000000
_LOST = 0x400 | 0x800 | 0x2000 | 0x4000 | 0x8000


def parse_inotify(payload: bytes, folders: dict[int, tuple[str, ...]]) -> ChangeBatch:
    """Validate bounded records; scope loss/overflow or an unknown watch requires a full rescan."""
    if len(payload) > _BUFFER:
        raise ValueError("Oversized inotify buffer")
    offset, paths = 0, set()
    while offset < len(payload):
        if len(payload) - offset < _HEADER.size:
            raise ValueError("Truncated inotify record")
        descriptor, mask, _cookie, length = _HEADER.unpack_from(payload, offset)
        end = offset + _HEADER.size + length
        if length % 4 or end > len(payload):
            raise ValueError("Invalid inotify record length")
        if mask & _LOST or descriptor not in folders:
            return changed(set(), full=True, reason="notification_lost")
        paths.update(folders[descriptor])
        offset = end
    return changed(paths)


def _register(library, descriptor: int, folders: tuple[WatchFolder, ...],
              cancel: threading.Event) -> dict[int, tuple[str, ...]]:
    result, root_mount = {}, None
    for folder in folders:
        if cancel.is_set():
            return result
        give_way()
        check_folder(folder)
        with anchored_directory(directory_stamps(folder.path)) as opened:
            if opened is None:
                raise ValueError("inotify requires anchored native directory descriptors")
            info = os.fstat(opened)
            actual_mount = descriptor_mount(opened)
            if root_mount is None:
                root_mount = actual_mount
            if ((info.st_dev, info.st_ino) != (folder.device, folder.inode) or actual_mount != root_mount):
                raise ValueError("Watched directory identity/mount changed")
            # The controlled proc descriptor link refers to this open, no-follow checked folder,
            # not an arbitrary user symlink. Kernel registration completes before descriptor close.
            key = library.inotify_add_watch(descriptor, os.fsencode(f"/proc/self/fd/{opened}"),
                                            _EVENTS | _ONLY_DIRECTORY)
            if key < 0:
                raise OSError(ctypes.get_errno(), "inotify folder registration failed")
            if key in result and result[key] != (folder.path,):
                raise ValueError("inotify directory aliases require a fresh scope review")
            result[key] = (folder.path,)
    return result


def _shared_watches(library, descriptor: int, files: tuple[WatchFile, ...], cancel: threading.Event) -> dict:
    result = {}
    for file in files:
        if cancel.is_set():
            return result
        with anchored_directory(directory_stamps(os.path.dirname(file.path))) as parent:
            opened = os.open(os.path.basename(file.path), os.O_PATH | os.O_NOFOLLOW, dir_fd=parent)
            try:
                info = os.fstat(opened)
                if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (file.device, file.inode):
                    raise ValueError("Shared watched file identity changed")
                if descriptor_mount(opened) != descriptor_mount(parent):
                    raise ValueError("Shared watched file crossed a mount boundary")
                key = library.inotify_add_watch(descriptor, os.fsencode(f"/proc/self/fd/{opened}"), _EVENTS)
                if key < 0:
                    raise OSError(ctypes.get_errno(), "inotify shared-file registration failed")
                result[key] = file.parents
            finally:
                os.close(opened)
    return result


def watch_linux(folders: tuple[WatchFolder, ...], on_change: Callable[[ChangeBatch], None],
                cancel: threading.Event, ready: Callable[[str], None] | None,
                shared: tuple[WatchFile, ...] = ()) -> None:
    """Cancel by bounded polling and close the single feed descriptor; no kernel settings are changed."""
    library = ctypes.CDLL(None, use_errno=True)
    library.inotify_init1.argtypes, library.inotify_init1.restype = [ctypes.c_int], ctypes.c_int
    library.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    library.inotify_add_watch.restype = ctypes.c_int
    descriptor = library.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    if descriptor < 0:
        raise OSError(ctypes.get_errno(), "inotify feed unavailable")
    try:
        scopes = _register(library, descriptor, folders, cancel)
        scopes.update(_shared_watches(library, descriptor, shared, cancel))
        if cancel.is_set():
            return
        if ready:
            ready("inotify")
        while not cancel.is_set():
            check_folder(folders[0])
            readable, _writes, _errors = select.select([descriptor], [], [], POLL_SECONDS)
            if not readable:
                continue
            try:
                payload = os.read(descriptor, _BUFFER)
            except BlockingIOError:
                continue
            if not payload:
                raise OSError("inotify feed closed unexpectedly")
            batch = parse_inotify(payload, scopes)
            if not cancel.is_set():
                on_change(batch)
            if batch.full:
                return  # caller must rebuild scopes from a fresh complete scan
    finally:
        os.close(descriptor)
