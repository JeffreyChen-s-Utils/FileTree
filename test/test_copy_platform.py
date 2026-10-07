"""Portable native-ABI doubles verify exclusive flags, stop semantics and state cleanup."""

from contextlib import nullcontext
import ctypes
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import copy_platform


def test_windows_copy_flags_and_stop_do_not_request_destination_deletion(monkeypatch):
    cancel = threading.Event()
    calls = []

    def copy(source, destination, callback, _data, _cancel, flags):
        calls.append((source, destination, flags))
        assert callback(10, 0, 10, 0, 1, 0, None, None, None) == 0
        cancel.set()
        assert callback(10, 1, 10, 1, 1, 0, None, None, None) == 2
        return 1

    monkeypatch.setattr(copy_platform, "_kernel", lambda: SimpleNamespace(CopyFileExW=copy))
    monkeypatch.setattr(copy_platform, "_pin", lambda *_args: nullcontext())
    monkeypatch.setattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, raising=False)
    copy_platform.windows_copy("source", "destination", cancel)
    assert calls == [("source", "destination", 0x801)]


@pytest.mark.parametrize("failure,metadata", [(False, False), (False, True), (True, False)])
def test_mac_descriptor_copy_flags_callbacks_and_cleanup(monkeypatch, failure, metadata):
    cancel = threading.Event()
    state_values, freed = {}, []

    def allocate():
        return 123

    def release(state):
        freed.append(state)
        return 0

    def configure(state, flag, callback):
        state_values.update(state=state, flag=flag, callback=callback)
        return 0

    def copy(source, destination, state, flags):
        assert (source, destination, state, flags) == (10, 20, 123, 7 if metadata else 15)
        callback = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                    ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p)(state_values["callback"].value)
        assert callback(4, 4, None, None, None, None) == 0
        cancel.set()
        assert callback(4, 4, None, None, None, None) == 2
        return -1 if failure else 0

    library = SimpleNamespace(copyfile_state_alloc=allocate, copyfile_state_free=release,
                              copyfile_state_set=configure, fcopyfile=copy)
    monkeypatch.setattr(ctypes, "CDLL", lambda *_args, **_kwargs: library)
    if failure:
        with pytest.raises(OSError, match="failed"):
            copy_platform.mac_copy(10, 20, cancel, metadata=metadata)
    else:
        copy_platform.mac_copy(10, 20, cancel, metadata=metadata)
    assert state_values["flag"] == 6 and freed == [123]


def test_missing_mac_native_metadata_interface_refuses_without_fallback(monkeypatch):
    monkeypatch.setattr(ctypes, "CDLL", lambda *_args, **_kwargs: object())
    with pytest.raises(OSError, match="unavailable"):
        copy_platform.mac_copy(10, 20, None)
    with pytest.raises(OSError, match="unavailable"):
        copy_platform.mac_xattrs(10, 100)


def test_mac_aggregate_attribute_cap_refuses_before_reading_excess_value(monkeypatch):
    reads = []

    def names(_fd, buffer, _size, _flags):
        value = b"first\0second\0"
        if buffer is not None:
            ctypes.memmove(buffer, value, len(value))
        return len(value)

    def attribute(_fd, name, buffer, size, _position, _flags):
        if buffer is not None:
            reads.append(name)
            ctypes.memmove(buffer, b"abcd", size)
        return 4

    library = SimpleNamespace(flistxattr=names, fgetxattr=attribute)
    monkeypatch.setattr(ctypes, "CDLL", lambda *_args, **_kwargs: library)
    with pytest.raises(ValueError, match="byte bound"):
        copy_platform.mac_xattrs(10, 10, total_limit=6)
    assert reads == [b"first"]
    reads.clear()
    assert copy_platform.mac_xattrs(10, 10) == ((b"first", 4, b"abcd"), (b"second", 4, b"abcd"))
    assert reads == [b"first", b"second"]
