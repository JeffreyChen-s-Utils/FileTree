"""Native tray/history/capacity proof using fresh owned sources; notifications require explicit opt-in."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QSettings, Qt, qVersion  # noqa: E402
from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from je_file_tree.core.background import MonitorConfig, load_attempts  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.gui import history  # noqa: E402
from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.autostart import Registration  # noqa: E402
from je_file_tree.gui.background_dialog import BackgroundDialog  # noqa: E402


def require(condition: bool, detail: str) -> None:
    """Retain a partial phase when the native condition has not been proved."""
    if not condition:
        raise RuntimeError(detail)


def pump(app: QApplication, ready: Callable[[], bool]) -> None:
    """Wait for actual Qt/worker completion without overriding its native platform."""
    deadline = time.monotonic() + 30
    while not ready():
        if time.monotonic() >= deadline:
            raise RuntimeError("Native background validation timed out")
        app.processEvents()
        time.sleep(.01)
    app.processEvents()


def _notification(app: QApplication, workspace, evidence: Path, *, required: bool) -> dict:
    supported = QSystemTrayIcon.supportsMessages()
    require(not required or supported, "Native tray notifications are unsupported")
    if not supported:
        return {"supported": False, "display_verified": False}
    workspace.background.tray.showMessage("FileTree · 原生通知測試", "隔離測試通知；來源檔案保持不變。",
                                          QSystemTrayIcon.MessageIcon.Information, 10000)

    def balloons():
        return [widget for widget in app.topLevelWidgets()
                if widget.metaObject().className() == "QBalloonTip" and widget.isVisible()]

    if required:
        pump(app, lambda: bool(balloons()))
    else:
        app.processEvents()
    visible = balloons()
    if visible:
        require(visible[0].grab().save(str(evidence / "notification-zh-TW.png")), "Notification capture failed")
    return {"supported": True, "dispatch": True, "display_verified": bool(visible),
            "scope": "explicit owned-fixture notification", "os_policy_approval_verified": False}


def _capture_dialog(app: QApplication, config: MonitorConfig, workspace, evidence: Path) -> None:
    dialog = BackgroundDialog(config, workspace, startup=Registration(False, "owned registration fixture"))
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    dialog.show()
    app.processEvents()
    require(dialog.grab().save(str(evidence / "background-dialog-zh-TW.png")), "Dialog capture failed")
    dialog.reject()
    dialog.deleteLater()
    require(workspace.grab().save(str(evidence / "background-workspace-zh-TW.png")), "Workspace capture failed")


def _source(owned: Path) -> tuple[Path, Path, tuple]:
    source = owned / "排程來源"
    (source / "中文資料夾").mkdir(parents=True)
    kept = source / "中文資料夾" / "保留.txt"
    kept.write_bytes("原生排程保留內容".encode() * 4096)
    captured = (kept.stat().st_dev, kept.stat().st_ino, hashlib.sha256(kept.read_bytes()).hexdigest())
    return source, kept, captured


def _session(app: QApplication, owned: Path, args) -> dict:
    source, kept, captured = _source(owned)
    settings = QSettings(str(owned / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "zh-TW")
    settings.setValue("check_updates", False)
    settings.setValue("history_enabled", True)
    original = history.history_folder
    history.history_folder = lambda: owned / "private-history"
    workspace = create_workspace(settings)
    workspace.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    workspace.resize(1180, 780)
    workspace.show()
    proof = {"tray_available": QSystemTrayIcon.isSystemTrayAvailable(), "autostart_registration": False}
    try:
        require(not (args.require_tray or args.require_notification) or proof["tray_available"],
                "A native tray is required for this proof")
        config = MonitorConfig(True, threshold=1, roots=(str(source),))
        workspace.background.configure(config)
        workspace.start_services()
        if proof["tray_available"]:
            workspace.background.tick()
            capacity = workspace.background.capacity
            pump(app, lambda: settings.contains("background_attempts") and workspace.background.scan is None
                 and next(iter(load_attempts(settings.value("background_attempts")).values())).state == "complete")
            pump(app, lambda: workspace.background.capacity is None)
            require(capacity is not None and not capacity.error and bool(capacity.rows), "Native OS capacity failed")
            entries = history.configured_history(settings).read(str(source))
            require(entries.count == 1 and not entries.entries[0].incomplete, "Native history was not complete")
            require(workspace.current.results.outcome is None, "Scheduled history replaced a foreground tab")
            proof.update(scheduled_history_complete=True, native_capacity_rows=len(capacity.rows),
                         foreground_unchanged=True)
            if args.notification or args.require_notification:
                proof["notification"] = _notification(app, workspace, args.evidence, required=args.require_notification)
            workspace.close()
            require(workspace.isHidden() and not workspace._closing and workspace.background.can_hide,
                    "Native close-to-tray lifetime failed")
            workspace.background.show_window()
            require(not workspace.isHidden(), "Native tray restoration failed")
            proof.update(close_to_tray=True, restored_window=True)
        else:
            require(not workspace.isHidden() and not workspace.background.timer.isActive()
                    and workspace.background.scan is None, "Unavailable tray did not pause visible monitoring")
            proof.update(unavailable_tray_visible=True, scheduled_history_complete=False)
        require(captured == (kept.stat().st_dev, kept.stat().st_ino, hashlib.sha256(kept.read_bytes()).hexdigest()),
                "Native background work changed source identity or content")
        proof["source_preserved"] = True
        _capture_dialog(app, config, workspace, args.evidence)
        workspace.quit_application()
        require(workspace.background.scan is None and workspace.background.capacity is None, "Quit did not join work")
        proof["quit_joined"] = True
        return proof
    finally:
        workspace.quit_application()
        history.history_folder = original


def main() -> None:
    """Require native rendering and retain explicit unavailable states, never a false desktop pass."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--notification", action="store_true")
    parser.add_argument("--require-notification", action="store_true")
    parser.add_argument("--require-tray", action="store_true")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    require(app.platformName() in ("windows", "cocoa", "xcb", "wayland"), "Native desktop rendering is required")
    args.evidence.mkdir(parents=True, exist_ok=True)
    proof = {"phase": "started", "platform": app.platformName(), "qt": qVersion(), "real_login_launch_verified": False}
    try:
        with tempfile.TemporaryDirectory(prefix="filetree-background-owned-") as scratch:
            proof["session"] = _session(app, Path(scratch).resolve(strict=True), args)
        proof["owned_fixture_cleanup"] = True
        proof["phase"] = "complete"
    finally:
        with _atomic_file(args.evidence / "background.json", encoding="utf-8") as stream:
            json.dump(proof, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()
