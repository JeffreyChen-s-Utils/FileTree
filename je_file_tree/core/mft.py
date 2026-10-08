"""Bounded NTFS 3.1 metadata parsing; no filesystem access, user payload retention or Qt imports.

Raw FILE records require matching update-sequence words at every 512-byte sector tail.
Nonresident mapping pairs retain unsigned run lengths, signed LCN deltas and sparse holes.
Only metadata attributes retain resident values; resident $DATA retains size, never contents.
Native reading and ordinary-scan fallback are separate from this parser.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

STANDARD_INFORMATION = 0x10
ATTRIBUTE_LIST = 0x20
FILE_NAME = 0x30
DATA = 0x80
REPARSE_POINT = 0xC0
_METADATA = frozenset({STANDARD_INFORMATION, ATTRIBUTE_LIST, FILE_NAME, REPARSE_POINT})
_SECTOR = 512
_MAX_RECORD = 65536
_MAX_ENTRIES = 4096
_MAX_LIST = 8 * 1024 * 1024
_ALIGN = 8
_RESIDENT_HEADER = 24
_NONRESIDENT_HEADER = 64
_PACKED_HEADER = 72
_LIST_HEADER = 26
_NAME_HEADER = 66
_STANDARD_BYTES = 48
_RECORD_HEADER = 48
_END = 0xFFFFFFFF
_MAX_VCN = (1 << 63) - 1
_MAX_REFERENCE = (1 << 64) - 1
_ORDINAL_MASK = (1 << 48) - 1
_PACKED = 0x8000 | 0x00FF
_FLAGS = 0x8000 | 0x4000 | 0x0001
_FILETIME_EPOCH = 116444736000000000


class MFTParseError(ValueError):
    """Malformed, unsupported or inconsistent metadata requires an ordinary filesystem scan."""


@dataclass(frozen=True, slots=True)
class Run:
    """A contiguous VCN range; a None LCN is an unallocated sparse hole."""

    vcn: int
    length: int
    lcn: int | None


@dataclass(frozen=True, slots=True)
class Attribute:
    """Attribute identity, size/allocation and extents; DATA contents are always absent.

    Continuation segments have unknown size/allocation: only LowestVcn zero owns those fields.
    Allocation is header-reported metadata, not a promise of independently recoverable bytes.
    """

    kind: int
    instance: int
    name: str
    flags: int
    resident: bool
    lowest_vcn: int
    size: int | None
    allocated: int | None
    runs: tuple[Run, ...]
    value: bytes | None = None


@dataclass(frozen=True, slots=True)
class FileRecord:
    """One FILE segment with its complete sequence-qualified identity and base-record reference."""

    ordinal: int
    sequence: int
    links: int
    flags: int
    base_reference: int
    attributes: tuple[Attribute, ...]

    @property
    def reference(self) -> int:
        """The file reference includes its reuse sequence, not only its MFT ordinal."""
        return self.ordinal | (self.sequence << 48)

    @property
    def in_use(self) -> bool:
        """Whether this segment is currently marked in use."""
        return bool(self.flags & 1)

    @property
    def is_dir(self) -> bool:
        """Whether the FILE header marks a filename-index directory."""
        return bool(self.flags & 2)


@dataclass(frozen=True, slots=True)
class FileName:
    """One complete parent reference and NTFS namespace/name; DOS aliases remain distinguishable."""

    parent: int
    namespace: int
    name: str


@dataclass(frozen=True, slots=True)
class AttributeListEntry:
    """A sequence-qualified segment and attribute identity for bounded extension resolution."""

    kind: int
    name: str
    lowest_vcn: int
    reference: int
    instance: int


@dataclass(frozen=True, slots=True)
class StandardInformation:
    """Native FILETIME nanoseconds and file attributes; changed time is distinct from creation."""

    created_ns: int
    modified_ns: int
    changed_ns: int
    accessed_ns: int
    attributes: int


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise MFTParseError(detail)


def _name(data: bytes, offset: int, count: int, minimum: int) -> str:
    if not count:
        return ""  # NTFS leaves NameOffset undefined when NameLength is zero.
    _require(offset >= minimum and offset % 2 == 0 and offset + count * 2 <= len(data), "Invalid attribute name")
    return data[offset:offset + count * 2].decode("utf-16-le", errors="surrogatepass")


def repair_record(data: bytes) -> bytes:
    """Validate raw FILE geometry and all sector markers before restoring update-sequence tails.

    This accepts raw on-disk records only. Already repaired native control replies must not be
    presented as raw records. Torn or partially repaired sectors are rejected rather than guessed.
    """
    _require(_SECTOR <= len(data) <= _MAX_RECORD and len(data) % _SECTOR == 0 and data[:4] == b"FILE",
             "Invalid raw FILE record geometry")
    offset, count = struct.unpack_from("<HH", data, 4)
    first, = struct.unpack_from("<H", data, 20)
    _require(count == len(data) // _SECTOR + 1 and offset >= _RECORD_HEADER and offset % 2 == 0
             and offset + count * 2 <= first <= len(data), "Invalid update-sequence array")
    marker = data[offset:offset + 2]
    _require(marker not in (b"\0\0", b"\xff\xff"), "Invalid update-sequence marker")
    tails = range(_SECTOR - 2, len(data), _SECTOR)
    _require(all(data[tail:tail + 2] == marker for tail in tails), "Torn or repaired FILE record")
    repaired = bytearray(data)
    for index, tail in enumerate(tails, 1):
        repaired[tail:tail + 2] = data[offset + index * 2:offset + index * 2 + 2]
    return bytes(repaired)


def parse_runs(data: bytes, lowest_vcn: int, highest_vcn: int) -> tuple[Run, ...]:
    """Decode bounded NTFS mapping pairs; holes never change the previous physical LCN."""
    _require(0 <= lowest_vcn <= _MAX_VCN and len(data) <= _MAX_RECORD, "Invalid mapping-pairs bounds")
    if highest_vcn == _MAX_REFERENCE and lowest_vcn == 0:
        _require(bool(data) and data[0] == 0, "Invalid empty nonresident extent")
        return ()
    _require(lowest_vcn <= highest_vcn < _MAX_VCN, "Invalid VCN extent")
    offset, vcn, lcn = 0, lowest_vcn, 0
    runs = []
    while offset < len(data):
        header = data[offset]
        offset += 1
        if not header:
            _require(vcn == highest_vcn + 1, "Mapping pairs do not cover the declared VCN range")
            return tuple(runs)
        length_bytes, delta_bytes = header & 15, header >> 4
        _require(1 <= length_bytes <= _ALIGN and delta_bytes <= _ALIGN
                 and offset + length_bytes + delta_bytes <= len(data) and len(runs) < _MAX_ENTRIES,
                 "Invalid mapping-pairs field")
        length = int.from_bytes(data[offset:offset + length_bytes], "little")
        offset += length_bytes
        _require(length > 0 and vcn + length <= highest_vcn + 1, "Invalid mapping-pairs run length")
        physical = None
        if delta_bytes:
            lcn += int.from_bytes(data[offset:offset + delta_bytes], "little", signed=True)
            _require(0 <= lcn <= _MAX_VCN and lcn + length <= _MAX_VCN, "Invalid physical cluster range")
            physical = lcn
        offset += delta_bytes
        runs.append(Run(vcn, length, physical))
        vcn += length
    raise MFTParseError("Unterminated mapping pairs")


def _resident(data: bytes, identity: tuple[int, int, str, int]) -> Attribute:
    kind, instance, name, flags = identity
    length, offset = struct.unpack_from("<IH", data, 16)
    _require(offset >= _RESIDENT_HEADER and offset + length <= len(data), "Invalid resident attribute bounds")
    if name:
        name_at, = struct.unpack_from("<H", data, 10)
        _require(name_at + len(name.encode("utf-16-le", errors="surrogatepass")) <= offset,
                 "Resident name overlaps its value")
    value = data[offset:offset + length] if kind in _METADATA else None
    return Attribute(kind, instance, name, flags, True, 0, length, 0, (), value)


def _nonresident(data: bytes, identity: tuple[int, int, str, int]) -> Attribute:
    kind, instance, name, flags = identity
    header = _PACKED_HEADER if flags & _PACKED else _NONRESIDENT_HEADER
    _require(len(data) >= header, "Truncated nonresident header")
    lowest, highest, mapping_at = struct.unpack_from("<QQH", data, 16)
    _require(header <= mapping_at < len(data), "Invalid mapping-pairs offset")
    if name:
        name_at, = struct.unpack_from("<H", data, 10)
        _require(name_at + len(name.encode("utf-16-le", errors="surrogatepass")) <= mapping_at,
                 "Nonresident name overlaps mapping pairs")
    runs = parse_runs(data[mapping_at:], lowest, highest)
    allocated = size = None
    if lowest == 0:
        allocated, size, initialized = struct.unpack_from("<qqq", data, 40)
        _require(0 <= initialized <= size and allocated >= 0, "Invalid nonresident sizes")
        if flags & _PACKED:
            allocated, = struct.unpack_from("<q", data, 64)
            _require(allocated >= 0, "Invalid compressed/sparse allocation")
        _require(bool(runs) or size == 0, "Nonempty data has no extents")
    return Attribute(kind, instance, name, flags, False, lowest, size, allocated, runs)


def _attribute(data: bytes) -> Attribute:
    _require(len(data) >= _RESIDENT_HEADER, "Truncated attribute header")
    kind, length, form, count, offset, flags, instance = struct.unpack_from("<IIBBHHH", data)
    _require(kind > 0 and kind < _END and kind % 16 == 0 and length == len(data)
             and form in (0, 1) and not flags & ~_FLAGS, "Unsupported attribute header")
    minimum = _RESIDENT_HEADER if form == 0 else (_PACKED_HEADER if flags & _PACKED else _NONRESIDENT_HEADER)
    name = _name(data, offset, count, minimum)
    identity = kind, instance, name, flags
    return _resident(data, identity) if form == 0 else _nonresident(data, identity)


def parse_record(data: bytes, ordinal: int) -> FileRecord:
    """Parse one raw NTFS 3.1 FILE record; corrupt headers, duplicate instances and missing ends refuse."""
    _require(0 <= ordinal <= _ORDINAL_MASK, "Invalid MFT ordinal")
    raw = repair_record(data)
    sequence, links, first, flags, used, allocated, base = struct.unpack_from("<HHHHIIQ", raw, 16)
    number, = struct.unpack_from("<I", raw, 44)
    _require(allocated == len(raw) and _RECORD_HEADER <= first < used <= allocated and first % _ALIGN == 0
             and flags in (0, 1, 2, 3) and number == ordinal & _END, "Invalid FILE record header")
    _require(sequence > 0 and (not flags & 1 or links > 0 or base > 0), "Invalid FILE record identity")
    attributes, instances = [], set()
    offset = first
    while offset + 4 <= used:
        kind, = struct.unpack_from("<I", raw, offset)
        if kind == _END:
            return FileRecord(ordinal, sequence, links, flags, base, tuple(attributes))
        _require(offset + _ALIGN <= used and len(attributes) < _MAX_ENTRIES, "Truncated or excessive attributes")
        length, = struct.unpack_from("<I", raw, offset + 4)
        _require(length >= _RESIDENT_HEADER and length % _ALIGN == 0 and offset + length <= used,
                 "Invalid attribute record length")
        attribute = _attribute(raw[offset:offset + length])
        _require(attribute.instance not in instances, "Duplicate attribute instance")
        instances.add(attribute.instance)
        attributes.append(attribute)
        offset += length
    raise MFTParseError("Unterminated FILE attributes")


def parse_file_name(data: bytes) -> FileName:
    """Parse a resident FILE_NAME; preserve UTF-16 names and reject embedded path separators/NULs.

    The root record's literal dot is retained as metadata, never joined as an ordinary child path.
    """
    _require(_NAME_HEADER <= len(data) <= _NAME_HEADER + 510, "Invalid FILE_NAME value bounds")
    parent, = struct.unpack_from("<Q", data)
    count, namespace = data[64:66]
    _require(count > 0 and namespace in (0, 1, 2, 3) and _NAME_HEADER + count * 2 == len(data),
             "Invalid FILE_NAME length/namespace")
    name = data[_NAME_HEADER:].decode("utf-16-le", errors="surrogatepass")
    _require(not any(char in name for char in ("\0", "/", "\\")) and name != "..", "Unsafe FILE_NAME path")
    return FileName(parent, namespace, name)


def parse_standard_information(data: bytes) -> StandardInformation:
    """Decode creation, modification, metadata-change and access dates separately from raw FILETIME."""
    _require(len(data) in (_STANDARD_BYTES, 72), "Invalid STANDARD_INFORMATION length")
    times = [(value - _FILETIME_EPOCH) * 100 for value in struct.unpack_from("<QQQQ", data)]
    attributes, = struct.unpack_from("<I", data, 32)
    return StandardInformation(*times, attributes)


def parse_attribute_list(data: bytes) -> tuple[AttributeListEntry, ...]:
    """Validate bounded extension identities; resolving sequences, base ownership and cycles is separate."""
    _require(0 < len(data) <= _MAX_LIST, "Invalid attribute-list bounds")
    entries, identities = [], set()
    offset = 0
    while offset < len(data):
        _require(offset + _LIST_HEADER <= len(data) and len(entries) < _MAX_ENTRIES, "Truncated attribute list")
        kind, length, count, name_at, lowest, reference, instance = struct.unpack_from("<IHBBQQH", data, offset)
        _require(kind > 0 and kind < _END and kind % 16 == 0 and length >= _LIST_HEADER
                 and length % _ALIGN == 0 and offset + length <= len(data) and lowest <= _MAX_VCN,
                 "Invalid attribute-list entry")
        name = _name(data[offset:offset + length], name_at, count, _LIST_HEADER)
        identity = kind, name, lowest, reference, instance
        _require(identity not in identities and reference >> 48 > 0, "Duplicate or unqualified extension identity")
        identities.add(identity)
        entries.append(AttributeListEntry(*identity))
        offset += length
    return tuple(entries)
