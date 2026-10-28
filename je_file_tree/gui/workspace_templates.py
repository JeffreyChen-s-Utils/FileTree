"""Strict, versioned named multi-tab inputs, separate from restart and scan results."""

from dataclasses import dataclass
import json
import ntpath
import os
from pathlib import PureWindowsPath

from PySide6.QtCore import QSettings

from je_file_tree.gui.startup_state import WorkspaceState, decode_workspace_state, encode_workspace_state

TEMPLATES_KEY = "workspace_templates_v1"
MAX_TEMPLATES = 32
MAX_PAYLOAD = 1024 * 1024
MAX_NAME = 80
_FIRST_PRINTABLE = 32


@dataclass(frozen=True, slots=True)
class TabImpact:
    """One existing tab affected by replacement, captured without walking its tree."""

    title: str
    scope: str | tuple[str, ...] | None
    active: bool
    scanning: bool
    has_result: bool


@dataclass(frozen=True, slots=True)
class ReplacementImpact:
    """Live affected tabs in visual order; independent of the saved opening snapshot."""

    tabs: tuple[TabImpact, ...] = ()


def absolute_root(path: str) -> bool:
    """Require native absolute paths; Windows accepts drive-rooted or UNC paths, never bare roots."""
    if not path or "\0" in path:
        return False
    if os.name != "nt":
        return os.path.isabs(path)
    drive, _tail = ntpath.splitdrive(path)
    drive = drive.replace("/", "\\")
    return (PureWindowsPath(path).is_absolute() and not drive.startswith(("\\\\?", "\\\\."))
            and (drive.startswith("\\\\") or drive[0].isalpha()))



@dataclass(frozen=True, slots=True)
class WorkspaceTemplate:
    """A name and immutable public next-scan choices; never contains scan results or approvals."""

    name: str
    state: WorkspaceState

    def __post_init__(self) -> None:
        if (not isinstance(self.name, str) or not self.name.strip() or self.name != self.name.strip()
                or len(self.name) > MAX_NAME or any(ord(char) < _FIRST_PRINTABLE for char in self.name)
                or not isinstance(self.state, WorkspaceState) or self.state.options is None):
            raise ValueError("Invalid workspace template")
        for scope in self.state.tabs:
            roots = scope if isinstance(scope, tuple) else (scope,) if scope is not None else ()
            if not all(absolute_root(root) for root in roots):
                raise ValueError("Workspace template roots must be absolute")


def _fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate workspace template fields")
    return result


def _validate(items: tuple[WorkspaceTemplate, ...]) -> None:
    if (type(items) is not tuple or len(items) > MAX_TEMPLATES
            or not all(isinstance(item, WorkspaceTemplate) for item in items)
            or len({item.name.casefold() for item in items}) != len(items)):
        raise ValueError("Invalid or duplicate workspace templates")


def read_templates(settings: QSettings) -> tuple[WorkspaceTemplate, ...]:
    """Reject malformed settings without rewriting them or interpreting paths against the current directory."""
    raw = settings.value(TEMPLATES_KEY)
    if raw is None:
        return ()
    if not isinstance(raw, str) or len(raw) > MAX_PAYLOAD:
        raise ValueError("Invalid workspace template data")
    try:
        value = json.loads(raw, object_pairs_hook=_fields)
    except (ValueError, RecursionError) as error:
        raise ValueError("Invalid workspace template data") from error
    if (not isinstance(value, dict) or set(value) != {"version", "templates"}
            or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["templates"], list) or len(value["templates"]) > MAX_TEMPLATES):
        raise ValueError("Unsupported workspace template data")
    items = []
    for item in value["templates"]:
        if not isinstance(item, dict) or set(item) != {"name", "state"}:
            raise ValueError("Invalid workspace template fields")
        items.append(WorkspaceTemplate(item["name"], decode_workspace_state(item["state"])))
    result = tuple(items)
    _validate(result)
    return result


def write_templates(settings: QSettings, items: tuple[WorkspaceTemplate, ...]) -> None:
    """Validate the complete replacement before writing a single dedicated settings value."""
    _validate(items)
    payload = json.dumps({"version": 1, "templates": [
        {"name": item.name, "state": encode_workspace_state(item.state)} for item in items]}, ensure_ascii=False)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("Workspace template data is too large")
    settings.setValue(TEMPLATES_KEY, payload)
