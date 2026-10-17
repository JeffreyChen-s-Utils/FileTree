"""Opt-in pytest phase evidence; leaves Qt handlers and fatal behavior untouched."""

from __future__ import annotations

import faulthandler
import json
import os
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

_MAX_NODEID = 4096
# Export/journal fault-injection tests replace os.replace until fixture teardown.
_ATOMIC_REPLACE = os.replace
_PUBLISH_PAUSE = time.sleep
_PUBLISH_ATTEMPTS = 10
_PUBLISH_DELAY = .01
_WINDOWS_READER_ERRORS = {5, 32, 33}


def _publish(temporary: Path, path: Path) -> None:
    for attempt in range(_PUBLISH_ATTEMPTS):
        try:
            _ATOMIC_REPLACE(temporary, path)
        except OSError as error:
            if getattr(error, "winerror", None) not in _WINDOWS_READER_ERRORS or attempt == _PUBLISH_ATTEMPTS - 1:
                raise
            _PUBLISH_PAUSE(_PUBLISH_DELAY)
        else:
            return


def write_record(path: Path, record: dict) -> None:
    """Replace a small JSON observation without exposing a partially written record."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    _publish(temporary, path)


class PhaseContext:
    """Keep only the latest phase and its entry-time Python thread snapshot."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def _record(self, phase: str, nodeid: str = "", outcome: str = "") -> None:
        record = {
            "schema": 1, "pid": os.getpid(), "phase": phase,
            "nodeid": nodeid[:_MAX_NODEID], "nodeid_truncated": len(nodeid) > _MAX_NODEID,
            "outcome": outcome, "utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns(),
        }
        write_record(self.folder / "active.json", record)
        temporary = self.folder / "phase-threads.tmp"
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\nPhase-entry snapshot, not a fault-time traceback.\n")
            stream.flush()
            faulthandler.dump_traceback(file=stream, all_threads=True)
        _publish(temporary, self.folder / "phase-threads.txt")

    def pytest_sessionstart(self) -> None:
        """Mark collection before any test module can terminate the process."""
        self._record("collection")

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> None:
        """Persist setup context before fixture execution."""
        self._record("setup", item.nodeid)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_call(self, item: pytest.Item) -> None:
        """Persist call context before entering the test body."""
        self._record("call", item.nodeid)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_teardown(self, item: pytest.Item) -> Iterator[None]:
        """Persist teardown context while allowing fixture cleanup even if recording fails."""
        try:
            self._record("teardown", item.nodeid)
        finally:
            yield

    def pytest_sessionfinish(self, exitstatus: int) -> None:
        """Record pytest completion separately from the child process exit."""
        self._record("session-finished", outcome=str(int(exitstatus)))


def pytest_configure(config: pytest.Config) -> None:
    """Activate only when the diagnostic runner supplies an evidence directory."""
    folder = os.environ.get("FILETREE_PYTEST_CONTEXT")
    if folder:
        config.pluginmanager.register(PhaseContext(Path(folder)), "filetree-phase-context")
