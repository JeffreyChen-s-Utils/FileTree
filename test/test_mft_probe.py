"""Diagnostic phase persistence and failure cleanup use mocked fixtures, not native validation claims."""

from contextlib import contextmanager
import json
import stat
import struct
from types import SimpleNamespace

import pytest

from tools import validate_mft as probe
from je_file_tree.core import mft
from test_mft import _filename, _nonresident, _record, _resident


@pytest.mark.parametrize("fail", [False, True])
def test_atomic_utf8_phase_evidence_and_fixture_exit(tmp_path, monkeypatch, fail):
    output = tmp_path / "evidence.json"
    exits = []

    @contextmanager
    def owned():
        try:
            yield SimpleNamespace(root=tmp_path / "owned")
        finally:
            exits.append(True)

    def proof(_volume):
        if fail:
            raise ValueError("metadata rejected")
        return {"source_preserved": True, "scanner_enabled": False}

    monkeypatch.setattr(probe, "owned_ntfs_volume", owned)
    monkeypatch.setattr(probe, "_proof", proof)
    monkeypatch.setattr(probe.sys, "argv", ["validate_mft.py", "--output", str(output)])
    if fail:
        with pytest.raises(ValueError, match="metadata rejected"):
            probe.main()
    else:
        probe.main()
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert exits == [True]
    assert evidence["phase"] == ("failed" if fail else "complete")
    assert evidence["cleanup_verified"] is not fail


def test_native_allocation_difference_refuses_with_bounded_metadata_evidence(monkeypatch):
    raw = _record(_resident(mft.FILE_NAME, _filename("fixture.bin", parent=5 | (7 << 48))),
                  _nonresident(b"\x11\x01\x14\0", identity=(1, "")))
    record = mft.parse_record(raw, 24)
    native = SimpleNamespace(record=lambda _ordinal: record, attributes=lambda _base: record.attributes)
    info = SimpleNamespace(st_ino=record.reference, st_size=100, st_mode=stat.S_IFREG)
    parent = SimpleNamespace(lstat=lambda: SimpleNamespace(st_ino=5 | (7 << 48)))
    path = SimpleNamespace(name="fixture.bin", lstat=lambda: info, parent=parent)
    monkeypatch.setattr(probe, "file_allocation", lambda *_args: 8192)
    with pytest.raises(RuntimeError, match="fixture.bin; raw=4096, native=8192, resident=False, flags=0, logical=100"):
        probe._observe(native, path)


@pytest.mark.parametrize("length", [0, 1, 7, 9, 24, 31, 127])
def test_resident_cluster_allocation_and_native_byte_length_are_distinct(monkeypatch, length):
    standard = bytearray(72)
    struct.pack_into("<QQQQI", standard, 0, *([116444736000000001] * 4), 0x20)
    raw = _record(_resident(mft.STANDARD_INFORMATION, bytes(standard)),
                  _resident(mft.FILE_NAME, _filename("fixture.bin", parent=5 | (7 << 48)), instance=1),
                  _resident(mft.DATA, b"r" * length, instance=2))
    record = mft.parse_record(raw, 24)
    native = SimpleNamespace(record=lambda _ordinal: record, attributes=lambda _base: record.attributes)
    info = SimpleNamespace(st_ino=record.reference, st_size=length, st_mtime_ns=100, st_nlink=1)
    path = SimpleNamespace(name="fixture.bin", lstat=lambda: info,
                           parent=SimpleNamespace(lstat=lambda: SimpleNamespace(st_ino=5 | (7 << 48))))
    monkeypatch.setattr(probe, "file_allocation", lambda *_args: length)
    observed = probe._observe(native, path)
    assert observed["raw_allocated"] == 0 and observed["native_allocated"] == length
    monkeypatch.setattr(probe, "file_allocation", lambda *_args: length + 1)
    with pytest.raises(RuntimeError, match="allocation differs"):
        probe._observe(native, path)
