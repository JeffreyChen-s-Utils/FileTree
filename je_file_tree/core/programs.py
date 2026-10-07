"""Read-only Windows uninstall registrations and bounded game manifests matched to recorded folders."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
import stat
import re
import sys
import threading

from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.duplicates import _check_snapshot
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import pack_snapshot, stat_snapshot

if sys.platform == "win32":
    import winreg

_UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
_REGISTRY_LIMIT = 20000
_MANIFEST_LIMIT = 10000
_TEXT_LIMIT = 1024 * 1024
_ROW_LIMIT = 1000
_TOKEN_LIMIT = 65536
_MAX_DEPTH = 64
_MAX_DWORD = 0xffffffff
_MAX_SIZE = (1 << 63) - 1
_FIELD_LIMIT = 4096
_STEAM = re.compile(r"appmanifest_([0-9]+)\.acf\Z", re.IGNORECASE)
_KV_TOKEN = re.compile(r'\s+|//[^\n]*(?:\n|$)|"(?:[^"\\]|\\.)*"|[{}]')


@dataclass(frozen=True, slots=True)
class Program:
    """A reported installation; matched folder totals remain snapshots, not an uninstall-space promise."""

    name: str
    version: str
    publisher: str
    source: str
    location: str
    reported: int | None
    node: Node | None = None
    complete: bool = False


@dataclass(frozen=True, slots=True)
class Programs:
    """Bounded rows, full discovered count and explicit unavailable/malformed/omitted metadata count."""

    rows: list[Program]
    count: int
    issues: int


def _stopped(cancel: threading.Event | None) -> bool:
    return cancel is not None and cancel.is_set()


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) and len(value) <= _FIELD_LIMIT and "\0" not in value else ""


def _location(value: object) -> str:
    text = os.path.expandvars(_text(value).strip('"'))
    return os.path.normpath(text) if text and os.path.isabs(text) else ""


def _field(key, name: str) -> object:
    try:
        return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return None  # optional fields are often absent and remain unknown


def _registration(key) -> Program | None:
    name = _text(_field(key, "DisplayName"))
    if not name or _field(key, "SystemComponent") == 1:
        return None
    amount = _field(key, "EstimatedSize")
    reported = amount * 1024 if type(amount) is int and 0 <= amount <= _MAX_DWORD else None
    return Program(name, _text(_field(key, "DisplayVersion")), _text(_field(key, "Publisher")), "registry",
                   _location(_field(key, "InstallLocation")), reported)


def _registry_view(hive, view: int, cancel: threading.Event | None) -> tuple[list[Program], int] | None:
    rows, issues = [], 0
    try:
        key = winreg.OpenKey(hive, _UNINSTALL, 0, winreg.KEY_READ | view)
    except FileNotFoundError:
        return rows, issues
    except OSError:
        return rows, 1
    with key:
        try:
            count = winreg.QueryInfoKey(key)[0]
        except OSError:
            return rows, 1
        issues += max(0, count - _REGISTRY_LIMIT)
        for position in range(min(count, _REGISTRY_LIMIT)):
            if _stopped(cancel):
                return None
            give_way()
            try:
                name = winreg.EnumKey(key, position)
                with winreg.OpenKey(key, name, 0, winreg.KEY_READ | view) as child:
                    program = _registration(child)
                    if program is not None:
                        rows.append(program)
            except OSError:
                issues += 1
    return rows, issues


def registered_programs(*, cancel: threading.Event | None = None) -> Programs | None:
    """Read HKLM/HKCU 32/64-bit views only; never read or execute uninstall commands."""
    if _stopped(cancel):
        return None
    if sys.platform != "win32":
        return Programs([], 0, 0)
    rows, issues = {}, 0
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            result = _registry_view(hive, view, cancel)
            if result is None:
                return None
            found, errors = result
            issues += errors
            for program in found:
                identity = (program.name, program.version, program.publisher, os.path.normcase(program.location),
                            program.reported)
                rows[identity] = program
    return Programs(list(rows.values()), len(rows), issues)


def _manifest_text(node: Node) -> str:
    if node.snapshot is None or node.error is not None or node.is_link or node.is_dir or node.size > _TEXT_LIMIT:
        raise ValueError("Manifest is unavailable, linked or exceeds 1 MiB")
    _check_snapshot(node, stat_snapshot(node.path))
    with open(node.path, "rb") as stream:
        opened = pack_snapshot(os.fstat(stream.fileno()))
        _check_snapshot(node, opened, descriptor=True)
        contents = stream.read(_TEXT_LIMIT + 1)
        if len(contents) != node.size or pack_snapshot(os.fstat(stream.fileno())) != opened:
            raise ValueError("Manifest changed while reading")
    _check_snapshot(node, stat_snapshot(node.path))
    return contents.decode("utf-8-sig")


def _kv_tokens(contents: str) -> list[tuple[bool, str]]:
    tokens, position = [], 0
    for match in _KV_TOKEN.finditer(contents):
        if match.start() != position:
            raise ValueError("Unsupported manifest syntax")
        piece = match.group()
        position = match.end()
        if piece.startswith('"'):
            tokens.append((False, re.sub(r'\\(["\\])', r'\1', piece[1:-1])))
        elif piece in ("{", "}"):
            tokens.append((True, piece))
        if len(tokens) > _TOKEN_LIMIT:
            raise ValueError("Manifest has too many fields")
    if position != len(contents):
        raise ValueError("Truncated manifest syntax")
    return tokens


def _key_values(contents: str) -> dict:
    root, key = {}, None
    stack = [root]
    for brace, value in _kv_tokens(contents):
        if brace and value == "{":
            if key is None or key in stack[-1] or len(stack) >= _MAX_DEPTH:
                raise ValueError("Invalid manifest nesting")
            child = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        elif brace:
            if key is not None or len(stack) <= 1:
                raise ValueError("Invalid manifest closing brace")
            stack.pop()
        elif key is None:
            key = value
        else:
            if key in stack[-1]:
                raise ValueError("Duplicate manifest key")
            stack[-1][key], key = value, None
    if key is not None or len(stack) != 1:
        raise ValueError("Incomplete manifest")
    return root


def _steam(node: Node) -> Program:
    state = _key_values(_manifest_text(node)).get("AppState")
    match = _STEAM.fullmatch(node.name)
    if not isinstance(state, dict) or state.get("appid") != match[1]:
        raise ValueError("Steam manifest ID does not match its filename")
    folder, name = _text(state.get("installdir")), _text(state.get("name"))
    if not name or not folder or folder in (".", "..") or any(char in folder for char in ("/", "\\")):
        raise ValueError("Steam installation name/directory is unavailable")
    location = os.path.join(node.parent.path, "common", folder)
    return Program(name, _text(state.get("buildid")), "", "steam", location, None)


def _epic(node: Node) -> Program:
    document = json.loads(_manifest_text(node))
    if not isinstance(document, dict):
        raise ValueError("Epic manifest is not an object")
    name, location = _text(document.get("DisplayName")), _location(document.get("InstallLocation"))
    if not name or not location:
        raise ValueError("Epic manifest has no installation name/location")
    amount = document.get("InstallSize")
    reported = amount if type(amount) is int and 0 <= amount <= _MAX_SIZE else None
    return Program(name, _text(document.get("AppVersionString")), "", "epic", location, reported)


def _manifest_kind(node: Node) -> str | None:
    if node.is_dir or node.parent is None:
        return None
    if _STEAM.fullmatch(node.name) and os.path.basename(node.parent.path).casefold() == "steamapps":
        return "steam"
    if node.name.casefold().endswith(".item"):
        parent_path = node.parent.path.replace("\\", "/").rstrip("/").casefold()
        if parent_path.endswith("/epicgameslauncher/data/manifests"):
            return "epic"
    return None


def _external_epic(cancel: threading.Event | None) -> tuple[list[Program], int] | None:
    """Read only the launcher's fixed ProgramData metadata directory, never its installation contents."""
    if sys.platform != "win32":
        return [], 0
    data = _location(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    if not data:
        return [], 1
    path = os.path.join(data, "Epic", "EpicGamesLauncher", "Data", "Manifests")
    rows, issues, examined = [], 0, 0
    try:
        folder = os.lstat(path)
        if not stat.S_ISDIR(folder.st_mode) or getattr(folder, "st_file_attributes", 0) & 0x400:
            return [], 1
        with os.scandir(path) as entries:
            for entry in entries:
                if _stopped(cancel):
                    return None
                if not entry.name.casefold().endswith(".item"):
                    continue
                examined += 1
                if examined > _MANIFEST_LIMIT:
                    issues += 1
                    break
                give_way()
                try:
                    info = os.lstat(entry.path)
                    node = Node(entry.path, stat.S_ISDIR(info.st_mode), size=info.st_size,
                                is_link=stat.S_ISLNK(info.st_mode), snapshot=pack_snapshot(info))
                    rows.append(_epic(node))
                except (OSError, ValueError, UnicodeError, RecursionError):
                    issues += 1
    except FileNotFoundError:
        return [], 0
    except OSError:
        issues += 1
    return rows, issues


def _scanned_games(root: Node, cancel: threading.Event | None) -> tuple[list[Program], int] | None:
    rows, issues, manifests = [], 0, 0
    for node in root.iter_nodes():
        if _stopped(cancel):
            return None
        if node.is_dir:
            give_way()
        kind = _manifest_kind(node)
        if kind is None:
            continue
        manifests += 1
        if manifests > _MANIFEST_LIMIT:
            issues += 1
            continue
        try:
            rows.append(_steam(node) if kind == "steam" else _epic(node))
        except (OSError, ValueError, UnicodeError, RecursionError):
            issues += 1
    return rows, issues


def installed_programs(root: Node, *, partial: bool = False,
                       cancel: threading.Event | None = None) -> Programs | None:
    """Match reports only to exact recorded folders; no extra install-folder scan or recursive registry walk.

    Read at most 1 MiB per recognized scanned game manifest, with snapshot/cloud/link guards, plus the
    fixed Windows Epic metadata location. Stop discards the result. Shared/nested installation folders
    can overlap; row totals must not be summed. Registrations omit some packaged/portable apps and
    reported sizes are estimates, never a promise of recoverable data.
    """
    registered = registered_programs(cancel=cancel)
    if registered is None:
        return None
    rows, issues = list(registered.rows), registered.issues
    for found in (_external_epic(cancel), _scanned_games(root, cancel)):
        if found is None:
            return None
        rows.extend(found[0])
        issues += found[1]
    rows = list({(row.source, row.name, row.version, os.path.normcase(row.location), row.reported): row
                 for row in rows}.values())
    wanted = {os.path.normcase(row.location) for row in rows if row.location}
    folders, stack = {}, [root]
    while stack:
        if _stopped(cancel):
            return None
        give_way()
        node = stack.pop()
        key = os.path.normcase(os.path.normpath(node.path))
        if not node.is_link and key in wanted:
            folders[key] = node
        stack.extend(child for child in node.children if child.is_dir and not child.is_link)
    coverage = coverage_of(root, cancel=cancel)
    if coverage is None:
        return None
    matched = []
    for row in rows:
        node = folders.get(os.path.normcase(row.location))
        matched.append(replace(row, node=node, complete=not partial and node is not None and coverage.can_clean(node)))
    matched.sort(key=lambda row: (-(row.node.size if row.node is not None else row.reported or 0), row.name.casefold()))
    return Programs(matched[:_ROW_LIMIT], len(matched), issues)
