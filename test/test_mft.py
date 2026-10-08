"""Raw metadata vectors cover fixups, runs, alias/extension identities and refused corrupt records."""

import struct

import pytest

from je_file_tree.core import mft


def _resident(kind, value, instance=0, name=""):
    encoded = name.encode("utf-16-le", errors="surrogatepass")
    value_at = -(-(24 + len(encoded)) // 8) * 8
    size = -(-(value_at + len(value)) // 8) * 8
    raw = bytearray(size)
    struct.pack_into("<IIBBHHHIH", raw, 0, kind, size, 0, len(encoded) // 2, 24, 0, instance, len(value), value_at)
    raw[24:24 + len(encoded)] = encoded
    raw[value_at:value_at + len(value)] = value
    return bytes(raw)


def _nonresident(runs, *, lowest=0, highest=0, size=100, allocated=4096, flags=0, identity=(0, "")):
    encoded = identity[1].encode("utf-16-le")
    header = 72 if flags & 0x8001 else 64
    mapping_at = -(-(header + len(encoded)) // 8) * 8
    length = -(-(mapping_at + len(runs)) // 8) * 8
    raw = bytearray(length)
    struct.pack_into("<IIBBHHH", raw, 0, 0x80, length, 1, len(encoded) // 2, header, flags, identity[0])
    struct.pack_into("<QQH", raw, 16, lowest, highest, mapping_at)
    struct.pack_into("<qqq", raw, 40, allocated, size, size)
    if flags & 0x8001:
        struct.pack_into("<q", raw, 64, allocated)
    raw[header:header + len(encoded)] = encoded
    raw[mapping_at:mapping_at + len(runs)] = runs
    return bytes(raw)


def _record(*attributes, ordinal=24, sequence=7, links=1, flags=1, base=0):
    raw = bytearray(1024)
    raw[:4] = b"FILE"
    struct.pack_into("<HH", raw, 4, 48, 3)
    used = 56 + sum(map(len, attributes)) + 8
    struct.pack_into("<HHHHIIQ", raw, 16, sequence, links, 56, flags, used, 1024, base)
    struct.pack_into("<I", raw, 44, ordinal)
    offset = 56
    for attribute in attributes:
        raw[offset:offset + len(attribute)] = attribute
        offset += len(attribute)
    struct.pack_into("<I", raw, offset, 0xFFFFFFFF)
    raw[48:50] = b"\x12\x34"
    for index, tail in enumerate((510, 1022), 1):
        raw[48 + index * 2:50 + index * 2] = raw[tail:tail + 2]
        raw[tail:tail + 2] = raw[48:50]
    return bytes(raw)


def _filename(name="卷 空白.dat", parent=5 | (3 << 48), namespace=1):
    encoded = name.encode("utf-16-le", errors="surrogatepass")
    raw = bytearray(66 + len(encoded))
    struct.pack_into("<Q", raw, 0, parent)
    raw[64:66] = bytes((len(encoded) // 2, namespace))
    raw[66:] = encoded
    return bytes(raw)


def _list_entry(kind=0x80, name="", lowest=0, reference=25 | (7 << 48), instance=3):
    encoded = name.encode("utf-16-le")
    length = -(-(26 + len(encoded)) // 8) * 8
    raw = bytearray(length)
    struct.pack_into("<IHBBQQH", raw, 0, kind, length, len(encoded) // 2, 26, lowest, reference, instance)
    raw[26:26 + len(encoded)] = encoded
    return bytes(raw)


def test_raw_record_repairs_every_sector_and_preserves_input():
    raw = _record(_resident(0x80, b"private resident data"))
    fixed = mft.repair_record(raw)
    assert fixed[510:512] == fixed[1022:1024] == b"\0\0"
    assert raw[510:512] == raw[1022:1024] == b"\x12\x34"
    with pytest.raises(mft.MFTParseError, match="repaired"):
        mft.repair_record(fixed)


def test_resident_data_retains_sizes_without_main_or_named_payload():
    record = mft.parse_record(_record(_resident(0x80, b"private resident data"),
                                    _resident(0x80, b"private named data", instance=1, name="secret")), 24)
    assert record.reference == 24 | (7 << 48)
    assert record.in_use and not record.is_dir and record.links == 1
    assert [attribute.size for attribute in record.attributes] == [21, 18]
    assert all(attribute.value is None and attribute.allocated == 0 for attribute in record.attributes)
    assert record.attributes[1].name == "secret"
    assert "private" not in repr(record)


def test_resident_capacity_uses_declared_value_space_including_padding_without_payload():
    attribute = bytearray(_resident(mft.DATA, b"private", instance=1))
    attribute.extend(bytes(16))
    struct.pack_into("<I", attribute, 4, len(attribute))
    record = mft.parse_record(_record(bytes(attribute)), 24)
    parsed = record.attributes[0]
    assert parsed.size == 7 and parsed.allocated == 0 and parsed.resident_capacity == 24
    assert parsed.value is None and "private" not in repr(parsed)


def test_file_names_keep_alias_namespace_parent_sequence_and_unicode():
    value = mft.parse_file_name(_filename())
    assert value == mft.FileName(5 | (3 << 48), 1, "卷 空白.dat")
    assert mft.parse_file_name(_filename("SHORT~1.DAT", namespace=2)).namespace == 2
    assert mft.parse_file_name(_filename(".")).name == ".", "root metadata is a literal dot"
    assert mft.parse_file_name(_filename("surrogate-\ud800")).name.endswith("\ud800")


@pytest.mark.parametrize("name", ["a/b", "a\\b", "a\0b", ".."])
def test_file_name_path_injection_refuses(name):
    with pytest.raises(mft.MFTParseError, match="Unsafe"):
        mft.parse_file_name(_filename(name))


@pytest.mark.parametrize("data", [b"", b"x" * 65, _filename()[:-1], _filename(namespace=4)])
def test_file_name_geometry_refuses(data):
    with pytest.raises(mft.MFTParseError):
        mft.parse_file_name(data)


def test_standard_dates_distinguish_creation_and_metadata_change():
    raw = bytearray(72)
    epoch = 116444736000000000
    struct.pack_into("<QQQQI", raw, 0, epoch + 1, epoch + 2, epoch + 3, epoch + 4, 0x20)
    assert mft.parse_standard_information(bytes(raw)) == mft.StandardInformation(100, 200, 300, 400, 0x20)
    with pytest.raises(mft.MFTParseError):
        mft.parse_standard_information(bytes(raw[:-1]))


def test_unsigned_run_lengths_signed_deltas_and_holes():
    # Physical 20..219, sparse hole, then backwards to LCN 15; a hole does not reset LCN 20.
    raw = bytes((0x11, 200, 20, 0x01, 3, 0x11, 2, 251, 0))
    assert mft.parse_runs(raw, 0, 204) == (mft.Run(0, 200, 20), mft.Run(200, 3, None), mft.Run(203, 2, 15))
    assert mft.parse_runs(b"\x11\x01\x00\x00", 0, 0) == (mft.Run(0, 1, 0),), "LCN zero is not a sparse encoding"
    assert mft.parse_runs(b"\0", 0, (1 << 64) - 1) == ()


@pytest.mark.parametrize("raw,lowest,highest", [(b"\x10\1\0", 0, 0), (b"\x19\1\0", 0, 0),
                                              (b"\x11\0\1\0", 0, 0), (b"\x11\1\xff\0", 0, 0),
                                              (b"\x11\1\1", 0, 0), (b"\x11\1\1\0", 0, 1),
                                              (b"\0", 2, 1), (b"\x11", 0, 0)])
def test_corrupt_or_unterminated_runs_refuse(raw, lowest, highest):
    with pytest.raises(mft.MFTParseError):
        mft.parse_runs(raw, lowest, highest)


def test_nonresident_sizes_and_continuations_do_not_invent_sizes():
    first = _nonresident(b"\x11\1\x14\0")
    continuation = _nonresident(b"\x11\1\x15\0", lowest=1, highest=1, size=-1, allocated=-1, identity=(1, ""))
    record = mft.parse_record(_record(first, continuation, base=24 | (7 << 48)), 24)
    assert (record.attributes[0].size, record.attributes[0].allocated) == (100, 4096)
    assert record.attributes[1].size is record.attributes[1].allocated is None
    assert record.attributes[1].runs == (mft.Run(1, 1, 21),)


def test_sparse_and_compressed_extents_keep_physical_header_allocation():
    attribute = _nonresident(b"\x11\1\x14\x01\x03\0", highest=3, size=16384, allocated=4096, flags=0x8000)
    parsed = mft.parse_record(_record(attribute), 24).attributes[0]
    assert parsed.allocated == 4096 and parsed.size == 16384
    assert parsed.runs[-1] == mft.Run(1, 3, None)


def test_nonresident_named_data_and_empty_data_have_no_payload():
    named = _nonresident(b"\x11\1\x14\0", identity=(0, "named"))
    empty = _nonresident(b"\0", highest=(1 << 64) - 1, size=0, allocated=0, identity=(1, ""))
    parsed = mft.parse_record(_record(named, empty, links=3), 24)
    assert parsed.links == 3 and parsed.attributes[0].name == "named"
    assert parsed.attributes[1].size == parsed.attributes[1].allocated == 0
    assert parsed.attributes[1].runs == () and all(value.value is None for value in parsed.attributes)


@pytest.mark.parametrize("offset,format_code,value", [(8, "B", 2), (12, "H", 0x400), (20, "H", 0),
                                                    (16, "I", 1000000), (10, "H", 1024)])
def test_corrupt_resident_forms_flags_and_value_bounds_refuse(offset, format_code, value):
    attribute = bytearray(_resident(0x80, b"data", name="named"))
    struct.pack_into("<" + format_code, attribute, offset, value)
    with pytest.raises(mft.MFTParseError):
        mft.parse_record(_record(bytes(attribute)), 24)


@pytest.mark.parametrize("offset,format_code,value", [(32, "H", 0), (40, "q", -1), (48, "q", -1),
                                                    (56, "q", 101), (10, "H", 1024)])
def test_corrupt_nonresident_bounds_and_sizes_refuse(offset, format_code, value):
    attribute = bytearray(_nonresident(b"\x11\1\x14\0", identity=(0, "named")))
    struct.pack_into("<" + format_code, attribute, offset, value)
    with pytest.raises(mft.MFTParseError):
        mft.parse_record(_record(bytes(attribute)), 24)


def test_attribute_list_keeps_full_extension_identity_and_names():
    raw = _list_entry() + _list_entry(name="named", lowest=1, reference=26 | (8 << 48), instance=4)
    entries = mft.parse_attribute_list(raw)
    assert entries == (mft.AttributeListEntry(0x80, "", 0, 25 | (7 << 48), 3),
                       mft.AttributeListEntry(0x80, "named", 1, 26 | (8 << 48), 4))


@pytest.mark.parametrize("raw", [b"", b"x" * 25, _list_entry()[:-1], _list_entry(reference=25),
                                 _list_entry() * 2])
def test_corrupt_duplicate_or_unqualified_attribute_list_refuses(raw):
    with pytest.raises(mft.MFTParseError):
        mft.parse_attribute_list(raw)


@pytest.mark.parametrize("offset,format_code,value", [(4, "H", 16), (6, "H", 2), (16, "H", 0),
                                                    (20, "H", 57), (22, "H", 16), (24, "I", 1025),
                                                    (28, "I", 512), (44, "I", 25), (510, "H", 1),
                                                    (1022, "H", 1), (60, "I", 0)])
def test_corrupt_raw_headers_sectors_and_attribute_lengths_refuse(offset, format_code, value):
    raw = bytearray(_record(_resident(0x80, b"resident")))
    struct.pack_into("<" + format_code, raw, offset, value)
    with pytest.raises(mft.MFTParseError):
        mft.parse_record(bytes(raw), 24)


def test_duplicate_instances_and_missing_attribute_end_refuse():
    with pytest.raises(mft.MFTParseError, match="Duplicate"):
        mft.parse_record(_record(_resident(0x80, b"one"), _resident(0x80, b"two")), 24)
    raw = bytearray(_record())
    struct.pack_into("<I", raw, 56, 0x80)
    with pytest.raises(mft.MFTParseError):
        mft.parse_record(bytes(raw), 24)


@pytest.mark.parametrize("flags", [4, 5, 8, 9, 11, 13, 15])
def test_known_system_and_view_index_flags_preserve_directory_and_live_bits(flags):
    record = mft.parse_record(_record(_resident(mft.DATA, b"private"), flags=flags), 24)
    assert record.flags == flags
    assert record.in_use == bool(flags & 1)
    assert record.is_dir == bool(flags & 2)
    assert record.attributes[0].value is None


def test_live_zero_link_segment_retains_metadata_without_inventing_a_name():
    record = mft.parse_record(_record(_resident(mft.DATA, b"private"), ordinal=12,
                                    sequence=12, links=0, flags=1), 12)
    assert record.in_use and record.links == 0 and record.base_reference == 0
    assert record.reference == 12 | (12 << 48)
    assert not any(attribute.kind == mft.FILE_NAME for attribute in record.attributes)
    assert record.attributes[0].value is None


def test_unused_formatted_segment_may_have_zero_sequence_and_links():
    record = mft.parse_record(_record(sequence=0, links=0, flags=0), 24)
    assert not record.in_use and record.sequence == record.links == 0
    assert record.attributes == ()


def test_large_record_metadata_crossing_sector_tail_is_repaired():
    value = b"metadata" * 70
    record = mft.parse_record(_record(_resident(0x20, value)), 24)
    assert record.attributes[0].value == value
