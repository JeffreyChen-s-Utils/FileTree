"""Reviewable exclusive folder copies; verification alone never moves or deletes an original."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
import os
import stat
import sys
import threading

from je_file_tree.core.copy_io import (
    CopyVolume, check_cancel, check_volume, compare_file, compare_metadata, copy_directory_metadata,
    copy_file, copy_volume,
)
from je_file_tree.core.copy_platform import windows_streams
from je_file_tree.core import namespace_moves
from je_file_tree.core.namespace_moves import NamespaceItem, NamespacePlan, MAX_ITEMS
from je_file_tree.core.no_replace import DirectoryStamp, anchored_directory, directory_stamps
from je_file_tree.core.node import Node, outermost
from je_file_tree.core.mounts import mount_points
from je_file_tree.core.operations import revalidate
from je_file_tree.core.pacing import give_way
from je_file_tree.core.protected import Protection, protected_places, protection_of
from je_file_tree.core.snapshot import stable_snapshot, stat_snapshot, unpack_snapshot

_UNAVAILABLE = 0x400 | 0x1000 | 0x40000 | 0x400000


@dataclass(frozen=True, slots=True)
class CopyProof:
    """Verified ordinary-folder destination and captured source plan; always reverify before Trash approval."""

    plan: NamespacePlan
    item: NamespaceItem
    destination: tuple[DirectoryStamp, ...]
    files: int
    bytes: int
    volume: CopyVolume


@dataclass(slots=True)
class CopyResult:
    """Successful verified copies, skipped/failed pairs and retained partial destination paths."""

    verified: list[CopyProof] = field(default_factory=list)
    skipped: list[tuple[NamespaceItem, str]] = field(default_factory=list)
    failed: list[tuple[NamespaceItem, str]] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)
    canceled: bool = False


def _readable(root: Node, node: Node, places: Sequence[Protection], cancel: threading.Event | None) -> str:
    if not node.is_dir or node.is_link:
        return "folder_required"
    reason = revalidate(node, root, places=places, approved=protection_of(node.path, places), cancel=cancel)
    if reason:
        return reason
    mounts = mount_points() if sys.platform.startswith("linux") else ()
    for entry in node.iter_nodes():
        check_cancel(cancel)
        info = unpack_snapshot(entry.snapshot)
        if (entry.is_link or info.is_link or info.attributes & _UNAVAILABLE
                or not (stat.S_ISREG(info.mode) or stat.S_ISDIR(info.mode)) or os.path.normpath(entry.path) in mounts):
            return "copy_unsupported"
        if os.name == "nt" and entry.is_dir and windows_streams(entry.path):
            return "directory_streams"
    return ""


def prepare_copy(root: Node, nodes: Sequence[Node], directory: str, *, collision: str = "skip",
                 cancel: threading.Event | None = None) -> NamespacePlan | None:
    """Preview 1–1000 selections for exclusive folder copies, including cross-volume destinations.

    Sources may be protected ordinary folders; their eventual Trash approval remains MainWindow's
    responsibility. Linked/special/cloud/partial sources and protected/descendant/colliding targets are
    refused. Explicit suffix choices are frozen in the preview. Does not read payloads or create paths.
    """
    if not nodes or len(nodes) > MAX_ITEMS or collision not in ("skip", "rename") or not directory:
        raise ValueError("Review 1–1000 folders and one existing destination directory")
    sources, places, reserved = outermost(nodes), tuple(protected_places()), set()
    items = []
    for number, node in enumerate(sources, 1):
        if cancel is not None and cancel.is_set():
            return None
        give_way()
        item = namespace_moves._prepare_item(root, node, (directory, None, collision, number),
                                               (sources, places, reserved), cancel)
        try:
            if item.reason in ("", "volume", "protected"):
                if not item.reason:
                    reserved.discard(os.path.normcase(item.destination))
                reason = _readable(root, node, places, cancel)
                if not reason:
                    reason = namespace_moves._target_reason(item.source, item.destination, node, sources,
                                                             places, reserved, item.target_ancestors)
                    reason = "" if reason == "volume" else reason
                    # Volume refusal precedes collision checking in namespace-only plans.
                    if not reason and (os.path.lexists(item.destination)
                                       or os.path.normcase(item.destination) in reserved):
                        reason = "collision"
                item = replace(item, reason=reason)
                if not reason:
                    reserved.add(os.path.normcase(item.destination))
        except (OSError, ValueError) as exc:
            item = replace(item, reason="error", detail=str(exc))
        items.append(item)
    return None if cancel is not None and cancel.is_set() else NamespacePlan(root, tuple(items), places)


def _source(plan: NamespacePlan, item: NamespaceItem, cancel: threading.Event | None) -> None:
    if item.node.path != item.source or item.node.snapshot != item.snapshot:
        raise ValueError("Captured source changed in the result tree")
    reason = _readable(plan.root, item.node, plan.places, cancel)
    if reason:
        raise ValueError(reason)


def _target(item: NamespaceItem, entry: Node) -> str:
    relative = os.path.relpath(entry.path, item.source)
    if relative == ".":
        return item.destination
    if relative == ".." or relative.startswith(".." + os.sep) or os.path.isabs(relative):
        raise ValueError("Copy entry escaped the reviewed folder")
    return os.path.join(item.destination, relative)


def _mkdir(path: str, volume: CopyVolume) -> None:
    with anchored_directory(directory_stamps(os.path.dirname(path))) as parent:
        check_volume(parent, volume)
        if parent is None:
            os.mkdir(path)
        else:
            os.mkdir(os.path.basename(path), mode=0o700, dir_fd=parent)


def _copy_entries(item: NamespaceItem, cancel: threading.Event | None,
                  progress: Callable[[str, int, int], None] | None, volume: CopyVolume) -> None:
    directories = []
    done = 0
    for entry in item.node.iter_nodes():
        check_cancel(cancel)
        target = _target(item, entry)
        if entry.is_dir:
            give_way()
            if entry is not item.node:
                _mkdir(target, volume)
            directories.append((entry.path, target))
        else:
            copy_file(entry.path, target, entry.snapshot, cancel, volume=volume)
            done += 1
            if progress is not None:
                progress(entry.path, done, item.node.file_count)
    for source, destination in reversed(directories):
        copy_directory_metadata(source, destination, cancel, volume=volume)


def copy_folders(plan: NamespacePlan, *, cancel: threading.Event | None = None,
                 progress: Callable[[str, int, int], None] | None = None) -> CopyResult:
    """Copy confirmed eligible folders exclusively and verify them; never Trash/delete/unlink originals.

    Failure stops this batch, preserves every original and retains partial destinations visibly.
    Cancellation also retains partial data. A CopyProof is an observation, not permission to remove
    anything; the GUI must reverify through its existing MainWindow.move_to_trash approval/worker flow.
    """
    result = CopyResult()
    for item in plan.items:
        if cancel is not None and cancel.is_set():
            result.canceled = True
            break
        if item.reason:
            result.skipped.append((item, item.reason))
            continue
        created = False
        try:
            with (anchored_directory(item.ancestors), anchored_directory(item.target_ancestors) as parent):
                _source(plan, item, cancel)
                reason = namespace_moves._target_reason(item.source, item.destination, item.node, (item.node,),
                                                        plan.places, set(), item.target_ancestors)
                if reason not in ("", "volume") or os.path.lexists(item.destination):
                    raise ValueError(reason or "collision")
                volume = copy_volume(parent, unpack_snapshot(item.target_ancestors[-1].snapshot).device)
                _mkdir(item.destination, volume)
                created = True
                destination = directory_stamps(item.destination)
                with anchored_directory(destination) as descriptor:
                    check_volume(descriptor, volume)
                    _copy_entries(item, cancel, progress, volume)
                    proof = CopyProof(plan, item, destination, item.node.file_count, item.node.size, volume)
                    verify_copy(proof, cancel=cancel)
                    result.verified.append(proof)
        except (OSError, ValueError) as exc:
            result.failed.append((item, str(exc)))
            if created:
                result.partial.append(item.destination)
            break
    result.canceled |= cancel is not None and cancel.is_set()
    return result


def verify_copy(proof: CopyProof, *, cancel: threading.Event | None = None) -> None:
    """Recheck full source coverage and exact destination topology, lengths and hashes below 64 MiB.

    Windows named streams are also enumerated/compared; unsupported enumeration prevents approval.
    Files at/above the limit are length-verified only. Never grants deletion permission or guarantees
    future stability. Call again immediately before the existing approved Trash operation.
    """
    item, plan = proof.item, proof.plan
    with (anchored_directory(item.ancestors), anchored_directory(proof.destination) as descriptor):
        check_volume(descriptor, proof.volume)
        _source(plan, item, cancel)
        files = size = 0
        for entry in item.node.iter_nodes():
            check_cancel(cancel)
            target = _target(item, entry)
            if entry.is_dir:
                _compare_directory(entry, target, proof.volume)
            else:
                compare_file(entry.path, target, entry.snapshot, cancel, volume=proof.volume)
                files += 1
                size += entry.size
        if (files, size) != (proof.files, proof.bytes):
            raise ValueError("Copied file count/size differs")
        _source(plan, item, cancel)
        if item.snapshot is None or stable_snapshot(stat_snapshot(item.source)) != stable_snapshot(item.snapshot):
            raise ValueError("Source changed at verification boundary")


def _compare_directory(entry: Node, target: str, volume: CopyVolume) -> None:
    give_way()
    with anchored_directory(directory_stamps(target)) as descriptor:
        check_volume(descriptor, volume)
        with os.scandir(descriptor if descriptor is not None else target) as children:
            names = {child.name for child in children}
        if names != {child.name for child in entry.children}:
            raise ValueError("Copied directory child names/count differ")
        if os.name == "nt" and windows_streams(target):
            raise ValueError("Unexpected destination directory streams")
        if os.name != "nt":
            with anchored_directory(directory_stamps(entry.path)) as source:
                compare_metadata(source, descriptor)
