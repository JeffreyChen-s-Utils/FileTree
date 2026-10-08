"""Bounded metadata I/O and extension identities fail closed without requiring a raw host volume."""

from collections import OrderedDict
import ctypes
from dataclasses import replace
import struct
from types import SimpleNamespace

import pytest

from je_file_tree.core import mft, mft_reader as reader
from test_mft import _list_entry, _nonresident, _record, _resident


def _geometry(**changes):
    fields = [123, 8192, 1024, 512, 0, 512, 4096, 1024, 4, 32768, 8, 16, 0, 0]
    names = ("serial", "sectors", "clusters", "free", "reserved", "sector", "cluster", "record",
             "per_cluster", "size", "lcn", "mirror", "zone_start", "zone_end")
    for key, value in changes.items():
        fields[names.index(key)] = value
    return reader._VOLUME_DATA.pack(*fields) + reader._EXTENDED.pack(8, 3, 1)


def _reader():
    value = object.__new__(reader.NTFSReader)
    value.geometry = reader.parse_volume_data(_geometry())
    value.handle = 9
    value._cache = OrderedDict()
    value.runs = (mft.Run(0, 8, 8),)
    return value


def test_volume_geometry_keeps_native_serial_and_initialized_bounds():
    assert reader.parse_volume_data(_geometry()) == reader.VolumeData(123, 512, 4096, 1024, 32768, 8, 1024)


@pytest.mark.parametrize("changes", [dict(sector=511), dict(cluster=512, sector=4096), dict(record=768),
                                      dict(sectors=1), dict(clusters=0), dict(free=-1), dict(reserved=1025),
                                      dict(lcn=1024), dict(size=1024), dict(size=32769), dict(size=1 << 32)])
def test_invalid_volume_geometry_refuses(changes):
    with pytest.raises(mft.MFTParseError):
        reader.parse_volume_data(_geometry(**changes))


@pytest.mark.parametrize("suffix", [b"", struct.pack("<IHH", 9, 3, 1), struct.pack("<IHH", 8, 3, 0),
                                     struct.pack("<IHH", 7, 3, 1)])
def test_incomplete_or_unsupported_extended_geometry_refuses(suffix):
    with pytest.raises(mft.MFTParseError):
        reader.parse_volume_data(_geometry()[:96] + suffix)


def test_admin_refusal_happens_before_any_volume_mapping(monkeypatch):
    monkeypatch.setattr(reader, "_administrator", lambda: False)
    monkeypatch.setattr(reader, "_volume", lambda _path: pytest.fail("must not access a volume"))
    with pytest.raises(PermissionError):
        reader.NTFSReader("C:\\")


def test_unbuffered_read_aligns_offset_length_and_memory(monkeypatch):
    value = _reader()
    value.geometry = replace(value.geometry, sector=4096)
    calls = []

    def pointer(handle, offset, _position, method):
        calls.append((handle, offset, method))
        return 1

    def read(handle, address, count, returned, _overlapped):
        assert handle == 9 and address.value % 4096 == count % 4096 == 0
        ctypes.memmove(address, bytes(index % 251 for index in range(count)), count)
        ctypes.cast(returned, ctypes.POINTER(ctypes.c_uint32))[0] = count
        return 1

    value.kernel = SimpleNamespace(SetFilePointerEx=pointer, ReadFile=read)
    assert value._read(1025, 1024) == bytes(index % 251 for index in range(1025, 2049))
    assert calls == [(9, 0, 0)]


def test_truncated_raw_read_never_returns_partial_metadata():
    value = _reader()
    value.kernel = SimpleNamespace(SetFilePointerEx=lambda *_args: 1, ReadFile=lambda *_args: 1)
    with pytest.raises(mft.MFTParseError, match="Truncated"):
        value._read(0, 1024)


@pytest.mark.parametrize("offset,size", [(-1, 1), (0, 0), (0, reader._MAX_METADATA + 1), (4194303, 2)])
def test_raw_read_bounds_refuse_before_native_io(offset, size):
    with pytest.raises(mft.MFTParseError):
        _reader()._read(offset, size)


def test_stream_crosses_fragmented_extents_and_refuses_missing_mapping(monkeypatch):
    value = _reader()
    calls = []

    def read(offset, size):
        calls.append((offset, size))
        return b"x" * size

    monkeypatch.setattr(value, "_read", read)
    runs = (mft.Run(0, 1, 8), mft.Run(1, 1, 20))
    assert value._stream(runs, 4090, 20) == b"x" * 20
    assert calls == [(8 * 4096 + 4090, 6), (20 * 4096, 14)]
    with pytest.raises(mft.MFTParseError, match="Missing"):
        value._stream((runs[0],), 4090, 20)


@pytest.mark.parametrize("run", [mft.Run(0, 1, None), mft.Run(0, 2, 1023), mft.Run(0, 1, -1)])
def test_sparse_or_off_volume_metadata_refuses_before_read(run):
    with pytest.raises(mft.MFTParseError, match="extents"):
        _reader()._stream((run,), 0, 1)


def _extensions(monkeypatch):
    value = _reader()
    base = mft.parse_record(_record(_resident(mft.ATTRIBUTE_LIST, _list_entry()), ordinal=24), 24)
    extension = mft.parse_record(_record(_resident(mft.DATA, b"private", instance=3),
                                         ordinal=25, base=base.reference), 25)
    monkeypatch.setattr(value, "record", lambda _ordinal: extension)
    return value, base, extension


def test_extension_resolves_exact_owner_sequence_attribute_without_payload(monkeypatch):
    value, base, _extension = _extensions(monkeypatch)
    attributes = value.attributes(base)
    assert len(attributes) == 2 and attributes[-1].size == 7
    assert attributes[-1].value is None


@pytest.mark.parametrize("changes", [dict(sequence=8), dict(base_reference=999), dict(flags=0),
                                      dict(attributes=())])
def test_stale_foreign_unused_or_missing_extensions_refuse(monkeypatch, changes):
    value, base, extension = _extensions(monkeypatch)
    monkeypatch.setattr(value, "record", lambda _ordinal: replace(extension, **changes))
    with pytest.raises(mft.MFTParseError):
        value.attributes(base)


def test_nested_extension_list_refuses_without_recursive_resolution(monkeypatch):
    value, base, extension = _extensions(monkeypatch)
    nested = mft.parse_record(_record(_resident(mft.ATTRIBUTE_LIST, _list_entry()), ordinal=25,
                                     base=base.reference), 25)
    monkeypatch.setattr(value, "record", lambda _ordinal: replace(extension, attributes=nested.attributes))
    with pytest.raises(mft.MFTParseError, match="Nested/cyclic"):
        value.attributes(base)


def test_mft_mapping_must_cover_initialized_length_and_be_contiguous(monkeypatch):
    value = _reader()
    base = mft.parse_record(_record(_nonresident(b"\x11\x08\x08\0", highest=7, size=32768)), 24)
    monkeypatch.setattr(value, "attributes", lambda _base: base.attributes)
    assert value._mft_runs(base) == (mft.Run(0, 8, 8),)
    value.geometry = replace(value.geometry, mft_size=65536)
    with pytest.raises(mft.MFTParseError, match="Incomplete"):
        value._mft_runs(base)


def test_cache_is_bounded_and_closed_reader_refuses_cached_records(monkeypatch):
    value = _reader()
    value.geometry = replace(value.geometry, mft_size=512 * 1024)
    monkeypatch.setattr(value, "_stream", lambda _runs, offset, _size: _record(ordinal=offset // 1024))
    for ordinal in range(300):
        value.record(ordinal)
    assert len(value._cache) == reader._CACHE_RECORDS and 0 not in value._cache
    value.handle = None
    with pytest.raises(mft.MFTParseError, match="Closed"):
        value.record(299)


def test_stream_records_skip_unused_and_preserve_directory_filter(monkeypatch):
    value = _reader()
    raw = _record(ordinal=0, flags=3) + bytes(1024) + _record(ordinal=2)
    value.geometry = replace(value.geometry, mft_size=len(raw))
    monkeypatch.setattr(value, "_stream", lambda *_args: raw)
    checks = []
    assert [record.ordinal for record in value.records(lambda: checks.append(True))] == [0, 2]
    assert checks == [True]
    assert [record.ordinal for record in value.records(directories_only=True)] == [0]


def test_record_stream_propagates_cancellation_before_io(monkeypatch):
    value = _reader()
    monkeypatch.setattr(value, "_stream", lambda *_args: pytest.fail("read after cancellation"))

    def cancelled():
        raise InterruptedError("cancelled")

    with pytest.raises(InterruptedError):
        list(value.records(cancelled))


def test_torn_in_use_record_and_bad_signature_are_visible(monkeypatch):
    value = _reader()
    value.geometry = replace(value.geometry, mft_size=1024)
    for raw in (_record(ordinal=0)[:-2] + b"xx", b"BAAD" + bytes(1020)):
        monkeypatch.setattr(value, "_stream", lambda *_args, raw=raw: raw)
        with pytest.raises(mft.MFTParseError):
            list(value.records())


def test_refused_record_diagnostics_identify_header_without_payload():
    raw = _record(_resident(mft.DATA, b"private payload"), ordinal=24, flags=5)
    with pytest.raises(mft.MFTParseError) as caught:
        reader._parse_record(raw, 24)
    assert "MFT record 24" in str(caught.value) and "flags=5" in str(caught.value)
    assert "header_number=24" in str(caught.value) and "private payload" not in str(caught.value)
    assert isinstance(caught.value.__cause__, mft.MFTParseError)


def test_short_refused_record_diagnostic_preserves_original_error():
    with pytest.raises(mft.MFTParseError, match="MFT record 24") as caught:
        reader._parse_record(b"FILE", 24)
    assert isinstance(caught.value.__cause__, mft.MFTParseError)
