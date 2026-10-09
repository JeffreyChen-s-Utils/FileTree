"""Pillow-backed image signatures/thumbnails outside the standard-library-only core."""

from __future__ import annotations

import io
import threading
from collections.abc import Callable

from PIL import Image, ImageOps, UnidentifiedImageError

from je_file_tree.core.analysis import CATEGORY_EXTENSIONS, extension_of
from je_file_tree.core.archives import _opened
from je_file_tree.core.node import Node
from je_file_tree.core.pacing import give_way
from je_file_tree.core.similar_photos import (
    DEFAULT_DISTANCE, PhotoSignature, SimilarPhotoResult, check_cancel, group_similar,
)
from je_file_tree.core.snapshot import unpack_snapshot

MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_PHOTOS = 100_000
MAX_THUMBNAILS = 1000
THUMBNAIL_SIZE = (80, 80)
HASH_SIZE = (9, 8)
_FORMATS = ("JPEG", "PNG", "WEBP", "GIF", "TIFF", "BMP", "ICO", "DIB", "PPM", "PSD", "TGA", "AVIF")
_READ_ERRORS = (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError)
PhotoProgress = Callable[[int, int], None]


def _image(node: Node, cancel: threading.Event | None) -> tuple[int, bytes]:
    check_cancel(cancel)
    if node.size > MAX_SOURCE_BYTES:
        raise OSError("Image exceeds the 128 MiB source limit")
    with _opened(node) as stream, Image.open(stream, formats=_FORMATS) as original:
        if original.width * original.height > MAX_PIXELS:
            raise OSError("Image exceeds the 40 million pixel limit")
        original.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        image = ImageOps.exif_transpose(original).convert("RGB")
        check_cancel(cancel)
        gray = image.convert("L").resize(HASH_SIZE, Image.Resampling.LANCZOS)
        pixels = gray.tobytes()
        value = 0
        for row in range(8):
            for column in range(8):
                value = (value << 1) | (pixels[row * 9 + column] > pixels[row * 9 + column + 1])
        target = io.BytesIO()
        image.save(target, format="PNG")
        result = value, target.getvalue()
    check_cancel(cancel)
    return result


def find_similar_photos(root: Node, *, min_size: int = 1024 * 1024, distance: int = DEFAULT_DISTANCE,
                       cancel: threading.Event | None = None,
                       progress: PhotoProgress | None = None) -> SimilarPhotoResult:
    """Decode only recorded image types on a worker; retain at most 1,000 display thumbnails.

    Refuse changed/link/cloud sources, cap candidate count/source bytes/pixels, use first animation
    frame with EXIF orientation and report failures. Stop waits through the current decoder call.
    """
    group_similar([], distance, cancel=cancel)  # Validate before reading any source.
    if min_size < 1:
        raise ValueError("Minimum image size must be positive")
    signatures, identities = [], set()
    skipped, limited = 0, False
    for node in root.iter_files():
        check_cancel(cancel)
        give_way()
        if node.size < min_size or extension_of(node.name) not in CATEGORY_EXTENSIONS["images"]:
            continue
        if len(signatures) == MAX_PHOTOS:
            limited = True
            break
        if node.snapshot is not None:
            identity = unpack_snapshot(node.snapshot).identity
            if identity[1] and identity in identities:
                continue
        else:
            identity = (0, 0)
        try:
            value, _thumbnail = _image(node, cancel)
        except _READ_ERRORS:
            skipped += 1
        else:
            identities.add(identity)
            signatures.append(PhotoSignature(node, value))
        if progress is not None:
            progress(len(signatures), skipped)
    groups = group_similar(signatures, distance, cancel=cancel)
    thumbnails, failed = _thumbnails(groups, cancel)
    check_cancel(cancel)
    return SimilarPhotoResult(groups, len(signatures), skipped + failed, distance, thumbnails, limited)


def _thumbnails(groups, cancel: threading.Event | None) -> tuple[dict[Node, bytes], int]:
    thumbnails: dict[Node, bytes] = {}
    attempts, skipped = 0, 0
    for group in groups:
        for node in group.files:
            if attempts == MAX_THUMBNAILS:
                break
            attempts += 1
            try:
                _value, thumbnails[node] = _image(node, cancel)
            except _READ_ERRORS:
                skipped += 1
        if attempts == MAX_THUMBNAILS:
            break
    return thumbnails, skipped
