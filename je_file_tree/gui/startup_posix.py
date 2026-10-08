"""Exclusive owned desktop/LaunchAgent metadata under anchored, no-follow user directories."""

from __future__ import annotations

from contextlib import contextmanager, suppress
import json
import os
from pathlib import Path
import plistlib
import stat
import sys
import uuid

from je_file_tree.gui.autostart import LABEL, MAX_BYTES, Registration, desktop_entry, launch_agent


def _target() -> Path:
    import pwd  # noqa: PLC0415 - POSIX account data, never an overridden HOME

    if os.getuid() == 0 or os.getuid() != os.geteuid():
        raise OSError("Startup registration requires an unelevated current user")
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    if sys.platform == "darwin":
        return home / "Library" / "LaunchAgents" / (LABEL + ".plist")
    configured = os.environ.get("XDG_CONFIG_HOME")
    folder = Path(configured) if configured else home / ".config"
    if not folder.is_absolute() or ".." in folder.parts:
        raise OSError("Startup configuration directory must be an absolute path without parent components")
    return folder / "autostart" / "je-file-tree-background.desktop"


@contextmanager
def _parent(target: Path, *, create: bool):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(target.anchor, flags)
    try:
        for component in target.parent.parts[1:]:
            if create:
                # Opening below still refuses a linked or non-directory arrival.
                with suppress(FileExistsError):
                    os.mkdir(component, mode=0o700, dir_fd=descriptor)
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
            raise OSError("Startup directory must belong to the current user and not be group/world writable")
        yield descriptor
    finally:
        os.close(descriptor)


def _identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns,
            metadata.st_ctime_ns, metadata.st_nlink, metadata.st_uid, metadata.st_mode)


def _read(parent: int, name: str) -> tuple[bytes, tuple[int, ...]] | None:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    except FileNotFoundError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o022 or metadata.st_size > MAX_BYTES):
            raise OSError("Startup entry is linked, unowned, writable by others or oversized")
        payload = bytearray()
        while len(payload) <= MAX_BYTES:
            part = os.read(descriptor, MAX_BYTES + 1 - len(payload))
            if not part:
                break
            payload.extend(part)
        if len(payload) > MAX_BYTES or _identity(os.fstat(descriptor)) != _identity(metadata):
            raise OSError("Startup entry changed while being read")
        return bytes(payload), _identity(metadata)
    finally:
        os.close(descriptor)


def _owned(payload: bytes) -> None:
    try:
        if sys.platform == "darwin":
            parsed = plistlib.loads(payload)
            expected = launch_agent(tuple(parsed["ProgramArguments"]))
        else:
            rows = payload.decode("utf-8").splitlines()
            receipts = [row.removeprefix("X-FileTree-Arguments=") for row in rows
                        if row.startswith("X-FileTree-Arguments=")]
            if len(receipts) != 1:
                raise ValueError("Missing startup ownership receipt")
            arguments = tuple(json.loads(receipts[0].replace("\\\\", "\\")))
            expected = desktop_entry(arguments)
        if payload != expected:
            raise ValueError("Startup entry differs from its owned canonical metadata")
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError) as error:
        raise OSError("Startup entry belongs to another application or was changed") from error


def inspect() -> Registration:
    """Read strict actual metadata without creating its directories or loading a LaunchAgent."""
    target = _target()
    try:
        with _parent(target, create=False) as parent:
            captured = _read(parent, target.name)
            if captured is not None:
                _owned(captured[0])
    except FileNotFoundError:
        captured = None
    return Registration(captured is not None, str(target))


def _unlink_created(parent: int, name: str, captured: os.stat_result) -> None:
    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if (current.st_dev, current.st_ino) != (captured.st_dev, captured.st_ino) or not stat.S_ISREG(current.st_mode):
        raise OSError("Startup temporary entry changed; retained for review")
    os.unlink(name, dir_fd=parent)


def _check_parent(target: Path, captured: int) -> None:
    with _parent(target, create=False) as current:
        old, fresh = os.fstat(captured), os.fstat(current)
        if (old.st_dev, old.st_ino) != (fresh.st_dev, fresh.st_ino):
            raise OSError("Startup directory changed before registration")


def _publish(parent: int, name: str, payload: bytes) -> None:
    temporary = ".filetree-startup-" + uuid.uuid4().hex
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
    captured = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Exclusive link publication cannot overwrite an entry that arrived after inspection.
        os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
    finally:
        _unlink_created(parent, temporary, captured)
    os.fsync(parent)


def apply(enabled: bool, arguments: tuple[str, ...]) -> Registration:
    """Apply only recognized metadata; removal affects future logins and never kills a running monitor."""
    target = _target()
    payload = (launch_agent(arguments) if sys.platform == "darwin" else desktop_entry(arguments)) if enabled else b""
    if len(payload) > MAX_BYTES:
        raise ValueError("Startup entry exceeds the metadata size limit")
    try:
        with _parent(target, create=enabled) as parent:
            captured = _read(parent, target.name)
            if captured is not None:
                _owned(captured[0])
            _check_parent(target, parent)
            if enabled:
                if captured is None:
                    _publish(parent, target.name, payload)
                elif captured[0] != payload:
                    raise OSError("Remove the previous FileTree startup entry before registering a different program")
            elif captured is not None:
                if _read(parent, target.name) != captured:
                    raise OSError("Startup entry changed before removal")
                os.unlink(target.name, dir_fd=parent)
                os.fsync(parent)
    except FileNotFoundError:
        if enabled:
            raise
    state = inspect()
    if state.installed != enabled:
        raise OSError("Startup registration changed before verification")
    return state
