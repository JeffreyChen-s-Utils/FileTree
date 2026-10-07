"""Metadata-only named stream measurements exclude default data, links and failed inventories."""

import ctypes
import importlib.util
import sys
from pathlib import Path

import pytest


def _load():
    source = Path(__file__).parents[1] / "tools/measure_streams.py"
    spec = importlib.util.spec_from_file_location("measure_streams", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(sys.platform != "win32", reason="Native stream ABI requires Windows")
def test_native_unicode_named_streams_and_default_data_are_separate(tmp_path):
    module = _load()
    file = tmp_path / "資料, sample.txt"
    file.write_bytes(b"default payload")
    streams = [(":Zone.Identifier:$DATA", b"[ZoneTransfer]\r\nZoneId=3\r\n"), (":附註:$DATA", b"x" * 1024)]
    try:
        for name, contents in streams:
            Path(str(file) + name).write_bytes(contents)
    except OSError as error:
        pytest.skip(f"Fixture volume does not support named streams: {error}")
    assert dict(module.named_streams(str(file))) == {name: len(contents) for name, contents in streams}
    assert file.read_bytes() == b"default payload"
    folder = tmp_path / "folder"
    folder.mkdir()
    assert module.named_streams(str(folder)) == []
    Path(str(folder) + ":note").write_bytes(b"folder stream")
    assert module.named_streams(str(folder)) == [(":note:$DATA", len(b"folder stream"))]
    with pytest.raises(OSError):
        module.named_streams(str(tmp_path / "missing"))


def test_failed_stream_entry_is_unknown_and_not_counted_empty(monkeypatch):
    module = _load()

    def streams(path):
        if path == "denied":
            raise PermissionError("denied")
        return [(":data:$DATA", 900)] if path == "named" else []

    monkeypatch.setattr(module, "named_streams", streams)
    result = module._inventory(["empty", "named", "denied"])
    assert result["known_entries"] == 2 and result["unknown_entries"] == 1
    assert result["entries_with_streams"] == 1 and result["stream_logical_bytes"] == 900
    assert result["errors"] == {"denied": 1}


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows enumeration")
def test_search_handle_closed_when_next_stream_fails(monkeypatch, tmp_path):
    module = _load()
    file = tmp_path / "x"
    file.write_bytes(b"x")
    closed = []

    class Kernel:
        def FindFirstStreamW(self, _path, _level, pointer, _flags):  # noqa: N802 - native ABI
            data = ctypes.cast(pointer, ctypes.POINTER(module._StreamData)).contents
            data.name, data.size = "::$DATA", 1
            return 123

        def FindNextStreamW(self, _handle, _pointer):  # noqa: N802 - native ABI
            ctypes.set_last_error(5)
            return 0

        def FindClose(self, handle):  # noqa: N802 - native ABI
            closed.append(handle)
            return 1

    monkeypatch.setattr(module, "_kernel", Kernel)
    with pytest.raises(OSError):
        module.named_streams(str(file))
    assert closed == [123]


def test_bounded_measurement_does_not_extrapolate_sample_prevalence(monkeypatch, sample_tree):
    module = _load()
    monkeypatch.setattr(module, "named_streams", lambda _path: [])
    result = module.measure(str(sample_tree), entries=3, repeats=2)
    assert result["sample_truncated"] and result["sampled_entries"] == 3
    assert len(result["scan_seconds"]) == 2 and len(result["stream_inventories"]) == 2
    assert all(inventory["known_entries"] == 3 for inventory in result["stream_inventories"])
