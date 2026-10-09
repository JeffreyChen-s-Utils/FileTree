"""Bounded native process/WSL observations before reviewed detached-disk compaction."""

import ctypes
from dataclasses import dataclass
import os
import subprocess
import tempfile
import threading

from je_file_tree.core.compression_ops import _kernel
from je_file_tree.core.copy_io import check_cancel
from je_file_tree.core.virtual_disk_sources import registered_disks
from je_file_tree.core.virtual_disks import VirtualDisk, _key

_PROCESSES = 16384
_OUTPUT = 65536
_END = 18
_NAME_LIMIT = 4096
_PRINTABLE = 32
_GUESTS = frozenset({"docker desktop.exe", "com.docker.backend.exe", "com.docker.service.exe",
                    "vmwp.exe", "vmmem.exe", "vmmemwsl.exe", "vmware-vmx.exe", "virtualboxvm.exe",
                    "vboxheadless.exe", "qemu-system-x86_64.exe", "qemu-system-aarch64.exe"})


class _Process(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint32), ("usage", ctypes.c_uint32), ("pid", ctypes.c_uint32),
               ("heap", ctypes.c_size_t), ("module", ctypes.c_uint32), ("threads", ctypes.c_uint32),
               ("parent", ctypes.c_uint32), ("priority", ctypes.c_int32), ("flags", ctypes.c_uint32),
               ("name", ctypes.c_uint16 * 260)]


@dataclass(frozen=True, slots=True)
class DiskRuntime:
    """Provider path/name signature and fresh absence of known guest processes/running WSL guests.

    Observations are conservative and not a lock against another program starting a machine. The
    user must additionally confirm that its owning machine is stopped throughout the operation.
    """

    registration: tuple[tuple[str, str, str | None], ...]


def _process_names(cancel: threading.Event | None) -> set[str]:
    kernel = _kernel()
    kernel.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    kernel.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    for name in ("Process32FirstW", "Process32NextW"):
        function = getattr(kernel, name)
        function.argtypes, function.restype = [ctypes.c_void_p, ctypes.POINTER(_Process)], ctypes.c_int32
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry, names = _Process(), set()
        entry.size = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        for _number in range(_PROCESSES):
            check_cancel(cancel)
            if not more:
                if ctypes.get_last_error() != _END:
                    raise ctypes.WinError(ctypes.get_last_error())
                return names
            units = list(entry.name)
            if 0 not in units:
                raise ValueError("Native process name is truncated")
            raw = bytes(entry.name)[:units.index(0) * 2]
            names.add(raw.decode("utf-16-le").casefold())
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
        raise ValueError("Native process inventory exceeds the review bound")
    finally:
        kernel.CloseHandle(handle)


def _wsl_program() -> str:
    kernel = _kernel()
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel.GetSystemDirectoryW(buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise OSError("Windows system directory unavailable")
    return os.path.join(buffer.value, "wsl.exe")


def _decode_running(raw: bytes) -> tuple[str, ...]:
    if len(raw) > _OUTPUT:
        raise ValueError("WSL running inventory exceeds the review bound")
    text = raw.decode("utf-16-le" if b"\0" in raw or raw.startswith(b"\xff\xfe") else "utf-8-sig")
    names = tuple(line.strip().removeprefix("\ufeff") for line in text.splitlines() if line.strip(" \t\ufeff"))
    if any(not name or len(name) > _NAME_LIMIT or any(ord(character) < _PRINTABLE for character in name)
           for name in names):
        raise ValueError("WSL running inventory contains malformed names")
    return names


def _running_wsl(required: bool, cancel: threading.Event | None) -> tuple[str, ...]:
    if not required:
        return ()  # No current-user WSL registration; other-user guest workers are checked natively.
    program = _wsl_program()
    if not os.path.isfile(program):
        if required:
            raise ValueError("Registered WSL provider has no fixed system runtime query")
        return ()
    check_cancel(cancel)
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run([program, "--list", "--running", "--quiet"], stdout=output,  # noqa: S603
                                    stderr=subprocess.STDOUT, timeout=10, check=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("WSL running-state query timed out") from exc
        check_cancel(cancel)
        if result.returncode:
            raise ValueError("WSL running-state query failed; stop state is unknown")
        output.seek(0)
        return _decode_running(output.read(_OUTPUT + 1))


def stopped_runtime(disk: VirtualDisk, *, cancel: threading.Event | None = None) -> DiskRuntime:
    """Require complete current-user providers, no known guest workers and no running WSL guests.

    Query only Toolhelp process metadata and fixed System32 wsl.exe --list --running --quiet, with
    bounded output/time and no shell/distro launch/shutdown. Any unknown, changed registered source,
    omitted inventory or known worker refuses compaction. Docker backend/service processes must be
    absent, even for custom disks found by scanning. The native provider separately checks detachment.
    Native snapshots are observational; absence does not replace the user's stopped-machine review.
    """
    check_cancel(cancel)
    if os.name != "nt":
        raise ValueError("Virtual-disk runtime checks require Windows")
    registrations = registered_disks(cancel=cancel)
    check_cancel(cancel)
    if registrations is None or registrations.issues:
        raise ValueError("Virtual-disk provider inventory is incomplete")
    signature = tuple(sorted((row.source, row.name, row.distro) for row in registrations.rows
                             if _key(row.path) == _key(disk.path)))
    if disk.source != "scan" and (disk.source, disk.name, disk.distro) not in signature:
        raise ValueError("Registered virtual-disk source changed")
    if _process_names(cancel) & _GUESTS:
        raise ValueError("A known virtual-machine/Docker process is running; stop it before review")
    if _running_wsl(any(row.source == "wsl" for row in registrations.rows), cancel):
        raise ValueError("A WSL guest is running; stop it before review")
    check_cancel(cancel)
    return DiskRuntime(signature)
