"""Group recorded image signatures by their distance to one representative, without Qt or decoders."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way

HASH_BITS = 64
MAX_DISTANCE = 16
DEFAULT_DISTANCE = 4


class PhotoSearchCancelledError(Exception):
    """The caller stopped image decoding or signature grouping."""


@dataclass(frozen=True, slots=True)
class PhotoSignature:
    """A recorded image and its 64-bit difference hash; it is not proof of equal contents."""

    node: Node
    value: int


@dataclass(frozen=True, slots=True)
class SimilarPhotoGroup:
    """Images within the threshold of the first file; pairwise distances can be larger."""

    files: list[Node]
    distances: list[int]


@dataclass(frozen=True, slots=True)
class SimilarPhotoResult:
    """Heuristic candidates and bounded thumbnails, distinct from verified duplicate decisions."""

    groups: list[SimilarPhotoGroup]
    files_read: int
    skipped: int
    distance: int
    thumbnails: dict[Node, bytes] = field(default_factory=dict, repr=False)
    limited: bool = False


def group_similar(signatures: list[PhotoSignature], distance: int = DEFAULT_DISTANCE,
                  *, cancel: threading.Event | None = None) -> list[SimilarPhotoGroup]:
    """Group by observed representatives, keeping every member within the requested 0..16 bits.

    This deliberately avoids transitive chains: a new image joins only if it matches the group's
    first image. Different pixel colours or unrelated scenes can collide; no group authorizes an
    automatic keeper choice, recoverable-space estimate or removal.
    """
    if not 0 <= distance <= MAX_DISTANCE:
        raise ValueError("Image hash distance must be between 0 and 16")
    check_cancel(cancel)
    index = _HashIndex(distance)
    files: list[list[Node]] = []
    distances: list[list[int]] = []
    for signature in signatures:
        check_cancel(cancel)
        give_way()
        if not 0 <= signature.value < 1 << HASH_BITS:
            raise ValueError("Image signature must contain 64 bits")
        position, score = index.match(signature.value, distance, cancel)
        if position is None:
            index.add(signature.value, len(files), cancel)
            files.append([signature.node])
            distances.append([0])
        else:
            files[position].append(signature.node)
            distances[position].append(score)
    groups = [SimilarPhotoGroup(nodes, scores) for nodes, scores in zip(files, distances, strict=True)
              if len(nodes) > 1]
    groups.sort(key=lambda group: sum(node.size for node in group.files), reverse=True)
    check_cancel(cancel)
    return groups


def check_cancel(cancel: threading.Event | None) -> None:
    """Check a shared stop request between image reads or signature comparisons."""
    if cancel is not None and cancel.is_set():
        raise PhotoSearchCancelledError


class _HashIndex:
    """Disjoint bands: at most d changed bits leave one of d+1 bands unchanged.

    Linear representative search measured 6,000 random hashes at 2.16 s (five-run median,
    2026-10-08). Interleaved BK-tree search was slower (1.62→2.10 s), so this index uses
    unchanged-band candidates at distances 0..8 and a simple linear fallback above that.
    """

    def __init__(self, distance: int) -> None:
        self.values: list[int] = []
        self.bands: list[tuple[int, int]] = []
        if distance <= HASH_BITS // 8:
            width, extra = divmod(HASH_BITS, distance + 1)
            shift = 0
            for position in range(distance + 1):
                bits = width + (position < extra)
                self.bands.append((shift, (1 << bits) - 1))
                shift += bits
        self.buckets: list[dict[int, list[int]]] = [{} for _band in self.bands]

    def add(self, value: int, index: int, cancel: threading.Event | None) -> None:
        check_cancel(cancel)
        self.values.append(value)
        for (shift, mask), bucket in zip(self.bands, self.buckets, strict=True):
            bucket.setdefault((value >> shift) & mask, []).append(index)

    def match(self, value: int, limit: int, cancel: threading.Event | None) -> tuple[int | None, int]:
        candidates: set[int] = set()
        for (shift, mask), bucket in zip(self.bands, self.buckets, strict=True):
            check_cancel(cancel)
            candidates.update(bucket.get((value >> shift) & mask, ()))
        positions = sorted(candidates) if self.bands else range(len(self.values))
        for position in positions:
            check_cancel(cancel)
            score = (self.values[position] ^ value).bit_count()
            if score <= limit:
                return position, score
        return None, 0
