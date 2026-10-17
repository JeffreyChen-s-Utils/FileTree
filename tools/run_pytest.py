"""Run pytest once, retaining native stderr, phase context and the actual child exit."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.pytest_context import write_record

_MAX_PORTABLE_EXIT = 255


def run_tests(folder: Path, arguments: list[str]) -> int:
    """Use a fresh evidence directory and preserve every nonzero child outcome."""
    folder.mkdir(parents=True, exist_ok=False)
    folder = folder.resolve()
    environment = dict(os.environ, FILETREE_PYTEST_CONTEXT=str(folder), PYTHONFAULTHANDLER="1",
                       PYTHONUNBUFFERED="1", QT_FORCE_STDERR_LOGGING="1")
    command = [sys.executable, "-m", "pytest", *arguments, "-p", "tools.pytest_context",
               "--capture=tee-sys", "-o", "faulthandler_timeout=60"]
    record = {"schema": 1, "state": "starting", "parent_pid": os.getpid(),
              "utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "capture": "tee-sys", "qt_force_stderr_logging": True, "fault_timeout_seconds": 60}
    write_record(folder / "process.json", record)
    started = time.monotonic()
    print(f"pytest evidence: {folder}", flush=True)
    # The interpreter is fixed; remaining arguments are explicitly pytest CLI arguments.
    with ((folder / "output.log").open("xb") as output,
          subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,  # noqa: S603
                           env=environment) as child):
        record.update(state="running", child_pid=child.pid,
                      child_pid_role="Popen process; may be a Windows venv launcher")
        write_record(folder / "process.json", record)
        returncode = child.wait()
    record.update(state="exited", returncode=returncode, elapsed_seconds=time.monotonic() - started)
    write_record(folder / "process.json", record)
    with (folder / "output.log").open("rb") as output:
        shutil.copyfileobj(output, sys.stdout.buffer)
    sys.stdout.buffer.flush()
    # POSIX negative signal return codes cannot be passed directly to sys.exit.
    return returncode if 0 <= returncode <= _MAX_PORTABLE_EXIT else 1


def main() -> int:
    """Accept pytest arguments after an explicit separator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.pytest_args[1:] if args.pytest_args[:1] == ["--"] else args.pytest_args
    return run_tests(args.evidence, arguments)


if __name__ == "__main__":
    raise SystemExit(main())
