"""Perform an actual Thunar-to-FileTree X11 drag using container-owned files."""

from __future__ import annotations

import subprocess  # nosec B404 - fixed X11 programs in the private test desktop
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from je_file_tree.gui.main_window import MainWindow, WELCOME_PAGE


def pump(app: QApplication, child: subprocess.Popen, *, seconds: float = 10) -> None:
    """Process native drag negotiation while a fixed X11 command runs."""
    deadline = time.monotonic() + seconds
    while child.poll() is None:
        if time.monotonic() > deadline:
            child.terminate()
            child.wait(timeout=10)
            raise RuntimeError("Native X11 command timed out")
        app.processEvents()
        time.sleep(.01)
    app.processEvents()


def xdotool(app: QApplication, *arguments: str) -> str:
    """Run a bounded, fixed input command while Qt handles its native events."""
    command = ["/usr/bin/xdotool", *arguments]
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603 # nosec B603
    pump(app, child)
    output, error = child.communicate()
    if child.returncode:
        raise RuntimeError(error.decode("utf-8", errors="replace"))
    return output.decode("utf-8").strip()


def check_drag(app: QApplication, window: MainWindow, evidence: Path, scratch: Path) -> dict[str, object]:
    """Require a real external drag to scan the expected folder while preserving its data."""
    parent = scratch / "drag-source"
    source = parent / "待掃描資料夾"
    source.mkdir(parents=True)
    payload = source / "original.txt"
    payload.write_bytes(b"original drag payload")
    before = payload.stat()
    with (evidence / "thunar.log").open("w", encoding="utf-8") as log:
        wm = subprocess.Popen(["/usr/bin/openbox"], stdout=log, stderr=log)  # noqa: S603 # nosec B603
        manager = subprocess.Popen(["/usr/bin/thunar", "--daemon"], stdout=log, stderr=log)  # noqa: S603 # nosec B603
        try:
            opener = subprocess.Popen(["/usr/bin/thunar", str(parent)], stdout=log, stderr=log)  # noqa: S603 # nosec B603
            pump(app, opener)
            identity = xdotool(app, "search", "--sync", "--onlyvisible", "--class", "Thunar").splitlines()[0]
            window.pages.setCurrentIndex(WELCOME_PAGE)
            window.setGeometry(0, 0, 1100, 720)
            window.show()
            app.processEvents()
            xdotool(app, "windowmove", identity, "1150", "0", "windowsize", identity, "850", "720",
                    "windowactivate", "--sync", identity, "key", "--clearmodifiers", "ctrl+2", "sleep", ".5")
            app.primaryScreen().grabWindow(0).save(str(evidence / "drag-before.png"))
            # The pinned Debian Thunar detailed view's first row, beyond the side pane.
            xdotool(app, "mousemove", "--window", identity, "310", "130", "mousedown", "1",
                    "sleep", ".2", "mousemove", "--window", identity, "325", "135", "sleep", ".2",
                    "mousemove", "500", "400", "sleep", "1", "mouseup", "1")
            deadline = time.monotonic() + 15
            while window._worker is not None or window.results.outcome is None or \
                    window.results.outcome.result.root.path != str(source):
                if time.monotonic() > deadline:
                    raise RuntimeError("Thunar drag did not finish a scan of the owned source folder")
                app.processEvents()
                time.sleep(.01)
            after = payload.stat()
            if payload.read_bytes() != b"original drag payload" or (before.st_dev, before.st_ino) != \
                    (after.st_dev, after.st_ino):
                raise RuntimeError("Native drag changed the original payload")
            return {"file_manager": "Thunar", "external_x11_drag": True,
                    "scanned_path": str(source), "original_identity_and_contents_preserved": True}
        finally:
            app.primaryScreen().grabWindow(0).save(str(evidence / "drag-after.png"))
            for child in (manager, wm):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=10)
