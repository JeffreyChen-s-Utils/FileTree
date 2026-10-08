"""Bounded native mount-table buffers refuse unknown/truncated paths and unknown descriptor identities."""

import ctypes

import pytest

from je_file_tree.core import darwin_mounts as native


def test_native_table_uses_modern_abi_and_preserves_literal_paths(monkeypatch):
    points = (b"/", "/private/owned/卷 空白\\literal".encode())
    assert ctypes.sizeof(native._StatFS) == 2168

    def call(table, size, flags):
        assert flags == 2
        if table is not None:
            assert size == ctypes.sizeof(table)
            for index, point in enumerate(points):
                table[index].mounted_on = point
        return len(points)

    monkeypatch.setattr(native, "_function", lambda name: call)
    assert native.mount_points() == frozenset({"/", "/private/owned/卷 空白\\literal"})


@pytest.mark.parametrize("count", [-1, 0, 4096, 1000000])
def test_unknown_or_unbounded_table_never_allocates_a_buffer(count, monkeypatch):
    monkeypatch.setattr(native, "_function", lambda name: lambda table, size, flags: count)
    with pytest.raises(OSError, match="unavailable or exceeds"):
        native.mount_points()


def test_mount_table_truncation_never_returns_a_complete_boundary_set(monkeypatch):
    def call(table, _size, _flags):
        return 1 if table is None else 2

    monkeypatch.setattr(native, "_function", lambda name: call)
    with pytest.raises(OSError, match="changed"):
        native.mount_points()


@pytest.mark.parametrize("path", [b"relative", b"", b"/" + b"x" * 1023])
def test_invalid_or_unterminated_native_path_is_not_a_mount(path):
    table = (native._StatFS * 1)()
    table[0].mounted_on = path
    with pytest.raises(OSError, match="Invalid"):
        native._points(table, 1)


def test_native_descriptor_id_comes_from_pinned_descriptor_and_rejects_missing_data(monkeypatch):
    def call(fd, pointer):
        assert fd == 123
        info = ctypes.cast(pointer, ctypes.POINTER(native._StatFS)).contents
        info.fsid[0], info.fsid[1] = 17, 19
        return 0

    monkeypatch.setattr(native, "_function", lambda name: call)
    assert native.descriptor_mount(123) == (17, 19)
    monkeypatch.setattr(native, "_function", lambda name: lambda _fd, _pointer: 0)
    with pytest.raises(OSError, match="unknown"):
        native.descriptor_mount(123)


def test_failed_native_descriptor_query_is_visible(monkeypatch):
    monkeypatch.setattr(native, "_function", lambda name: lambda _fd, _pointer: -1)
    with pytest.raises(OSError, match="unavailable"):
        native.descriptor_mount(123)
