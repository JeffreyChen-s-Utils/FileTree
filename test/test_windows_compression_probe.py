"""The native probe canonicalizes fresh scratch roots even when TEMP uses Windows short names."""

import ctypes
import json
import os
import sys
from pathlib import Path

import pytest

from tools import validate_windows_compression as probe


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows short-path fixture")
def test_owned_native_probe_accepts_canonicalized_short_temp_root(tmp_path, monkeypatch):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetShortPathNameW.restype = ctypes.c_uint32
    long_path = tmp_path.resolve(strict=True)
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel.GetShortPathNameW(str(long_path), buffer, len(buffer))
    if not 0 < length < len(buffer) or os.path.normcase(buffer.value) == os.path.normcase(str(long_path)):
        pytest.skip("8.3 names unavailable on this owned temporary fixture")
    original = probe.tempfile.TemporaryDirectory
    monkeypatch.setattr(probe.tempfile, "TemporaryDirectory", lambda **kwargs:
                        original(dir=buffer.value, **kwargs))
    evidence = tmp_path / "proof.json"
    monkeypatch.setattr(sys, "argv", ["validate_windows_compression.py", "--output", str(evidence)])
    assert probe.main() == 0
    result = json.loads(evidence.read_text(encoding="utf-8"))
    assert result["private_fixture"]
    for mode in ("ntfs", "xpress8k"):
        assert result[mode]["outside_unchanged"] and result[mode]["hardlink_refused"]
        assert result[mode]["before"] == result[mode]["restored"]
    assert Path(buffer.value).resolve(strict=True) == long_path
