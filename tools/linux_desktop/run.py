"""Run desktop checks under X11 and a private session bus in a fresh, resource-limited container."""

from __future__ import annotations

import json
import os
import re
import select
import subprocess  # nosec B404 - fixed test programs, no shell
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


def run_probe(environment: dict[str, str], evidence: Path) -> int:
    """Require complete artifacts even if the bus wrapper masks a crashed child."""
    command = ["/usr/bin/dbus-run-session", "--", sys.executable,
               "/workspace/tools/linux_desktop/probe.py", str(evidence)]
    result = subprocess.run(command, env=environment, check=False)  # noqa: S603 # nosec B603
    if result.returncode:
        return result.returncode
    proof = json.loads((evidence / "proof.json").read_text(encoding="utf-8"))
    for key in ("dbus", "trash", "fallback", "drag", "cjk_font", "background"):
        if not proof.get(key) or isinstance(proof[key], dict) and "error" in proof[key]:
            raise RuntimeError(f"Incomplete native desktop evidence: {key}")
    if not (evidence / "desktop-zh-TW.png").is_file():
        raise RuntimeError("Missing native desktop screenshot")
    return 0


@contextmanager
def display_server(environment: dict[str, str], log: TextIO) -> Iterator[None]:
    """Use Xvfb's private readiness pipe and allocated display; always join the owned child."""
    reader, writer = os.pipe()
    server = None
    try:
        command = ["/usr/bin/Xvfb", "-displayfd", str(writer), "-screen", "0", "2560x900x24", "-nolisten", "tcp"]
        server = subprocess.Popen(command, env=environment, stdout=log, stderr=log,  # noqa: S603 # nosec B603
                                  pass_fds=(writer,))
        os.close(writer)
        writer = None
        if not select.select([reader], [], [], 10)[0]:
            raise RuntimeError("Xvfb did not report a ready display")
        display = os.read(reader, 32).decode("ascii").strip()
        if re.fullmatch(r"[0-9]{1,5}", display) is None or server.poll() is not None:
            raise RuntimeError("Xvfb reported an invalid display or exited")
        environment["DISPLAY"] = ":" + display
        yield
    finally:
        os.close(reader)
        if writer is not None:
            os.close(writer)
        if server is not None:
            if server.poll() is None:
                server.terminate()
            server.wait(timeout=10)


def main() -> int:
    """Set up only container-owned desktop state; preserve evidence on success or failure."""
    if len(sys.argv) != 1:
        raise ValueError("Desktop container evidence is fixed at /evidence")
    evidence = Path("/evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="filetree-desktop-") as scratch:
        environment = dict(os.environ, QT_QPA_PLATFORM="xcb", HOME=scratch,
                           XDG_DATA_HOME=f"{scratch}/data", XDG_CONFIG_HOME=f"{scratch}/config",
                           XDG_CACHE_HOME=f"{scratch}/cache", PYTHONPATH="/workspace")
        with (evidence / "xvfb.log").open("w", encoding="utf-8") as log, display_server(environment, log):
            return run_probe(environment, evidence)


if __name__ == "__main__":
    raise SystemExit(main())
