"""Native tray/history/capacity proof using fresh owned sources; notifications require explicit opt-in."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import replace
import faulthandler
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
from je_file_tree.core.cleanup_policy import CleanupPolicy, RuleSetting  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.gui import history  # noqa: E402
from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.autostart import Registration  # noqa: E402
from je_file_tree.gui.background_dialog import BackgroundDialog  # noqa: E402
from je_file_tree.gui.recurring_dialog import RecurringDialog  # noqa: E402
from je_file_tree.gui.workspace import ScanWorkspace  # noqa: E402
from tools.recurring_probe import validate_review  # noqa: E402

_EXPECTED_SCHEDULES = 2


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
    (source / "既有.dmp").write_bytes(b"owned old dump" * 4096)
    captured = (kept.stat().st_dev, kept.stat().st_ino, hashlib.sha256(kept.read_bytes()).hexdigest())
    return source, kept, captured


def _proposal(app: QApplication, workspace, source: Path, config: MonitorConfig, evidence: Path) -> dict:
    first = next(iter(workspace.background.reports.values()))
    require(not first.comparison_complete and len(first.baseline.candidates) == 1,
            "First proposal did not keep the missing baseline unknown")
    old = source / "既有.dmp"
    old_proof = old.stat().st_ino, hashlib.sha256(old.read_bytes()).hexdigest()
    new = source / "新增.dmp"
    new.write_bytes(b"owned new dump" * 4096)
    new_proof = new.stat().st_ino, hashlib.sha256(new.read_bytes()).hexdigest()
    workspace.background.configure(replace(config, interval_hours=config.interval_hours + 1))
    workspace.background.tick()
    pump(app, lambda: workspace.background.scan is None and bool(workspace.background.reports))
    report = next(iter(workspace.background.reports.values()))
    require(report.comparison_complete and [row.path for row in report.new_junk] == [str(new)]
            and report.growth[0].path == str(source) and report.growth[0].change == new.stat().st_size,
            "Native scheduled comparison did not match owned history")
    require(workspace.background.report_status(report) is None, "Native proposal binding failed")
    dialog = RecurringDialog((report,), workspace.background.report_status, workspace.current)
    try:
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        dialog.show()
        app.processEvents()
        require(dialog.grab().save(str(evidence / "recurring-dialog-zh-TW.png")), "Proposal capture failed")
    finally:
        dialog.shutdown()
        dialog.reject()
        dialog.deleteLater()
    require(old_proof == (old.stat().st_ino, hashlib.sha256(old.read_bytes()).hexdigest())
            and new_proof == (new.stat().st_ino, hashlib.sha256(new.read_bytes()).hexdigest()),
            "Proposal preparation/view changed owned sources")
    require(history.configured_history(workspace.settings).read(str(source)).count == _EXPECTED_SCHEDULES,
            "Proposal did not preserve both scheduled history entries")
    return {"comparison_complete": True, "new_junk_rows": len(report.new_junk), "growth_rows": len(report.growth),
            "binding_current": True, "source_preserved": True, "native_trash_move": False}


def _settings(owned: Path) -> QSettings:
    settings = QSettings(str(owned / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "zh-TW")
    settings.setValue("check_updates", False)
    settings.setValue("history_enabled", True)
    settings.setValue("cleanup_policy", CleanupPolicy((RuleSetting("crash_dumps", True, 0),)).dumps())
    return settings


def _workspace(settings: QSettings, retain: Callable[[str, dict], None], proof: dict) -> ScanWorkspace:
    retain("creating_workspace", proof)
    workspace = create_workspace(settings)
    workspace.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    workspace.resize(1180, 780)
    workspace.show()
    retain("checking_tray", proof)
    proof["tray_available"] = QSystemTrayIcon.isSystemTrayAvailable()
    return workspace


def _join(workspace: ScanWorkspace | None, original: Callable[[], Path],
          retain: Callable[[str, dict], None], proof: dict) -> None:
    try:
        retain("joining", proof)
    finally:
        try:
            if workspace is not None:
                workspace.quit_application()
                pump(QApplication.instance(), lambda: workspace._close_ready)
        finally:
            history.history_folder = original


def _session(app: QApplication, owned: Path, args, retain: Callable[[str, dict], None]) -> dict:
    source, kept, captured = _source(owned)
    settings = _settings(owned)
    original = history.history_folder
    history.history_folder = lambda: owned / "private-history"
    proof, workspace = {"autostart_registration": False}, None
    try:
        workspace = _workspace(settings, retain, proof)
        require(not (args.require_tray or args.require_notification) or proof["tray_available"],
                "A native tray is required for this proof")
        config = MonitorConfig(True, threshold=1, roots=(str(source),))
        retain("starting_services", proof)
        workspace.background.configure(config)
        workspace.start_services()
        if proof["tray_available"]:
            retain("scheduled_scan", proof)
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
            retain("recurring_proposal", proof)
            proof["recurring"] = _proposal(app, workspace, source, config, args.evidence)
            retain("recurring_review", proof)
            proof["recurring_review"] = validate_review(app, workspace, source, args.evidence, pump)
            if args.notification or args.require_notification:
                retain("notification", proof)
                proof["notification"] = _notification(app, workspace, args.evidence, required=args.require_notification)
            retain("close_to_tray", proof)
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
        retain("capturing_dialog", proof)
        _capture_dialog(app, workspace.background.config, workspace, args.evidence)
        retain("quitting", proof)
        _quit_joined(app, workspace)
        require(workspace.background.scan is None and workspace.background.capacity is None, "Quit did not join work")
        proof["quit_joined"] = True
        return proof
    finally:
        _join(workspace, original, retain, proof)


def _quit_joined(app: QApplication, workspace: ScanWorkspace) -> None:
    """Keep native Qt dispatch alive until the asynchronous closing fence has joined all work."""
    workspace.quit_application()
    pump(app, lambda: workspace._close_ready)


def _save(evidence: Path, proof: dict) -> None:
    with _atomic_file(evidence / "background.json", encoding="utf-8") as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


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

    def retain(phase: str, session: dict) -> None:
        """Persist the last native call before entering it, without inferring completion."""
        proof.update(phase=phase, last_native_phase=phase, session=dict(session))
        _save(args.evidence, proof)

    _save(args.evidence, proof)
    faulthandler.dump_traceback_later(60, repeat=True)
    try:
        with tempfile.TemporaryDirectory(prefix="filetree-background-owned-") as scratch:
            proof["session"] = _session(app, Path(scratch).resolve(strict=True), args, retain)
            proof["phase"] = "owned_fixture_cleanup"
            _save(args.evidence, proof)
        proof["owned_fixture_cleanup"] = True
        proof["phase"] = "complete"
    except (OSError, RuntimeError) as error:
        proof.update(phase="failed", error=str(error))
        raise
    finally:
        faulthandler.cancel_dump_traceback_later()
        _save(args.evidence, proof)


if __name__ == "__main__":
    main()
