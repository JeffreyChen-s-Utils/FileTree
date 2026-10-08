"""Prove native metadata feeds using exclusively fresh, owned disposable sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.change_watch import ChangeBatch, watch  # noqa: E402
from je_file_tree.core.scanner import scan  # noqa: E402


def _case(scratch: Path, *, external: bool = False) -> dict:
    source = scratch / ("external" if external else "來源")
    branch = source / "資料"
    branch.mkdir(parents=True)
    kept = source / "保留.bin"
    kept.write_bytes(b"owned unchanged source" * 1024)
    before = (kept.stat().st_ino, hashlib.sha256(kept.read_bytes()).hexdigest())
    target = branch / "event.bin"
    if external:
        target.write_bytes(b"owned shared content")
        alias = scratch / "outside-alias"
        os.link(target, alias)
        target = alias
    root = scan(source).root
    cancel, ready, arrived = threading.Event(), threading.Event(), threading.Event()
    backends, batches, errors = [], [], []

    def changed(batch: ChangeBatch) -> None:
        batches.append({"folders": batch.folders, "full": batch.full, "reason": batch.reason})
        if str(branch) in batch.folders or batch.full:
            arrived.set()

    def initialized(backend: str) -> None:
        backends.append(backend)
        ready.set()

    def run() -> None:
        try:
            watch(root, changed, cancel, ready=initialized)
        except (OSError, ValueError, UnicodeError) as error:
            errors.append(str(error))
            ready.set()

    worker = threading.Thread(target=run)
    worker.start()
    try:
        if not ready.wait(15) or errors or not backends:
            raise RuntimeError(f"Native setup failed: {errors}")
        with target.open("wb") as stream:
            stream.write(b"fresh owned event" * 2048)
            stream.flush()
            os.fsync(stream.fileno())
        if not arrived.wait(15) or errors:
            raise RuntimeError(f"Native event missing: {backends}, {batches}, {errors}")
    finally:
        cancel.set()
        worker.join(15)
        if worker.is_alive():
            raise RuntimeError("Native watcher did not join; retain owned sources")
    after = (kept.stat().st_ino, hashlib.sha256(kept.read_bytes()).hexdigest())
    if before != after or target.read_bytes() != b"fresh owned event" * 2048:
        raise RuntimeError("Owned source preservation failed")
    return {"backends": backends, "batches": batches, "joined": True,
            "kept_identity_sha256": before, "source_preserved": True, "external_alias": external}


def validate(output: Path) -> None:
    """Accept only an evidence destination, never an existing source/volume/bin selector."""
    evidence = {"phase": "starting", "platform": sys.platform, "owned_fixture_cleanup": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = None
    try:
        if not (sys.platform == "win32" or sys.platform.startswith("linux")):
            raise RuntimeError("Native change-feed validation requires Windows or Linux")
        scratch = tempfile.TemporaryDirectory(prefix="filetree-watch-owned-")
        evidence["owned_source"] = scratch.name
        evidence["ordinary"] = _case(Path(scratch.name))
        if sys.platform.startswith("linux"):
            evidence["external_alias"] = _case(Path(scratch.name), external=True)
        scratch.cleanup()
        evidence["owned_fixture_cleanup"] = True
        evidence["phase"] = "complete"
    except (OSError, ValueError, RuntimeError) as error:
        evidence["error"] = str(error)
        if scratch is not None:
            # Failed native lifetime checks retain fixtures while their thread may still use them.
            scratch._finalizer.detach()
        raise
    finally:
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    validate(parser.parse_args().output)
