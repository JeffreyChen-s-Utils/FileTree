"""Native compact validation confined to freshly created disposable NTFS fixtures.

Run py -3 tools/validate_windows_compression.py --output proof.json. No existing volume, bin, user
file or caller-selected compression scope is accepted. Junction targets remain inside owned scratch.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import struct
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.compression import file_system  # noqa: E402
from je_file_tree.core.compression_ops import compress_files  # noqa: E402
from je_file_tree.core.scanner import ScanOptions, scan  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402

_PAYLOAD = b"owned compression fixture text\n" * 65536
_OPTIONS = ScanOptions(exact_windows_allocation=True)


def _junction(path: Path, target: Path, owned: Path) -> None:
    if not path.is_relative_to(owned) or not target.resolve().is_relative_to(owned):
        raise ValueError("Refusing unowned junction")
    path.mkdir()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                  ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                                      ctypes.c_void_p]
    handle = kernel.CreateFileW(str(path), 0x40000000, 0, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    substitute = ("\\??\\" + str(target)).encode("utf-16-le")
    display = str(target).encode("utf-16-le")
    names = substitute + b"\0\0" + display + b"\0\0"
    raw = struct.pack("<LHHHHHH", 0xA0000003, 8 + len(names), 0, 0, len(substitute),
                      len(substitute) + 2, len(display)) + names
    returned = ctypes.c_uint32()
    try:
        if not kernel.DeviceIoControl(handle, 0x900a4, ctypes.create_string_buffer(raw), len(raw),
                                      None, 0, ctypes.byref(returned), None):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


def _record(path: Path) -> dict[str, int | str]:
    node = next((item for item in scan(path.parent, options=_OPTIONS).root.children if item.name == path.name), None)
    if node is None:
        raise RuntimeError("Owned fixture not scanned")
    return {"size": node.size, "allocated": node.allocated, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _case(owned: Path, mode: str) -> dict:
    scope, outside = owned / mode, owned / (mode + "-outside")
    scope.mkdir()
    outside.mkdir()
    source, peer = scope / "fixture 測試.log", outside / "peer.log"
    source.write_bytes(_PAYLOAD)
    peer.write_bytes(_PAYLOAD)
    link = scope / "junction"
    _junction(link, outside, owned)
    try:
        before, peer_before = _record(source), _record(peer)
        root = next(node for node in scan(owned, options=_OPTIONS).root.children if node.name == scope.name)
        result = compress_files(root, list(root.iter_files()), mode)
        compressed = _record(source)
        root = scan(scope, options=_OPTIONS).root
        restored_result = compress_files(root, list(root.iter_files()), "uncompress")
        restored, peer_after = _record(source), _record(peer)
        if (result.completed != 1 or restored_result.completed != 1
                or compressed["allocated"] >= before["allocated"] or peer_before != peer_after
                or before != restored or compressed["sha256"] != before["sha256"]):
            raise RuntimeError("Compression/content/restoration/outside-scope check failed")
        os.link(source, outside / "hardlink.log")
        root = scan(scope, options=_OPTIONS).root
        refused = compress_files(root, list(root.iter_files()), mode)
        if refused.completed or len(refused.failures) != 1:
            raise RuntimeError("Hard-linked file was not refused")
        return {"before": before, "compressed": compressed, "restored": restored,
                "operation": asdict(result), "restoration": asdict(restored_result),
                "outside_unchanged": peer_before == peer_after, "hardlink_refused": True}
    finally:
        if not link.is_relative_to(owned) or not outside.resolve().is_relative_to(owned):
            raise RuntimeError("Refusing unowned cleanup")
        os.rmdir(link)


def main() -> int:
    """Validate native operations only inside a fresh temporary directory and write the evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Native Windows validation required")
    with tempfile.TemporaryDirectory(prefix="filetree-compression-validation-") as scratch:
        owned = Path(scratch).absolute()
        if file_system(str(owned)) != "NTFS":
            raise RuntimeError("Fresh owned fixture is not on NTFS")
        evidence = {"private_fixture": True, "ntfs": _case(owned, "ntfs"),
                    "xpress8k": _case(owned, "xpress8k")}
    with _atomic_file(args.output, encoding="utf-8") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
