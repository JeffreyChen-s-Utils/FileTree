"""Read-only exact hard-link replacement previews and complete duplicate-payload verification."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
import hashlib
import os
import stat
import sys
import threading
from typing import BinaryIO

from je_file_tree.core.copy_io import CopyVolume, check_cancel, check_volume, copy_volume, opened_file
from je_file_tree.core.copy_platform import mac_xattrs, windows_streams
from je_file_tree.core.duplicate_decisions import check_group
from je_file_tree.core.duplicates import DuplicateGroup
from je_file_tree.core.no_replace import DirectoryStamp, anchored_directory, directory_stamps
from je_file_tree.core.node import Node
from je_file_tree.core.operations import revalidate
from je_file_tree.core.pacing import give_way
from je_file_tree.core.protected import Protection, protected_places
from je_file_tree.core.snapshot import pack_snapshot, stable_snapshot, unpack_snapshot

MAX_LINKS = 1000
_MIN_COPIES = 2
_CHUNK = 1024 * 1024
_ATTRIBUTE_LIMIT = 64 * 1024 * 1024
_UNAVAILABLE = 0x400 | 0x1000 | 0x40000 | 0x400000


@dataclass(frozen=True, slots=True)
class LinkPair:
    """Frozen kept/copy paths and scan/handle/parent observations; a reason marks a refused row."""

    keeper: Node | None
    copy: Node
    keeper_path: str
    copy_path: str
    keeper_snapshot: bytes | None
    copy_snapshot: bytes | None
    keeper_proof: bytes | None
    copy_proof: bytes | None
    keeper_parents: tuple[DirectoryStamp, ...] = ()
    copy_parents: tuple[DirectoryStamp, ...] = ()
    volume: CopyVolume | None = None
    reason: str = ""
    digest: bytes | None = None


@dataclass(frozen=True, slots=True)
class LinkPlan:
    """Read-only replacement rows from explicit duplicate keepers; nodes must remain in the same tree."""

    root: Node
    groups: tuple[DuplicateGroup, ...]
    pairs: tuple[LinkPair, ...]
    places: tuple[Protection, ...]


@dataclass(frozen=True, slots=True)
class LinkVerification:
    """Full payload comparison, never a deletion/linking permission or a concurrent transaction."""

    pair: LinkPair
    digest: bytes
    bytes_read: int


def _ordinary(node: Node) -> str:
    if node.snapshot is None:
        return "unverified"
    info = unpack_snapshot(node.snapshot)
    if (node.is_dir or node.is_link or info.is_link or not stat.S_ISREG(info.mode) or info.attributes & _UNAVAILABLE
            or not info.device or not info.inode):
        return "link_unsupported"
    return "duplicate_hard_links" if info.links != 1 else ""


def _row(group: DuplicateGroup, copy: Node, reason: str) -> LinkPair:
    keeper = group.kept
    return LinkPair(keeper, copy, keeper.path if keeper is not None else "", copy.path,
                    keeper.snapshot if keeper is not None else None, copy.snapshot,
                    group.proofs.get(keeper), group.proofs.get(copy), reason=reason, digest=group.digest)


def _parents(pair: LinkPair) -> LinkPair:
    if pair.reason:
        return pair
    try:
        if unpack_snapshot(pair.keeper_snapshot).device != unpack_snapshot(pair.copy_snapshot).device:
            return replace(pair, reason="volume")
        keeper = directory_stamps(os.path.dirname(pair.keeper_path))
        copied = directory_stamps(os.path.dirname(pair.copy_path))
        with anchored_directory(keeper) as source, anchored_directory(copied) as target:
            volume = copy_volume(source, unpack_snapshot(pair.keeper_snapshot).device)
            check_volume(target, volume)
        return replace(pair, keeper_parents=keeper, copy_parents=copied, volume=volume)
    except (OSError, ValueError) as exc:
        return replace(pair, reason=str(exc))


def prepare_links(root: Node, groups: Sequence[DuplicateGroup], *,
                  cancel: threading.Event | None = None) -> LinkPlan | None:
    """Preview at most 1,000 extra-copy rows without reading payloads, linking or deleting anything.

    Require explicit keepers and recorded duplicate digest/handle proofs. Protected, changed, unknown,
    linked, special, cloud/offline and already hard-linked members refuse their entire decision.
    Other-volume/bind-mount extras remain visible refused rows. Member overlap is rejected; all paths,
    snapshots and groups are frozen before later verification. Cancellation returns None.
    """
    if (not groups or any(len(group.files) < _MIN_COPIES for group in groups)
            or sum(len(group.files) for group in groups) > 2 * MAX_LINKS):
        raise ValueError("Review at most 1,000 duplicate replacements")
    if sum(len(group.files) - (group.kept in group.files) for group in groups) > MAX_LINKS:
        raise ValueError("Review at most 1,000 duplicate replacements")
    members = [node for group in groups for node in group.files]
    if len(set(members)) != len(members) or len({os.path.normcase(node.path) for node in members}) != len(members):
        raise ValueError("Duplicate decisions overlap")
    places, frozen, pairs = tuple(protected_places()), [], []
    for original in groups:
        give_way()
        if cancel is not None and cancel.is_set():
            return None
        group = replace(original, files=list(original.files), proofs=dict(original.proofs))
        reason = next((value for node in group.files if (value := _ordinary(node))), "")
        reason = reason or check_group(group, root, places=places, cancel=cancel) or ""
        frozen.append(group)
        pairs.extend(_parents(_row(group, node, reason)) for node in group.files if node is not group.kept)
    return None if cancel is not None and cancel.is_set() else LinkPlan(root, tuple(frozen), tuple(pairs), places)


def _digests(stream: BinaryIO, cancel: threading.Event | None) -> tuple[bytes, bytes, int]:
    before = pack_snapshot(os.fstat(stream.fileno()))
    remaining = total = unpack_snapshot(before).size
    sha, duplicate = hashlib.sha256(), hashlib.blake2b(digest_size=16)
    while remaining:
        check_cancel(cancel)
        block = stream.read(min(_CHUNK, remaining))
        if not block:
            raise ValueError("Duplicate stream ended before its recorded length")
        sha.update(block)
        duplicate.update(block)
        remaining -= len(block)
        give_way()
    if stream.read(1) or stable_snapshot(pack_snapshot(os.fstat(stream.fileno()))) != stable_snapshot(before):
        raise ValueError("Duplicate stream changed during complete comparison")
    return sha.digest(), duplicate.digest(), total


def _streams(pair: LinkPair, cancel: threading.Event | None) -> int:
    before = windows_streams(pair.keeper_path)
    if before != windows_streams(pair.copy_path):
        raise ValueError("Duplicate alternate-stream names/lengths differ")
    total = 0
    for name, _size in before:
        if name == "::$DATA":
            continue
        with open(pair.keeper_path + name, "rb") as source, open(pair.copy_path + name, "rb") as copied:
            first, _, size = _digests(source, cancel)
            second, _, other = _digests(copied, cancel)
            if first != second or size != other:
                raise ValueError("Duplicate alternate-stream contents differ")
            total += size + other
    if before != windows_streams(pair.keeper_path) or before != windows_streams(pair.copy_path):
        raise ValueError("Duplicate alternate-stream inventory changed")
    return total


def _attributes(source: int, target: int) -> None:
    if sys.platform == "darwin":
        first, second = mac_xattrs(source, _ATTRIBUTE_LIMIT), mac_xattrs(target, _ATTRIBUTE_LIMIT)
        if first != second or any(value is None for _name, _size, value in first):
            raise ValueError("Duplicate native attributes/resource forks differ or exceed full-verification bounds")
    elif hasattr(os, "listxattr"):
        names = sorted(os.listxattr(source))
        if names != sorted(os.listxattr(target)):
            raise ValueError("Duplicate extended-attribute names differ")
        for name in names:
            if os.getxattr(source, name) != os.getxattr(target, name):
                raise ValueError("Duplicate extended-attribute contents differ")


def verify_link_pair(plan: LinkPlan, pair: LinkPair, *,
                     cancel: threading.Event | None = None) -> LinkVerification:
    """Revalidate the exact preview and read/hash both complete main payloads and every Windows ADS.

    Every size is fully SHA-256 compared, with the original duplicate BLAKE2 digest checked too;
    there is no length-only large-file/stream fallback. Compare POSIX attributes strictly; native
    macOS attributes/resource forks at/above 64 MiB are refused. Parent/volume/mount and exact
    recorded handle/path snapshots must remain unchanged throughout. Does not replace/delete/link.
    A later executor must recheck again; this read-only result grants no mutation permission.
    """
    check_cancel(cancel)
    if (pair not in plan.pairs or pair.reason or pair.keeper is None or pair.digest is None
            or pair.keeper.path != pair.keeper_path or pair.copy.path != pair.copy_path):
        raise ValueError("Duplicate linking preview is refused or no longer matches its paths")
    for node in (pair.keeper, pair.copy):
        if reason := revalidate(node, plan.root, places=plan.places, cancel=cancel):
            raise ValueError("Duplicate linking source refused: " + reason)
    with (anchored_directory(pair.keeper_parents) as keeper_parent,
          anchored_directory(pair.copy_parents) as copy_parent):
        check_volume(keeper_parent, pair.volume)
        check_volume(copy_parent, pair.volume)
        with (opened_file(pair.keeper_path, pair.keeper_snapshot, volume=pair.volume) as source,
              opened_file(pair.copy_path, pair.copy_snapshot, volume=pair.volume) as copied):
            if (pack_snapshot(os.fstat(source.fileno())) != pair.keeper_proof
                    or pack_snapshot(os.fstat(copied.fileno())) != pair.copy_proof):
                raise ValueError("Duplicate opened-file proof changed")
            digest, original, size = _digests(source, cancel)
            other, original_other, length = _digests(copied, cancel)
            if digest != other or original != pair.digest or original_other != pair.digest or size != length:
                raise ValueError("Duplicate complete contents differ from the recorded decision")
            _attributes(source.fileno(), copied.fileno())
            streams = _streams(pair, cancel) if os.name == "nt" else 0
    check_cancel(cancel)
    return LinkVerification(pair, digest, size + length + streams)
