"""Compare raw MFT metadata only on a freshly created private NTFS image; preserve every fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core import mft  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.core.mft_reader import NTFSReader  # noqa: E402
from je_file_tree.core.windows_allocation import file_allocation  # noqa: E402
from tools.validate_windows_volume import _fixtures, _write  # noqa: E402
from tools.windows_owned_volume import owned_ntfs_volume, require, verify_volume  # noqa: E402

_DOS_NAMESPACE = 2


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _capture(paths: list[Path]) -> dict[str, tuple]:
    result = {}
    for path in paths:
        info = path.lstat()
        result[str(path)] = (info.st_dev, info.st_ino, info.st_size, info.st_nlink, _digest(path))
    return result


def _observe(native: NTFSReader, path: Path) -> dict:
    info = path.lstat()
    record = native.record(info.st_ino & ((1 << 48) - 1))
    require(record.reference == info.st_ino and record.in_use and not record.base_reference,
            "Native file reference/sequence differs from raw record")
    attributes = native.attributes(record)
    names = [mft.parse_file_name(item.value) for item in attributes if item.kind == mft.FILE_NAME]
    parent = path.parent.lstat()
    require(any(item.name == path.name and item.parent == parent.st_ino and item.namespace != _DOS_NAMESPACE
                for item in names),
            "Raw name/parent reference differs from native path")
    heads = [item for item in attributes if item.kind == mft.DATA and not item.name and item.lowest_vcn == 0]
    require(len(heads) == 1 and heads[0].size == info.st_size, "Raw unnamed size differs from native file")
    allocation = file_allocation(str(path), info)
    # MFT resident DATA owns no separate clusters; FILE_STANDARD_INFO reports its resident byte length.
    expected_allocation = heads[0].size if heads[0].resident else heads[0].allocated
    require(allocation is not None and expected_allocation == allocation,
            f"Raw unnamed allocation differs from native FILE_STANDARD_INFO: {path.name}; "
            f"raw={heads[0].allocated}, native={allocation}, resident={heads[0].resident}, "
            f"flags={heads[0].flags}, logical={heads[0].size}, expected_native={expected_allocation}")
    standard = [mft.parse_standard_information(item.value) for item in attributes
                if item.kind == mft.STANDARD_INFORMATION]
    require(len(standard) == 1 and standard[0].modified_ns == info.st_mtime_ns,
            "Raw standard modified time differs from native file")
    require(record.links == info.st_nlink, "Raw link count differs from native file")
    require(all(item.value is None for item in attributes if item.kind == mft.DATA),
            "DATA payload was retained in parsed metadata")
    return {"reference": record.reference, "names": len(names), "links": record.links,
            "size": heads[0].size, "raw_allocated": heads[0].allocated, "native_allocated": allocation,
            "resident": heads[0].resident,
            "attribute_list": any(item.kind == mft.ATTRIBUTE_LIST for item in attributes),
            "named_streams": [{"name": item.name, "size": item.size, "allocated": item.allocated}
                              for item in attributes if item.kind == mft.DATA and item.name and not item.lowest_vcn]}


def _proof(volume) -> dict:
    root = _fixtures(volume)
    verify_volume(volume)
    tiny = root / "resident.bin"
    _write(tiny, b"private resident fixture")
    stream = Path(str(tiny) + ":owned")
    _write(stream, b"private named stream")
    for size in (0, 1, 7, 9, 31, 127):
        _write(root / f"resident-{size:03}.bin", b"r" * size)
    linked = root / "extensions.bin"
    _write(linked, b"private extension fixture" * 4096)
    for index in range(128):
        os.link(linked, root / (f"alias-{index:03}-" + "long-name-" * 8 + ".bin"))
    paths = sorted(root.iterdir())
    before = _capture([*paths, stream])
    observations = {}
    with NTFSReader(str(root)) as native:
        for path in paths:
            observations[path.name] = _observe(native, path)
        require(observations[tiny.name]["resident"] and observations[tiny.name]["named_streams"],
                "Fresh fixture did not exercise resident/named metadata")
        require(observations[linked.name]["attribute_list"], "Fresh aliases did not exercise MFT extensions")
        references = {item.reference for item in native.records() if item.in_use and not item.base_reference}
        require(all(item[1] in references for name, item in before.items() if name != str(stream)),
                "Bounded raw streaming omitted a fresh native file reference")
        native.verify()
    verify_volume(volume)
    require(_capture([*paths, stream]) == before, "MFT observations changed fixture identity/data/streams")
    return {"files": observations, "source_preserved": True, "stream_preserved": True,
            "raw_stream_complete": True, "scanner_enabled": False}


def main() -> None:
    """Persist bounded metadata evidence across phases; never accept an existing disk or source path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    evidence = {"phase": "starting", "platform": sys.platform, "cleanup_verified": False}

    def save():
        with _atomic_file(options.output, encoding="utf-8") as stream:
            json.dump(evidence, stream, ensure_ascii=False, indent=2)

    save()
    try:
        with owned_ntfs_volume() as volume:
            evidence.update(phase="reading", owned_volume=str(volume.root))
            save()
            evidence.update(_proof(volume))
            evidence["phase"] = "validated"
            save()
        evidence.update(phase="complete", cleanup_verified=True)
    except (OSError, ValueError, RuntimeError) as error:
        evidence.update(phase="failed", error=str(error))
        save()
        raise
    save()


if __name__ == "__main__":
    main()
