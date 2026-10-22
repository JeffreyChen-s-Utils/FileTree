"""Measure Windows PowerShell 5.1 start-up with early owned-child samples: diagnostic only (#99/#100).

``python -m tools.measure_powershell_startup --output build/powershell-startup.json``

Each launch runs the fixed ``powershell.exe -NoLogo -NoProfile -NonInteractive`` with a script that only
prints a clock origin, converts one literal JSON value and exits. The observer samples a still-live
launch after one second, inside start-up, so its kernel thread states and newest modules show what
start-up waits on. Launches are sequential; a slow or timed-out launch never triggers a retry.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from tools.observed_process import run_observed
from tools.windows_trace_clock import trace_clock

_LAUNCHES = 12
_MAX_LAUNCHES = 32
_TIMEOUT = 30
_SAMPLE_AFTER = 1.0
_CLOCK_PREFIX = "FILETREE_STARTUP_CLOCK "
_JSON_PREFIX = "FILETREE_STARTUP_JSON "
_TEXT_LIMIT = 8192
_UNIX_EPOCH_FILETIME = 116444736000000000
_SCRIPT = (
    "$before = [DateTime]::UtcNow.ToFileTimeUtc(); $clock = [Diagnostics.Stopwatch]::StartNew(); "
    "$after = [DateTime]::UtcNow.ToFileTimeUtc(); "
    # The extra parentheses keep the -f arguments together instead of splitting WriteLine's arguments.
    "[Console]::Error.WriteLine(('" + _CLOCK_PREFIX
    + "{{\"pid\":{0},\"before_filetime_100ns\":{1},\"after_filetime_100ns\":{2}}}' -f $PID, $before, $after)); "
    "$null = '{\"a\":1}' | ConvertFrom-Json; "
    "[Console]::Error.WriteLine('" + _JSON_PREFIX + "' + $clock.ElapsedMilliseconds)"
)


def powershell() -> Path:
    """The system's Windows PowerShell 5.1, never a PATH lookup."""
    return Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"


def _filetime() -> int:
    return _UNIX_EPOCH_FILETIME + time.time_ns() // 100


def _json_ms(stderr: str) -> int | None:
    values = [line.rpartition(_JSON_PREFIX)[2].strip() for line in stderr.splitlines() if _JSON_PREFIX in line]
    return int(values[0]) if len(values) == 1 and values[0].isdigit() else None


def launch(program: Path, number: int) -> dict:
    """One bounded launch; the record keeps the actual outcome, clocks and every observer sample."""
    # Encoded: Windows argument quoting would strip the script's double quotes from -Command.
    encoded = base64.b64encode(_SCRIPT.encode("utf-16-le")).decode("ascii")
    command = [str(program), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
    record: dict = {"launch": number, "parent_before_filetime_100ns": _filetime()}
    started = time.monotonic()
    try:
        result, outcome = run_observed(command, timeout=_TIMEOUT, sample_after=_SAMPLE_AFTER), "completed"
    except subprocess.TimeoutExpired as error:
        result, outcome = error, "timeout"
    except OSError as error:
        return {**record, "outcome": "start-failed", "error": str(error)[:2048]}
    stderr = (result.stderr or b"").decode("utf-8", errors="replace")
    observation = getattr(result, "process_observation", {"status": "missing"})
    clock = trace_clock(stderr, _CLOCK_PREFIX, observation)
    origin = clock.get("origin")
    record.update(outcome=outcome, returncode=getattr(result, "returncode", None),
                  elapsed_seconds=round(time.monotonic() - started, 3), clock=clock,
                  launch_to_origin_ms=(round((origin["before_filetime_100ns"] - record["parent_before_filetime_100ns"])
                                             / 10_000, 1) if origin else None),
                  first_json_ms=_json_ms(stderr), stderr=stderr[-_TEXT_LIMIT:],
                  stdout=(result.stdout or b"")[-_TEXT_LIMIT:].decode("utf-8", errors="replace"),
                  process_observation=observation)
    return record


def measure(launches: int) -> dict:
    """Run the launches in order; the first is the runner's cold start."""
    program = powershell()
    records = [launch(program, number + 1) for number in range(launches)]
    timings = [item["launch_to_origin_ms"] for item in records if item.get("launch_to_origin_ms") is not None]
    return {"program": str(program), "python": sys.version, "commit": os.environ.get("GITHUB_SHA"),
            "launches": records, "launch_to_origin_ms": timings,
            "timeouts": sum(item.get("outcome") == "timeout" for item in records)}


def main() -> int:
    """Write a new report; any launch failure is evidence, not a reason to repeat it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launches", type=int, default=_LAUNCHES)
    args = parser.parse_args()
    if sys.platform != "win32" or not 1 <= args.launches <= _MAX_LAUNCHES:
        parser.error(f"Windows and 1-{_MAX_LAUNCHES} launches are required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(measure(args.launches), output, ensure_ascii=True, indent=1)
        output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
