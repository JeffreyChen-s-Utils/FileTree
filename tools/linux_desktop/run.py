"""Run desktop checks under X11 and a private session bus in a fresh, resource-limited container."""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - fixed test programs, no shell
import sys
import tempfile
import time
from pathlib import Path


def run_probe(environment: dict[str, str], evidence: Path) -> int:
    """Require complete artifacts even if the bus wrapper masks a crashed child."""
    command = ["/usr/bin/dbus-run-session", "--", sys.executable,
               "/workspace/tools/linux_desktop/probe.py", str(evidence)]
    result = subprocess.run(command, env=environment, check=False)  # noqa: S603 # nosec B603
    if result.returncode:
        return result.returncode
    proof = json.loads((evidence / "proof.json").read_text(encoding="utf-8"))
    for key in ("dbus", "trash", "fallback", "cjk_font"):
        if not proof.get(key) or isinstance(proof[key], dict) and "error" in proof[key]:
            raise RuntimeError(f"Incomplete native desktop evidence: {key}")
    if not (evidence / "desktop-zh-TW.png").is_file():
        raise RuntimeError("Missing native desktop screenshot")
    return 0


def main() -> int:
    """Set up only container-owned desktop state; preserve evidence on success or failure."""
    evidence = Path(sys.argv[1] if len(sys.argv) > 1 else "/evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="filetree-desktop-") as scratch:
        environment = dict(os.environ, DISPLAY=":99", QT_QPA_PLATFORM="xcb", HOME=scratch,
                           XDG_DATA_HOME=f"{scratch}/data", XDG_CONFIG_HOME=f"{scratch}/config",
                           XDG_CACHE_HOME=f"{scratch}/cache", PYTHONPATH="/workspace")
        with (evidence / "xvfb.log").open("w", encoding="utf-8") as log:
            command = ["/usr/bin/Xvfb", ":99", "-screen", "0", "2560x900x24", "-nolisten", "tcp"]
            server = subprocess.Popen(command, env=environment, stdout=log, stderr=log)  # noqa: S603 # nosec B603
            try:
                deadline = time.monotonic() + 10
                socket = Path("/tmp/.X11-unix/X99")  # noqa: S108 - standard X11 socket inside a fresh container
                while not socket.exists():
                    if server.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Xvfb did not start")
                    time.sleep(.05)
                return run_probe(environment, evidence)
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
