"""Run pytest once, retaining native stderr, phase context and the actual child exit."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.pytest_context import write_record

_MAX_PORTABLE_EXIT = 255
# One argv element each, never a shell: letters, digits, spaces and the punctuation of pytest options,
# paths and -k/-m expressions. Quotes, control characters and shell metacharacters are refused.
_SAFE_ARGUMENT = re.compile(r"[\w .,:=@+~/\\()\[\]-]+")
_PLUGIN_OPTION = "-p"
_DISABLE_PLUGIN = "no:"


def evidence_folder(path: Path) -> Path:
    """Resolve a new evidence folder, refusing one outside the directory the runner was started from."""
    resolved = os.path.realpath(path)
    base = os.path.realpath(os.getcwd())
    if not resolved.startswith(base + os.sep):
        raise ValueError(f"evidence folder {str(path)!r} must be inside {base!r}")
    return Path(resolved)


def pytest_arguments(arguments: list[str]) -> list[str]:
    """Validate forwarded pytest arguments; ``-p`` may only disable plugins, never load one."""
    checked, expects_plugin = [], False
    for argument in arguments:
        if not _SAFE_ARGUMENT.fullmatch(argument):
            raise ValueError(f"unsupported pytest argument {argument!r}")
        if expects_plugin:
            plugin = argument  # the value of a separate "-p"
        elif argument.startswith(_PLUGIN_OPTION) and argument != _PLUGIN_OPTION:
            plugin = argument[len(_PLUGIN_OPTION):]  # the joined form "-pno:name"
        else:
            plugin = None
        if plugin is not None and not plugin.startswith(_DISABLE_PLUGIN):
            raise ValueError(f"-p may only disable plugins: {argument!r}")
        expects_plugin = not expects_plugin and argument == _PLUGIN_OPTION
        checked.append(argument)
    if expects_plugin:
        raise ValueError("-p needs a no:<plugin> value")
    return checked


def run_tests(folder: Path, arguments: list[str]) -> int:
    """Use a fresh evidence directory and preserve every nonzero child outcome."""
    folder = evidence_folder(folder)
    arguments = pytest_arguments(arguments)
    folder.mkdir(parents=True, exist_ok=False)
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
