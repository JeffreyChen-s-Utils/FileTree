"""FreeBSD statfs version, bounds, literal paths and pinned descriptor identity are checked."""

import ctypes

import pytest

from je_file_tree.core import freebsd_mounts as native


def test_native_table_preserves_literals_and_checks_abi(monkeypatch):
    points = (b"/", "/private/owned/卷 空白\\literal".encode())
    assert ctypes.sizeof(native._StatFS) == 2344

    def call(table, size, flags):
        assert flags == 2
        if table is not None:
            assert size == ctypes.sizeof(table)
            for index, point in enumerate(points):
                table[index].version = native._VERSION
                table[index].mounted_on = point
        return len(points)

    monkeypatch.setattr(native, "_function", lambda name: call)
    assert native.mount_points() == frozenset({"/", "/private/owned/卷 空白\\literal"})


@pytest.mark.parametrize("count", [-1, 0, 4096, 1000000])
def test_unknown_or_unbounded_table_refuses(count, monkeypatch):
    monkeypatch.setattr(native, "_function", lambda name: lambda table, size, flags: count)
    with pytest.raises(OSError, match="unavailable or exceeds"):
        native.mount_points()


def test_changing_table_is_not_complete(monkeypatch):
    monkeypatch.setattr(native, "_function", lambda name: lambda table, size, flags: 1 if table is None else 2)
    with pytest.raises(OSError, match="changed"):
        native.mount_points()


@pytest.mark.parametrize("path", [b"relative", b"", b"/" + b"x" * 1023])
def test_invalid_or_unterminated_path_refuses(path):
    table = (native._StatFS * 1)()
    table[0].version, table[0].mounted_on = native._VERSION, path
    with pytest.raises(OSError, match="Invalid"):
        native._points(table, 1)


def test_obsolete_native_version_refuses():
    table = (native._StatFS * 1)()
    table[0].version, table[0].mounted_on = 0x20030518, b"/"
    with pytest.raises(OSError, match="version"):
        native._points(table, 1)


@pytest.mark.parametrize("version", [native._VERSION, 0x20030518])
def test_descriptor_identity_checks_version(version, monkeypatch):
    def call(fd, pointer):
        assert fd == 123
        info = ctypes.cast(pointer, ctypes.POINTER(native._StatFS)).contents
        info.version, info.fsid[0], info.fsid[1] = version, 17, 19
        return 0

    monkeypatch.setattr(native, "_function", lambda name: call)
    if version == native._VERSION:
        assert native.descriptor_mount(123) == (17, 19)
    else:
        with pytest.raises(OSError, match="version"):
            native.descriptor_mount(123)


def test_missing_descriptor_id_and_query_failure_refuse(monkeypatch):
    def empty(_fd, pointer):
        ctypes.cast(pointer, ctypes.POINTER(native._StatFS)).contents.version = native._VERSION
        return 0

    monkeypatch.setattr(native, "_function", lambda name: empty)
    with pytest.raises(OSError, match="unknown"):
        native.descriptor_mount(123)
    monkeypatch.setattr(native, "_function", lambda name: lambda fd, pointer: -1)
    with pytest.raises(OSError, match="unavailable"):
        native.descriptor_mount(123)
