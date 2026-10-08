"""Populated guest preservation on an owned, detached fixture only; no existing image selector."""

from contextlib import contextmanager
import ctypes
from dataclasses import asdict, replace
import hashlib
import os
from pathlib import Path
import tempfile
import time
from collections.abc import Iterator

from PySide6.QtWidgets import QApplication, QWidget

from je_file_tree.core import virtual_disk_info as native
from je_file_tree.core.copy_io import opened_file
from je_file_tree.core.operation_journal import OperationJournal
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.snapshot import stat_snapshot, unpack_snapshot
from je_file_tree.core.virtual_disks import find_virtual_disks
from je_file_tree.core.virtual_disk_compaction import prepare_compaction
from je_file_tree.gui.virtual_disk_compaction import DiskCompactionWorker
from tools.windows_owned_volume import OwnedVolume, _library, _physical, require, verify_volume

_BYTES = 1024 * 1024
_TIMEOUT = 20
_OPTIONS = ScanOptions(exact_windows_allocation=True, workers=1)


def _payload(path: Path, data: bytes, volume: OwnedVolume) -> None:
    verify_volume(volume)
    require(path.parent.is_relative_to(volume.root), "Guest fixture escaped the owned mounted root")
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with opened_file(str(path), stat_snapshot(str(path))) as stream:
        while block := stream.read(_BYTES):
            digest.update(block)
    return digest.hexdigest()


def capture_guest(volume: OwnedVolume) -> dict[str, dict[str, object]]:
    """Write only new ordinary fixture payloads and capture full main/ADS hashes, identities and sizes."""
    verify_volume(volume)
    root = volume.root / "owned-guest-preservation"
    root.mkdir()
    payload = root / "保留資料.bin"
    _payload(payload, bytes(range(256)) * (_BYTES // 256), volume)
    with Path(str(payload) + ":owned-stream").open("xb") as stream:
        stream.write(b"owned guest named stream\0" * 1024)
    os.link(payload, root / "guest hard-link.bin")
    _payload(root / "zero blocks.bin", b"\xa5" * (32 * _BYTES), volume)
    verify_volume(volume)
    with (root / "zero blocks.bin").open("r+b") as stream:
        for _block in range(32):
            stream.write(b"\0" * _BYTES)
        stream.flush()
        os.fsync(stream.fileno())
    _payload(root / "guest text.txt", b"owned unchanged guest text\n" * 4096, volume)
    captured = {}
    for path in root.iterdir():
        info = unpack_snapshot(stat_snapshot(str(path)))
        captured[path.name] = {"size": info.size, "identity": list(info.identity), "links": info.links,
                               "sha256": _hash(path)}
    with Path(str(payload) + ":owned-stream").open("rb") as stream:
        captured[payload.name]["stream_sha256"] = hashlib.sha256(stream.read()).hexdigest()
    return captured


@contextmanager
def _readonly_guest(volume: OwnedVolume) -> Iterator[OwnedVolume]:
    library = _library()
    kind = volume.image.suffix.removeprefix(".")
    storage = native._Storage(native._DEVICES[kind], native._Guid.from_buffer_copy(native._MICROSOFT))
    parameters, handle = native._Open(2, 0, 1, native._Guid()), ctypes.c_void_p()
    code = library.OpenVirtualDisk(ctypes.byref(storage), str(volume.image), 0, 1,
                                   ctypes.byref(parameters), ctypes.byref(handle))
    if code:
        raise ctypes.WinError(code)
    attached = False
    try:
        require(bytes(native._query(library, handle, 2).value.guid) == volume.identifier,
                "Refusing attachment of a changed owned UUID")
        code = library.AttachVirtualDisk(handle, None, 3, 0, None, None)  # READ_ONLY | NO_DRIVE_LETTER
        if code:
            raise ctypes.WinError(code)
        attached = True
        current = replace(volume, physical=_physical(library, handle), root=Path(volume.volume_id), handle=handle)
        end = time.monotonic() + _TIMEOUT
        while not current.root.exists():
            require(time.monotonic() < end, "Owned read-only guest volume did not become available")
            time.sleep(0.05)
        verify_volume(current)
        yield current
    finally:
        try:
            code = library.DetachVirtualDisk(handle, 0, 0) if attached else 0
            if code:
                raise OSError(f"Owned read-only detach failed ({code}); image must be retained")
        finally:
            native._kernel().CloseHandle(handle)


def verify_guest(volume: OwnedVolume, captured: dict[str, dict[str, object]]) -> None:
    """Reattach only the captured owned UUID read-only, never format, and reverify exact guest records."""
    with _readonly_guest(volume) as current:
        root = current.root / "owned-guest-preservation"
        require({path.name for path in root.iterdir()} == set(captured), "Guest namespace changed after compaction")
        for name, record in captured.items():
            path = root / name
            info = unpack_snapshot(stat_snapshot(str(path)))
            require(info.size == record["size"] and list(info.identity) == record["identity"]
                    and info.links == record["links"] and _hash(path) == record["sha256"],
                    "Guest identity/link count/length/content changed after compaction")
            if "stream_sha256" in record:
                with Path(str(path) + ":owned-stream").open("rb") as stream:
                    require(hashlib.sha256(stream.read()).hexdigest() == record["stream_sha256"],
                            "Guest named stream changed after compaction")


def compaction_proof(volume: OwnedVolume, captured: dict[str, dict[str, object]]) -> dict:
    """Use the real read-only preview/runtime checks, durable GUI worker/executor and owned guest recheck."""
    disk = find_virtual_disks(scan(volume.image.parent, options=_OPTIONS).root, registrations=[]).rows[0]
    before_identity = unpack_snapshot(disk.snapshot).identity
    plan = prepare_compaction(disk)
    require(plan.info.identifier == volume.identifier, "Reviewed UUID differs from the freshly owned fixture")
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    with tempfile.TemporaryDirectory(prefix="filetree-owned-compaction-audit-") as scratch:
        journal = OperationJournal(Path(scratch))
        worker = DiskCompactionWorker(plan, journal, parent)
        worker.run()  # Explicit owned-fixture approval; native/audit code unchanged, synchronous and joined.
        outcome = worker.result
        require(outcome.compacted and not outcome.error and not worker.journal_errors,
                "Native owned compaction/audit failed: " + outcome.error + " / ".join(worker.journal_errors))
        records = journal.recent().records
        require(len(records) == 1 and records[0].outcome.status == "compacted"
                and records[0].source == disk.path and records[0].identity == before_identity,
                "Durable owned compaction outcome/identity differs")
        require(unpack_snapshot(stat_snapshot(disk.path)).identity == before_identity,
                "Owned backing identity changed after compaction")
        verify_guest(volume, captured)
        parent.deleteLater()
        app.processEvents()
    return {"outcome": asdict(outcome), "guest_records": captured, "guest_full_hashes_and_ids_preserved": True,
            "guest_named_stream_preserved": True, "guest_hard_link_preserved": True,
            "read_only_reattach": True, "production_runtime_checks": True,
            "durable_approval_and_compacted_outcome": True, "guest_used": None}
