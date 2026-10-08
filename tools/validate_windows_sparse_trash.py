"""Compare sparse Qt Trash lengths on only a newly owned 2 GiB VHDX; no disk/path selector."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.validate_windows_volume import _save  # noqa: E402
from tools.windows_owned_volume import owned_ntfs_volume  # noqa: E402
from tools.windows_sparse_trash_probe import sparse_trash_proof  # noqa: E402

_CAPACITY = 2048 * 1024 * 1024


def main() -> int:
    """Create the fixed larger private disk, retain partial observations and confirm owned cleanup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evidence = {"fresh_owned_disk": True, "virtual_capacity": _CAPACITY,
                "phase": "before_create", "owned_disk_detached_and_removed": False}
    _save(args.output, evidence)
    def record(name: str, result: dict) -> None:
        evidence.setdefault("sparse_trash_diagnostic", {})[name] = result
        evidence["phase"] = "sparse_trash_" + name
        _save(args.output, evidence)
    with owned_ntfs_volume(capacity=_CAPACITY) as volume:
        evidence.update(native_device=volume.physical, volume_id=volume.volume_id)
        root = volume.root / "owned-fixtures"
        root.mkdir()
        sparse_trash_proof(volume, root, record)
    evidence.update(phase="complete", owned_disk_detached_and_removed=True)
    _save(args.output, evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
