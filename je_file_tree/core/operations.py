"""Revalidate a scan snapshot immediately before each user-approved filesystem operation."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from je_file_tree.core.node import Node, outermost
from je_file_tree.core.lock_holders import LockReport
from je_file_tree.core.pacing import give_way
from je_file_tree.core.protected import Protection, protection_of
from je_file_tree.core.snapshot import Snapshot, stat_snapshot, unpack_snapshot
from je_file_tree.core.system_files import system_file


@dataclass(slots=True)
class MoveReceipt:
    """Platform move result with an optional actual Trash destination."""

    success: bool
    destination: str | None = None


@dataclass(slots=True)
class MoveResult:
    """Separate successes, skipped snapshot entries, platform failures and affected parents."""

    moved: list[Node] = field(default_factory=list)
    skipped: list[tuple[Node, str]] = field(default_factory=list)
    failed: list[Node] = field(default_factory=list)
    parents: list[Node] = field(default_factory=list)
    holders: dict[Node, LockReport] = field(default_factory=dict)
    destinations: dict[Node, str | None] = field(default_factory=dict)
    journal_errors: list[str] = field(default_factory=list)
    copy_errors: list[tuple[str, str, str, str]] = field(default_factory=list)


def revalidate(node: Node, root: Node, *, places: Sequence[Protection] = (),
               approved: Protection | None = None, cancel: threading.Event | None = None,
               snapshot_overrides: dict[tuple[int, int], bytes] | None = None) -> str | None:
    """Return a reason key if the entry changed, escaped, became protected or has incomplete coverage.

    Ancestors retain their scan identity and must not have become links. A selected folder's complete
    descendants and child names are checked too; modifications deep inside it cannot hide behind its
    unchanged aggregate size. This is a no-follow snapshot check, not an OS transaction with Trash.
    snapshot_overrides is reserved for trusted post-rename receipts keyed by inode identity; callers
    must never use it to approve arbitrary metadata changes. Defaults leave scan validation unchanged.
    """
    if node is root or not node.is_in(root):
        return "outside"
    reason = _check_ancestors(node)
    if reason is not None:
        return reason
    reason = _check_location(node, root, places, approved)
    return reason if reason is not None else _check_subtree(node, cancel, snapshot_overrides)


def _check_ancestors(node: Node) -> str | None:
    above = node.parent
    while above is not None:
        reason = _check_node(above, identity_only=True)
        if reason is not None:
            return reason
        if above.is_link:
            return "link"
        above = above.parent
    return None


def _check_location(node: Node, root: Node, places: Sequence[Protection], approved: Protection | None) -> str | None:
    path = node.path
    try:
        parent = os.path.realpath(os.path.dirname(path), strict=True)
        scan_root = os.path.realpath(root.path, strict=True)
        if os.path.commonpath((scan_root, parent)) != scan_root:
            return "outside"
    except OSError:
        return "missing"
    except ValueError:
        return "outside"
    current = protection_of(os.path.join(parent, node.name), places)
    if system_file(os.path.join(parent, node.name)) is not None:
        return 'system_managed'
    if current != approved:
        return "protected"
    return None


def _check_subtree(node: Node, cancel: threading.Event | None,
                   overrides: dict[tuple[int, int], bytes] | None = None) -> str | None:
    stack = [node]
    while stack:
        if cancel is not None and cancel.is_set():
            return "cancelled"
        give_way()
        entry = stack.pop()
        reason = _check_node(entry, overrides=overrides)
        if reason is not None:
            return reason
        if entry.is_dir and not entry.is_link:
            try:
                with os.scandir(entry.path) as children:
                    names = {child.name for child in children}
            except OSError:
                return "unreadable"
            if names != {child.name for child in entry.children}:
                return "changed"
            stack.extend(entry.children)
    return None


def _check_node(node: Node, *, identity_only: bool = False,
                overrides: dict[tuple[int, int], bytes] | None = None) -> str | None:
    if not identity_only and system_file(node.path) is not None:
        return 'system_managed'
    if node.snapshot is None:
        return "unverified"
    if not identity_only and node.error is not None:
        return "incomplete"
    try:
        current = unpack_snapshot(stat_snapshot(node.path))
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"
    before = unpack_snapshot(node.snapshot)
    if overrides and not identity_only:
        before = unpack_snapshot(overrides.get(before.identity, node.snapshot))
    return _changed(node, before, current, identity_only)


def _changed(node: Node, before: Snapshot, current: Snapshot, identity_only: bool) -> str | None:
    if current.is_link != before.is_link or current.is_link != node.is_link:
        return "link"
    if current.mode != before.mode:
        return "kind"
    if before.inode and current.identity != before.identity:
        return "identity"
    if not before.inode:
        return "unverified"
    if not identity_only and (
            current.size, current.modified_ns, current.changed_ns, current.attributes, current.links) != (
                before.size, before.modified_ns, before.changed_ns, before.attributes, before.links):
        return "changed"
    return None


def move_batch(root: Node, nodes: Sequence[Node], mover: Callable[[str], bool | MoveReceipt], *,
               places: Sequence[Protection] = (), approved: dict[Node, Protection | None] | None = None,
               cancel: threading.Event | None = None) -> MoveResult:
    """Revalidate and move an approved batch, keeping failed/skipped nodes attached for later rescans."""
    result = MoveResult()
    approvals = approved or {}
    for node in outermost(nodes):
        if node.parent is not None and node.parent not in result.parents:
            result.parents.append(node.parent)
        reason = revalidate(node, root, places=places, approved=approvals.get(node), cancel=cancel)
        if reason is None:
            # A folder walk can take seconds. Recheck its own entry and ancestors at the actual move boundary.
            reason = (_check_ancestors(node) or _check_location(node, root, places, approvals.get(node))
                      or _check_node(node))
        if reason is not None:
            result.skipped.append((node, reason))
            continue
        try:
            receipt = mover(node.path)
        except OSError:
            receipt = False
        success = receipt.success if isinstance(receipt, MoveReceipt) else receipt
        if success:
            result.destinations[node] = receipt.destination if isinstance(receipt, MoveReceipt) else None
        (result.moved if success else result.failed).append(node)
    return result
