"""Check actual D-Bus typing, freedesktop Trash and native CJK rendering with container-owned fixtures."""

from __future__ import annotations

import configparser
import json
import os
import subprocess  # nosec B404 - own test service and fixed desktop programs
import sys
import time
import xml.etree.ElementTree as ET  # nosec B405 - XML from our own private bus service
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtGui import QFont, QRawFont
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from je_file_tree.core.scanner import scan
from je_file_tree.core.export import _atomic_file
from je_file_tree.gui import file_actions, main_window
from je_file_tree.gui.i18n import set_language
from je_file_tree.gui.qt_translation import apply_qt_translation
from je_file_tree.gui.scan_worker import analyse
from drag import check_drag


def require(condition: bool, message: str) -> None:
    """Fail with a clear probe condition, keeping evidence for CI artifacts."""
    if not condition:
        raise RuntimeError(message)


def pump(app: QApplication, ready: Callable[[], bool], *, seconds: float = 15) -> None:
    """Keep Qt responsive while a real process, bus reply or worker finishes."""
    deadline = time.monotonic() + seconds
    while not ready():
        if time.monotonic() > deadline:
            raise RuntimeError("Desktop probe timed out")
        app.processEvents()
        time.sleep(.01)
    app.processEvents()


def check_bus(app: QApplication, evidence: Path, scratch: Path) -> dict[str, object]:
    """Require an actual wire call accepted by a service exporting exactly as, s."""
    output = scratch / "show-items.json"
    with (evidence / "manager.log").open("w", encoding="utf-8") as log:
        command = [sys.executable, "/workspace/tools/linux_desktop/manager.py", str(output)]
        service = subprocess.Popen(command, stdout=log, stderr=log)  # noqa: S603 # nosec B603 - own script
        try:
            pump(app, lambda: output.with_suffix(".ready").exists())
            bus = QDBusConnection.sessionBus()
            message = QDBusMessage.createMethodCall("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
                                                    "org.freedesktop.DBus.Introspectable", "Introspect")
            reply = bus.call(message)
            xml = ET.fromstring(reply.arguments()[0])  # noqa: S314 # nosec B314 - own private test service
            method = xml.find("./interface[@name='org.freedesktop.FileManager1']/method[@name='ShowItems']")
            require(method is not None, "Strict service did not export ShowItems")
            signature = [arg.attrib["type"] for arg in method.findall("arg") if arg.get("direction") == "in"]
            require(signature == ["as", "s"], f"Unexpected strict signature: {signature}")
            target = scratch / "資料, with space.txt"
            target.write_text("owned test", encoding="utf-8")
            accepted = file_actions.show_items(str(target))
            pump(app, lambda: output.exists() or not accepted)
            require(accepted and output.exists(), "ShowItems was rejected by the strict (as, s) service")
            recorded = json.loads(output.read_text(encoding="utf-8"))
            require(recorded == {"uris": [QUrl.fromLocalFile(str(target)).toString()], "startup_id": ""},
                    "ShowItems did not preserve the Unicode/comma/space path")
            return {"signature": signature, "call": recorded}
        finally:
            service.terminate()
            service.wait(timeout=10)


def check_trash(app: QApplication, window: main_window.MainWindow, scratch: Path) -> dict[str, object]:
    """Move one owned fixture through MainWindow's normal review/confirmation/journal workflow."""
    root = scratch / "trash-source"
    root.mkdir()
    target = root / "垃圾桶 測試.txt"
    target.write_text("owned trash contents", encoding="utf-8")
    window.results.show_outcome(analyse(scan(root)))
    node = window.results.outcome.result.root.children[0]
    original_review, original_question = main_window.CleanupReview.exec, QMessageBox.question

    def approve(dialog):
        dialog.model.setData(dialog.model.index(0, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        return QDialog.DialogCode.Accepted

    try:
        main_window.CleanupReview.exec = approve
        QMessageBox.question = lambda *_args: QMessageBox.StandardButton.Yes
        window.move_to_trash([node])
        pump(app, lambda: window._trash_worker is None)
        require(not target.exists(), "Approved owned fixture did not enter the Trash")
        trash = Path(os.environ["XDG_DATA_HOME"]) / "Trash"
        infos = list((trash / "info").glob("*.trashinfo"))
        require(len(infos) == 1, "Expected one freedesktop trashinfo receipt")
        receipt = configparser.ConfigParser(interpolation=None)
        receipt.read(infos[0], encoding="utf-8")
        require(unquote(receipt["Trash Info"]["Path"]) == str(target), "Trash original path was not preserved")
        require(bool(receipt["Trash Info"]["DeletionDate"]), "Trash receipt is missing its deletion date")
        trashed = trash / "files" / infos[0].name.removesuffix(".trashinfo")
        require(trashed.read_text(encoding="utf-8") == "owned trash contents", "Trash contents differ")
        return {"trashinfo": True, "original_path_preserved": True, "contents_preserved": True}
    finally:
        main_window.CleanupReview.exec, QMessageBox.question = original_review, original_question


def check_fallback(app: QApplication, evidence: Path, scratch: Path) -> dict[str, object]:
    """Verify the native desktop fallback opens the parent with Unicode preserved."""
    binary = scratch / "bin"
    binary.mkdir()
    record = scratch / "xdg-open.json"
    executable = binary / "xdg-open"
    executable.write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                          "from je_file_tree.core.export import _atomic_file\n"
                          "with _atomic_file(os.environ['FILETREE_XDG_LOG'], encoding='utf-8') as out:\n"
                          "    json.dump(sys.argv[1:], out)\n", encoding="utf-8")
    executable.chmod(0o700)
    folder = scratch / "備援 資料,夾"
    folder.mkdir()
    target = folder / "test.txt"
    target.write_text("owned fallback", encoding="utf-8")
    environment = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=f"unix:path={scratch}/absent-bus",
                       FILETREE_XDG_LOG=str(record), PATH=f"{binary}:{os.environ['PATH']}")
    command = [sys.executable, "/workspace/tools/linux_desktop/fallback.py", str(target), str(record)]
    with (evidence / "fallback.log").open("w", encoding="utf-8") as log:
        child = subprocess.Popen(command, env=environment, stdout=log, stderr=log)  # noqa: S603 # nosec B603
        try:
            pump(app, lambda: child.poll() is not None)
            require(child.returncode == 0, "Native desktop fallback process failed")
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=10)
    arguments = json.loads(record.read_text(encoding="utf-8"))
    require(len(arguments) == 1, "Fallback did not preserve a single folder argument")
    actual = QUrl(arguments[0]).toLocalFile() or arguments[0]
    require(actual == str(folder), f"Fallback opened the wrong folder: {arguments}")
    return {"disconnected_bus": True, "parent_folder_preserved": True, "arguments": arguments}


def main() -> int:
    """Run only owned fixtures; emit proof and a native Traditional Chinese screenshot."""
    evidence, scratch = Path(sys.argv[1]), Path(os.environ["HOME"])
    app = QApplication([])
    app.setOrganizationName("FileTreeDesktopTests")
    app.setApplicationName("FileTreeDesktopTests")
    app.setFont(QFont("Noto Sans CJK TC"))
    set_language("zh-TW")
    apply_qt_translation("zh-TW")
    settings = QSettings(str(scratch / "settings.ini"), QSettings.Format.IniFormat)
    window = main_window.MainWindow(settings)
    try:
        proof, failures = {}, []
        for name, check in (("dbus", lambda: check_bus(app, evidence, scratch)),
                            ("trash", lambda: check_trash(app, window, scratch)),
                            ("fallback", lambda: check_fallback(app, evidence, scratch)),
                            ("drag", lambda: check_drag(app, window, evidence, scratch))):
            try:
                proof[name] = check()
            except (OSError, RuntimeError, ValueError, ET.ParseError) as error:
                proof[name] = {"error": str(error)}
                failures.append(name)
        require(QRawFont.fromFont(app.font()).supportsCharacter(ord("檔")), "Native font lacks CJK glyphs")
        window.pages.setCurrentIndex(main_window.RESULTS_PAGE)
        window.show()
        app.processEvents()
        require(window.grab().save(str(evidence / "desktop-zh-TW.png")), "Native X11 capture failed")
        proof["cjk_font"] = app.font().family()
        with _atomic_file(evidence / "proof.json", encoding="utf-8") as stream:
            json.dump(proof, stream, indent=2)
        print(json.dumps(proof, indent=2))
        require(not failures, "Failed native desktop checks: " + ", ".join(failures))
        return 0
    finally:
        window.close()


if __name__ == "__main__":
    raise SystemExit(main())
