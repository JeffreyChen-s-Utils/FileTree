"""Exact folder budgets evaluated only from a completed scan tree."""

from __future__ import annotations

import os
import ntpath
import threading
from dataclasses import dataclass
from pathlib import PureWindowsPath

from je_file_tree.core.coverage import Coverage
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

MAX_RULES = 256
MAX_BYTES = (1 << 63) - 1
WINDOWS_DRIVE_LENGTH = 2
EXTENDED_DRIVE_LENGTH = 6


def budget_path(path: str) -> str:
    """Return a native absolute identity without resolving links or reading the source."""
    if not isinstance(path, str) or not path or "\0" in path or not os.path.isabs(path):
        raise ValueError("Budget path must be absolute")
    if os.name == "nt":
        drive, _tail = ntpath.splitdrive(path)
        drive = drive.replace("/", "\\")
        extended_drive = (drive.startswith("\\\\?\\") and len(drive) >= EXTENDED_DRIVE_LENGTH
                          and drive[4].isalpha() and drive[5] == ":")
        extended_unc = drive.lower().startswith("\\\\?\\unc\\")
        ordinary = (not drive.startswith(("\\\\?", "\\\\."))
                    and (drive.startswith("\\\\") or
                         len(drive) == WINDOWS_DRIVE_LENGTH and drive[0].isalpha()))
        if not PureWindowsPath(path).is_absolute() or not (ordinary or extended_drive or extended_unc):
            raise ValueError("Budget path must be a native absolute directory")
    return os.path.normcase(os.path.normpath(path))


def _inside(path: str, ancestor: str) -> bool:
    try:
        return os.path.commonpath((path, ancestor)) == ancestor
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class BudgetRule:
    """One durable target and its exact byte ceiling."""

    identity: str
    version: int
    name: str
    path: str
    limit: int

    def __post_init__(self) -> None:
        budget_path(self.path)
        if (not isinstance(self.identity, str) or not self.identity
                or type(self.version) is not int or self.version < 1
                or not isinstance(self.name, str) or not self.name.strip()
                or type(self.limit) is not int or not 0 <= self.limit <= MAX_BYTES):
            raise ValueError("Invalid folder budget rule")


@dataclass(frozen=True, slots=True)
class BudgetTicket:
    """Rules and globally ordered sequence captured before a scan starts."""

    sequence: int
    rules: tuple[BudgetRule, ...]


@dataclass(frozen=True, slots=True)
class BudgetObservation:
    """A known byte count or an explicit unknown reason, without a Node reference."""

    identity: str
    version: int
    sequence: int
    measured_at: float
    bytes: int | None
    reason: str | None

    @property
    def known(self) -> bool:
        """Whether the observed target had complete coverage."""
        return self.bytes is not None


@dataclass(frozen=True, slots=True)
class BudgetBatch:
    """Observations from one successful complete top-level or scheduled scan."""

    observations: tuple[BudgetObservation, ...]


def observe_budgets(root: Node, coverage: Coverage, ticket: BudgetTicket,
                    measured_at: float, cancel: threading.Event | None = None) -> BudgetBatch | None:
    """Match bounded paths in one folder walk and preserve missing targets as unknown."""
    if not ticket.rules:
        return BudgetBatch(())
    sources = root.children if root.path is None else (root,)
    source_paths = tuple(_observed_path(source.path) for source in sources if source.path is not None)
    relevant = {budget_path(rule.path): rule for rule in ticket.rules
                if any(_inside(budget_path(rule.path), source) for source in source_paths)}
    found: dict[str, Node] = {}
    stack = list(sources)
    while stack and len(found) < len(relevant):
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        node = stack.pop()
        if node.path is not None:
            key = _observed_path(node.path)
            if key in relevant:
                found[key] = node
            if node.is_dir and not node.is_link:
                stack.extend(node.children)
    if cancel is not None and cancel.is_set():
        return None
    observations = []
    for path, rule in relevant.items():
        size, reason = _measurement(found.get(path), coverage)
        observations.append(BudgetObservation(rule.identity, rule.version, ticket.sequence,
                                              measured_at, size, reason))
    return BudgetBatch(tuple(observations))


def _measurement(node: Node | None, coverage: Coverage) -> tuple[int | None, str | None]:
    if node is None:
        return None, "missing"
    if node.is_link:
        return None, "linked"
    if not node.is_dir:
        return None, "not_folder"
    if not coverage.can_clean(node):
        return None, "incomplete"
    return node.size, None


def _observed_path(path: str) -> str:
    """Compare scanned names without treating a source path as a user-created rule."""
    return os.path.normcase(os.path.normpath(path))
