"""Verify literal-file lsof reporting on a fresh held file, without mounting an image."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import tempfile

from je_file_tree.core.export import _atomic_file
from tools import macos_busy_observer as observer

_PAYLOAD = b"FileTree owned literal-file observer probe\n"


def _native() -> None:
    if sys.platform != "darwin" or not os.getuid() or os.getuid() != os.geteuid():
        raise ValueError("Unelevated native macOS required")


def validate(output: Path) -> None:
    """Keep native output and cleanup truth even if the backend or PID check fails."""
    _native()
    if output.exists():
        raise ValueError("Existing observer evidence refused")
    output.parent.mkdir(parents=True, exist_ok=True)
    proof = {"phase": "started", "pid": os.getpid(), "mounts_created": False,
             "busy_cause_established": False, "owned_fixture_cleanup": False}
    try:
        with tempfile.NamedTemporaryFile(prefix="filetree-lsof-owned-", mode="w+b") as stream:
            path = Path(stream.name).resolve(strict=True)
            stream.write(_PAYLOAD)
            stream.flush()
            before = os.fstat(stream.fileno())
            proof["owned_file"] = str(path)
            result = observer._run(["/usr/sbin/lsof", "-nP", "-F0pcftn", "-f", "--", str(path)],
                                   observer._CLOCK() + 2, 65536)
            proof["lsof"] = {**result.summary(), "stdout_base64": base64.b64encode(result.stdout).decode("ascii")}
            fields = [field.lstrip(b"\n") for field in result.stdout.split(b"\0")]
            proof["own_pid_reported"] = ("p" + str(os.getpid())).encode("ascii") in fields
            stream.seek(0)
            after = os.fstat(stream.fileno())
            proof["source_preserved"] = (before.st_dev, before.st_ino, before.st_size) == (
                after.st_dev, after.st_ino, after.st_size) and stream.read() == _PAYLOAD
            if (result.returncode != 0 or result.timed_out or result.stdout_truncated or result.stderr_truncated
                    or not proof["own_pid_reported"] or not proof["source_preserved"]):
                raise RuntimeError("Literal-file observer did not verify the owned held file")
        proof.update(phase="verified", owned_fixture_cleanup=True)
    except (OSError, ValueError, RuntimeError) as error:
        proof.update(phase="failed", error=str(error)[:2048])
        raise
    finally:
        path_value = proof.get("owned_file")
        if path_value is not None:
            proof["owned_fixture_cleanup"] = not Path(path_value).exists()
        with _atomic_file(output, encoding="utf-8") as stream:
            json.dump(proof, stream, indent=2)
            stream.write("\n")


def main() -> int:
    """Write proof for a disposable native query; never detach or change a user volume."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    validate(parser.parse_args().output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
