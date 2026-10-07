"""Bounded current-user Recycle Bin Shell lookup and canonical undelete; no commands or script hosts."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import os
import threading
from typing import Any
import uuid

from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot
from je_file_tree.core.trash_restore import TrashOrigin, _unchanged

_LIMIT = 100_000
_IID_ITEM = "43826d1e-e718-42ee-bc55-a1e261c37bfe"
_IID_ITEM2 = "7e9fb0d3-919f-4307-ab2e-9b1860310c93"
_IID_ENUM = "70629033-e363-4a28-a567-0db78006e6d7"
_IID_MENU = "000214e4-0000-0000-c000-000000000046"
_RECYCLE = "b7534046-3ecb-4c18-be4e-64cd4cb7d6ac"
_ENUM = "94f60519-2850-4924-aa5a-d15e84868039"
_UI = "3981e225-f559-11d3-8e3a-00c04f6837d5"


class _Guid(ctypes.Structure):
    _fields_ = [("first", ctypes.c_uint32), ("second", ctypes.c_uint16), ("third", ctypes.c_uint16),
                ("last", ctypes.c_ubyte * 8)]


class _Key(ctypes.Structure):
    _fields_ = [("guid", _Guid), ("id", ctypes.c_uint32)]


class _Command(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint32), ("mask", ctypes.c_uint32), ("window", ctypes.c_void_p),
                ("verb", ctypes.c_char_p), ("parameters", ctypes.c_char_p), ("directory", ctypes.c_char_p),
                ("show", ctypes.c_int32), ("hotkey", ctypes.c_uint32), ("icon", ctypes.c_void_p)]


def _guid(value: str) -> _Guid:
    return _Guid.from_buffer_copy(uuid.UUID(value).bytes_le)


def _check(status: int) -> None:
    if status < 0:
        raise OSError(f"Recycle Bin Shell HRESULT 0x{status & 0xffffffff:08x}")


def _call(pointer: ctypes.c_void_p, slot: int, types: Sequence[Any], values: Sequence[Any]) -> int:
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    method = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, *types)(table[slot])
    return method(pointer, *values)


def _libraries() -> tuple[Any, Any, Any]:
    if os.name != "nt":
        raise ValueError("Recycle Bin Shell requires Windows")
    ole, shell, props = (ctypes.WinDLL(name) for name in ("ole32", "shell32", "propsys"))
    ole.CoInitializeEx.argtypes, ole.CoInitializeEx.restype = [ctypes.c_void_p, ctypes.c_uint32], ctypes.c_int32
    ole.CoUninitialize.argtypes, ole.CoUninitialize.restype = [], None
    ole.CoTaskMemFree.argtypes, ole.CoTaskMemFree.restype = [ctypes.c_void_p], None
    shell.SHGetKnownFolderItem.argtypes = [ctypes.POINTER(_Guid), ctypes.c_uint32, ctypes.c_void_p,
                                         ctypes.POINTER(_Guid), ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderItem.restype = ctypes.c_int32
    props.PSGetPropertyKeyFromName.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(_Key)]
    props.PSGetPropertyKeyFromName.restype = ctypes.c_int32
    return ole, shell, props


@contextmanager
def _owned(pointer: ctypes.c_void_p) -> Iterator[ctypes.c_void_p]:
    if not pointer:
        raise OSError("Recycle Bin Shell returned an empty interface")
    try:
        yield pointer
    finally:
        _call(pointer, 2, (), ())


def _bound(pointer: ctypes.c_void_p, handler: str, interface: str) -> ctypes.c_void_p:
    result = ctypes.c_void_p()
    _check(_call(pointer, 3, (ctypes.c_void_p, ctypes.POINTER(_Guid), ctypes.POINTER(_Guid),
                            ctypes.POINTER(ctypes.c_void_p)),
                 (None, ctypes.byref(_guid(handler)), ctypes.byref(_guid(interface)), ctypes.byref(result))))
    return result


def _text(pointer: ctypes.c_void_p, slot: int, parameter: Any, kind: Any, ole: Any) -> str:
    result = ctypes.c_void_p()
    try:
        _check(_call(pointer, slot, (kind, ctypes.POINTER(ctypes.c_void_p)), (parameter, ctypes.byref(result))))
        if not result:
            raise OSError("Recycle Bin Shell string is unavailable")
        return ctypes.wstring_at(result)
    finally:
        if result:
            ole.CoTaskMemFree(result)


def _property(pointer: ctypes.c_void_p, name: str, libraries: tuple[Any, Any, Any]) -> str:
    ole, _shell, props = libraries
    key, item2 = _Key(), ctypes.c_void_p()
    _check(props.PSGetPropertyKeyFromName(name, ctypes.byref(key)))
    _check(_call(pointer, 0, (ctypes.POINTER(_Guid), ctypes.POINTER(ctypes.c_void_p)),
                 (ctypes.byref(_guid(_IID_ITEM2)), ctypes.byref(item2))))
    with _owned(item2):
        return _text(item2, 17, ctypes.byref(key), ctypes.POINTER(_Key), ole)


def _matching(pointer: ctypes.c_void_p, origin: TrashOrigin, actual: str | None,
              libraries: tuple[Any, Any, Any]) -> str | None:
    path = _text(pointer, 5, 0x80058000, ctypes.c_uint32, libraries[0])  # SIGDN_FILESYSPATH
    if actual is not None and os.path.normcase(path) != os.path.normcase(actual):
        return None
    if not _unchanged(unpack_snapshot(origin.snapshot), unpack_snapshot(stat_snapshot(path))):
        return None
    name = _property(pointer, "System.ItemNameDisplay", libraries)
    directory = _property(pointer, "System.Recycle.DeletedFrom", libraries)
    if os.path.normcase(os.path.join(directory, name)) != os.path.normcase(origin.path):
        return None
    return path


@dataclass(frozen=True, slots=True)
class RecycleItem:
    """One exact source/identity-matched Shell item; its COM handle is valid only inside recycle_item."""

    handle: ctypes.c_void_p
    trashed: str
    source: str

    def undelete(self, *, window: int = 0) -> None:
        """Invoke only the canonical restore verb; request synchronous completion and leave OS UI unanswered.

        The caller must immediately recheck source/payload/parent/receipt observations. Windows may
        show its own collision/error question; this code never answers it or suppresses it. A return
        does not prove completion: the caller must observe the actual restored identity/location.
        """
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.CreatePopupMenu.argtypes, user.CreatePopupMenu.restype = [], ctypes.c_void_p
        user.DestroyMenu.argtypes, user.DestroyMenu.restype = [ctypes.c_void_p], ctypes.c_int32
        menu = user.CreatePopupMenu()
        if not menu:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            with _owned(_bound(self.handle, _UI, _IID_MENU)) as context:
                _check(_call(context, 3, (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                         ctypes.c_uint32, ctypes.c_uint32), (menu, 0, 1, 0x7fff, 0)))
                command = _Command(ctypes.sizeof(_Command), 0x100, window, b"undelete", None, None, 1, 0, None)
                _check(_call(context, 4, (ctypes.POINTER(_Command),), (ctypes.byref(command),)))
        finally:
            user.DestroyMenu(menu)


@contextmanager
def recycle_item(origin: TrashOrigin, *, actual: str | None = None,
                 cancel: threading.Event | None = None) -> Iterator[RecycleItem]:
    """Find the captured source/identity in the current user's Shell bin, bounded to 100k items.

    Metadata-only lookup, no payload reads/moves. STA initialization and all strings/interfaces are
    released on success, failure or cancellation. Unknown/ambiguous metadata never chooses by name
    alone. COM thread-mode/permission failures propagate; no scripts or ShellExecute fallback.
    """
    libraries = _libraries()
    ole, shell, _props = libraries
    _check(ole.CoInitializeEx(None, 2))
    selected = ctypes.c_void_p()
    selected_path = ""
    try:
        folder = ctypes.c_void_p()
        _check(shell.SHGetKnownFolderItem(ctypes.byref(_guid(_RECYCLE)), 0, None,
                                          ctypes.byref(_guid(_IID_ITEM)), ctypes.byref(folder)))
        with _owned(folder), _owned(_bound(folder, _ENUM, _IID_ENUM)) as iterator:
            for _ in range(_LIMIT):
                if cancel is not None and cancel.is_set():
                    raise ValueError("Recycle Bin lookup canceled")
                pointer, fetched = ctypes.c_void_p(), ctypes.c_uint32()
                status = _call(iterator, 3, (ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
                                           ctypes.POINTER(ctypes.c_uint32)), (1, ctypes.byref(pointer),
                                                                           ctypes.byref(fetched)))
                _check(status)
                if not pointer or not fetched.value:
                    if pointer:
                        _call(pointer, 2, (), ())
                    break
                with _owned(pointer):
                    path = _matching(pointer, origin, actual, libraries)
                    if path is not None:
                        if selected:
                            raise ValueError("Captured original has ambiguous Recycle Bin identities")
                        _call(pointer, 1, (), ())
                        selected, selected_path = ctypes.c_void_p(pointer.value), path
                        if actual is not None:
                            break
            else:
                raise ValueError("Recycle Bin lookup exceeded its item limit")
            if not selected:
                raise ValueError("Captured original was not found in the Recycle Bin")
            yield RecycleItem(selected, selected_path, origin.path)
    finally:
        if selected:
            _call(selected, 2, (), ())
        ole.CoUninitialize()
