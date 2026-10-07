"""Validate native freedesktop undo using fresh private fixtures, never existing OS Trash scopes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.core.mounts import mount_points  # noqa: E402
from je_file_tree.core.snapshot import stat_snapshot  # noqa: E402
from je_file_tree.core.trash_restore import capture_origin, prepare_restore, restore  # noqa: E402


def require(condition: bool, message: str) -> None:
    """Fail the probe on any missing preservation/identity evidence."""
    if not condition:
        raise RuntimeError(message)


def native_case(case: str) -> dict[str, bool]:
    """Use only paths created by this invocation in its newly owned scratch directory."""
    with tempfile.TemporaryDirectory(prefix="filetree-undo-owned-") as scratch:
        owned = Path(scratch).resolve(strict=True)
        data = owned / "data"
        scope = data / "Trash"
        scope.mkdir(parents=True, mode=0o700)
        files, info = scope / "files", scope / "info"
        files.mkdir(mode=0o700)
        info.mkdir(mode=0o700)
        os.environ["XDG_DATA_HOME"] = str(data)
        source = owned / "original"
        (source / "empty").mkdir(parents=True)
        (source / "file").write_bytes(b"fresh owned undo bytes")
        digest = hashlib.sha256((source / "file").read_bytes()).hexdigest()
        origin = capture_origin(str(source), stat_snapshot(str(source)))
        payload = files / "payload"
        source.rename(payload)
        receipt = info / "payload.trashinfo"
        receipt.write_text(f"[Trash Info]\nPath={quote(str(source))}\nDeletionDate=2026-10-08T00:00:00\n",
                           encoding="utf-8")
        roots = [point for point in mount_points() if os.path.commonpath((str(owned), point)) == point]
        volume = max(roots, key=len)
        plan = prepare_restore(origin, str(payload), volume)
        if case == "collision":
            source.mkdir()
            (source / "arrival").write_bytes(b"arrival retained")
        elif case == "changed":
            (payload / "file").write_bytes(b"changed owned bytes")
        elif case == "parent":
            info.rename(scope / "old-info")
            info.mkdir(mode=0o700)
        result = restore(plan)
        if case == "success":
            require(result.restored and not result.error and not result.receipt_retained, "Native restore refused")
            require(hashlib.sha256((source / "file").read_bytes()).hexdigest() == digest, "Restored bytes differ")
            require((source / "empty").is_dir() and not payload.exists() and not receipt.exists(),
                    "Payload/receipt/empty-folder state differs")
        else:
            require(not result.restored and bool(result.error) and result.receipt_retained, "Unsafe restore succeeded")
            require(payload.is_dir(), "Refused payload disappeared")
            if case == "collision":
                require((source / "arrival").read_bytes() == b"arrival retained", "Arrival overwritten")
            else:
                require(not source.exists(), "Refusal created the original path")
            actual_receipt = scope / "old-info" / receipt.name if case == "parent" else receipt
            require(actual_receipt.is_file(), "Refused receipt disappeared")
        require(files.is_dir() and info.is_dir() and scope.is_dir(), "OS-bin containers removed")
        return {"passed": True, "native_rename": True, "containers_preserved": True, "only_fresh_owned_paths": True}


def main() -> None:
    """Write an atomic native proof artifact without Qt, network calls, elevation or actual user bins."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        raise ValueError("Native Linux descriptor and mount APIs required")
    previous = os.environ.get("XDG_DATA_HOME")
    try:
        proof = {case: native_case(case) for case in ("success", "collision", "changed", "parent")}
    finally:
        if previous is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = previous
    with _atomic_file(args.output, encoding="utf-8") as stream:
        json.dump(proof, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
