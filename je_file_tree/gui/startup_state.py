"""Bounded, read-only scan scopes for an administrator workspace restart."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from je_file_tree.core.multi_scan import MAX_ROOTS

if TYPE_CHECKING:
    from je_file_tree.gui.workspace import ScanWorkspace

MAX_TABS = 16
_PREFIX = "--restore-workspace="
_MAX_PAYLOAD = 1024 * 1024
ScanScope = str | tuple[str, ...] | None


def _valid_scope(scope: ScanScope) -> bool:
    if scope is None:
        return True
    roots = (scope,) if isinstance(scope, str) else scope
    return (type(roots) is tuple and 1 <= len(roots) <= MAX_ROOTS
            and all(isinstance(root, str) and root != "" and "\0" not in root for root in roots))


def _scope(value: object) -> ScanScope:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(root, str) for root in value):
        return tuple(value)
    raise ValueError("Invalid scan scope in workspace restart data")


def _fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate workspace restart fields")
    return result


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    """Keep blank/single/combined tabs distinct; restore scans without operation approvals."""

    tabs: tuple[ScanScope, ...]
    active: int = 0

    def __post_init__(self) -> None:
        if (type(self.tabs) is not tuple or not 1 <= len(self.tabs) <= MAX_TABS
                or not all(_valid_scope(scope) for scope in self.tabs)
                or type(self.active) is not int or not 0 <= self.active < len(self.tabs)):
            raise ValueError("Invalid workspace restart scope or active tab")

    def arguments(self) -> list[str]:
        """Use the existing single-folder command when it preserves the complete scope."""
        if len(self.tabs) == 1:
            scope = self.tabs[0]
            if scope is None:
                return []
            if isinstance(scope, str) and not scope.startswith("-"):
                return [scope]
        payload = json.dumps({"version": 1, "tabs": self.tabs, "active": self.active},
                             ensure_ascii=False, separators=(",", ":"))
        if len(payload) > _MAX_PAYLOAD:
            raise ValueError("Workspace restart data is too large")
        return [_PREFIX + payload]

    def restore(self, workspace: ScanWorkspace) -> None:
        """Populate a fresh workspace, then rescan each explicit scope and select the active tab."""
        if workspace.tabs.count() != 1:
            raise ValueError("Workspace restoration requires a fresh tab")
        windows = [workspace.current]
        for _scope_value in self.tabs[1:]:
            window = workspace.add_tab()
            if window is None:
                raise ValueError("Workspace tab could not be restored")
            windows.append(window)
        for window, scope in zip(windows, self.tabs, strict=True):
            if isinstance(scope, str):
                window.start_scan(scope)
            elif scope is not None:
                window.start_scan_roots(scope)
        workspace.tabs.setCurrentIndex(self.active)


def workspace_state(arguments: Sequence[str]) -> WorkspaceState | None:
    """Decode internal restart metadata before approval, preserving ordinary folder/background arguments."""
    values = [argument[len(_PREFIX):] for argument in arguments if argument.startswith(_PREFIX)]
    if "--restore-workspace" in arguments:
        raise ValueError("Workspace restart data is missing")
    if not values:
        return None
    if len(values) != 1 or any(not argument.startswith("-") for argument in arguments):
        raise ValueError("Ambiguous workspace restart arguments")
    if len(values[0]) > _MAX_PAYLOAD:
        raise ValueError("Workspace restart data is too large")
    try:
        value = json.loads(values[0], object_pairs_hook=_fields)
    except (ValueError, RecursionError) as error:
        raise ValueError("Invalid workspace restart data") from error
    if (not isinstance(value, dict) or set(value) != {"version", "tabs", "active"}
            or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["tabs"], list)):
        raise ValueError("Unsupported workspace restart data")
    return WorkspaceState(tuple(_scope(scope) for scope in value["tabs"]), value["active"])
