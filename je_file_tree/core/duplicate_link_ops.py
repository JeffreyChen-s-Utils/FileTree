"""Explicit same-volume duplicate linking with exclusive backups, publication and truthful failures."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
import os
import threading
import uuid

from je_file_tree.core.copy_io import _pinned_file, check_cancel, check_file, check_volume, opened_file
from je_file_tree.core.duplicate_decisions import check_group
from je_file_tree.core.duplicate_links import LinkPair, LinkPlan, _attributes, _digests, _streams
from je_file_tree.core.link_io import _remove_alias, _retire_backup
from je_file_tree.core.no_replace import anchored_directory, rename_no_replace
from je_file_tree.core.operations import revalidate
from je_file_tree.core.pacing import give_way
from je_file_tree.core.snapshot import stable_snapshot, stat_snapshot, unpack_snapshot


@dataclass(frozen=True, slots=True)
class LinkOutcome:
    """Observed alias publication and actual retained artifacts, even when retirement/rollback fails."""

    pair: LinkPair
    linked: bool
    error: str = ""
    retained: tuple[str, ...] = ()


@dataclass(slots=True)
class LinkResult:
    """One outcome per preview row and captured affected parents; no guaranteed freed-space amount."""

    outcomes: list[LinkOutcome] = field(default_factory=list)
    parents: tuple[str, ...] = ()
    canceled: bool = False


@dataclass(slots=True)
class _Attempt:
    pair: LinkPair
    temporary: str
    backup: str
    temporary_snapshot: bytes | None = None
    backup_snapshot: bytes | None = None
    linked: bool = False


def _own_change(before: bytes, after: bytes, links: int) -> bytes:
    original, actual = unpack_snapshot(before), unpack_snapshot(after)
    if actual.links != links or replace(actual, changed_ns=original.changed_ns, links=original.links) != original:
        raise ValueError("Native linking observations changed unexpectedly")
    return stable_snapshot(after)


def _checked(plan: LinkPlan, pair: LinkPair, keeper: bytes, cancel: threading.Event | None) -> None:
    if (pair.reason or pair.keeper is None or pair.keeper.path != pair.keeper_path
            or pair.copy.path != pair.copy_path):
        raise ValueError("Reviewed linking paths are stale or refused")
    overrides = {unpack_snapshot(pair.keeper_snapshot).identity: keeper}
    for node in (pair.keeper, pair.copy):
        if reason := revalidate(node, plan.root, places=plan.places, cancel=cancel, snapshot_overrides=overrides):
            raise ValueError("Duplicate linking source refused: " + reason)
    check_file(pair.keeper_path, keeper)
    check_file(pair.copy_path, pair.copy_snapshot)


def _compare(pair: LinkPair, keeper: bytes, cancel: threading.Event | None) -> None:
    with (opened_file(pair.keeper_path, keeper, volume=pair.volume) as source,
          opened_file(pair.copy_path, pair.copy_snapshot, volume=pair.volume) as copied):
        first, original, size = _digests(source, cancel)
        second, other, length = _digests(copied, cancel)
        if first != second or original != pair.digest or other != pair.digest or size != length:
            raise ValueError("Duplicate full payloads differ from their approved decision")
        _attributes(source.fileno(), copied.fileno())
        if os.name == "nt":
            _streams(pair, cancel)


def _link(pair: LinkPair, temporary: str, source: int | None, target: int | None) -> None:
    if os.name == "nt":
        os.link(pair.keeper_path, temporary, follow_symlinks=False)
    elif source is not None and target is not None:
        os.link(os.path.basename(pair.keeper_path), os.path.basename(temporary), src_dir_fd=source,
                dst_dir_fd=target, follow_symlinks=False)
    else:
        raise ValueError("Native linking requires anchored parent descriptors")


def _publish(state: _Attempt, keeper: bytes, source: int | None,
              target: int | None, cancel: threading.Event | None) -> bytes:
    pair = state.pair
    check_cancel(cancel)
    _link(pair, state.temporary, source, target)
    state.temporary_snapshot = stat_snapshot(state.temporary)
    current = _own_change(keeper, stat_snapshot(pair.keeper_path), unpack_snapshot(keeper).links + 1)
    check_file(state.temporary, current)
    check_file(pair.copy_path, pair.copy_snapshot)
    check_cancel(cancel)
    rename_no_replace(pair.copy_path, state.backup, target, target)
    state.backup_snapshot = _own_change(pair.copy_snapshot, stat_snapshot(state.backup), 1)
    check_cancel(cancel)
    rename_no_replace(state.temporary, pair.copy_path, target, target)
    state.linked = True  # A successful native exclusive publication is preserved if later verification fails.
    current = _own_change(current, stat_snapshot(pair.keeper_path), unpack_snapshot(current).links)
    check_file(pair.copy_path, current)
    return current


def _recover(state: _Attempt) -> list[str]:
    errors = []
    pair = state.pair
    try:
        with anchored_directory(pair.copy_parents) as parent:
            check_volume(parent, pair.volume)
            if state.backup_snapshot is None and os.path.lexists(state.backup):
                state.backup_snapshot = _own_change(pair.copy_snapshot, stat_snapshot(state.backup), 1)
            if state.backup_snapshot is not None and not state.linked:
                check_file(state.backup, state.backup_snapshot)
                rename_no_replace(state.backup, pair.copy_path, parent, parent)
                _own_change(state.backup_snapshot, stat_snapshot(pair.copy_path), 1)
    except (OSError, ValueError) as exc:
        errors.append("Exclusive rollback retained actual paths: " + str(exc))
    if state.temporary_snapshot is not None and os.path.lexists(state.temporary):
        try:
            _remove_alias(pair, state.temporary, state.temporary_snapshot)
        except (OSError, ValueError) as exc:
            errors.append("Temporary alias retained: " + str(exc))
    return errors


def _one(plan: LinkPlan, pair: LinkPair, keeper: bytes,
          cancel: threading.Event | None) -> tuple[LinkOutcome, bytes]:
    parent = os.path.dirname(pair.copy_path)
    state = _Attempt(pair, os.path.join(parent, ".filetree-link-" + uuid.uuid4().hex + ".tmp"),
                     os.path.join(parent, ".filetree-copy-" + uuid.uuid4().hex + ".bak"))
    try:
        with (anchored_directory(pair.keeper_parents) as source,
              anchored_directory(pair.copy_parents) as target, _pinned_file(pair.keeper_path)):
            check_volume(source, pair.volume)
            check_volume(target, pair.volume)
            _checked(plan, pair, keeper, cancel)
            _compare(pair, keeper, cancel)
            current = _publish(state, keeper, source, target, cancel)
            _retire_backup(pair, state.backup, state.backup_snapshot, current, cancel)
            check_file(pair.copy_path, current)
            check_file(pair.keeper_path, current)
        return LinkOutcome(pair, True), current
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
        if not state.linked and state.backup_snapshot is not None and not os.path.lexists(state.temporary):
            try:
                state.linked = (unpack_snapshot(stat_snapshot(pair.copy_path)).identity
                                == unpack_snapshot(pair.keeper_snapshot).identity)
            except OSError as observed:
                errors.append("Publication could not be observed: " + str(observed))
        errors.extend(_recover(state))
        retained = tuple(path for path in (state.backup, state.temporary) if os.path.lexists(path))
        return LinkOutcome(pair, state.linked, "; ".join(errors), retained), keeper


def execute_links(plan: LinkPlan, *, cancel: threading.Event | None = None,
                  progress: Callable[[LinkPair], None] | None = None) -> LinkResult:
    """Execute an explicitly reviewed plan; fully rehash before every same-volume replacement.

    Group metadata/handle/content decisions are rechecked before changes. Create a unique temporary
    hard link, exclusively retain the captured old copy as a sibling backup, then publish without
    overwriting arrivals. Fully compare the retained backup again before its scoped native removal.
    Editing any surviving name changes their shared data/metadata; old copies are not kept in Trash.
    Failed operations attempt exclusive rollback and retain/report actual artifacts on collisions.
    Partial published aliases remain linked=True even if verification/retirement fails. Cancel stops
    unstarted work; native calls/rollback are joined. No copy/overwrite or directory-delete fallback.
    Caller must keep the scan tree stable, obtain explicit approval and rescan affected parents.
    """
    result = LinkResult(parents=tuple(sorted({os.path.dirname(path) for pair in plan.pairs
                                            for path in (pair.copy_path, pair.keeper_path) if path})))
    for group in plan.groups:
        give_way()
        pairs = [pair for pair in plan.pairs if pair.copy in group.files]
        reason = ("cancelled" if cancel is not None and cancel.is_set() else
                  check_group(group, plan.root, places=plan.places, cancel=cancel, rehash=True)
                  if any(not pair.reason for pair in pairs) else "")
        keeper = group.kept.snapshot if group.kept is not None else None
        for pair in pairs:
            if pair.reason or reason or cancel is not None and cancel.is_set():
                result.outcomes.append(LinkOutcome(pair, False, pair.reason or reason or "cancelled"))
                continue
            if progress is not None:
                progress(pair)
            outcome, keeper = _one(plan, pair, keeper, cancel)
            result.outcomes.append(outcome)
            if outcome.error:
                reason = "Previous replacement failed; review a fresh scan before remaining copies"
    result.canceled = cancel is not None and cancel.is_set()
    return result
