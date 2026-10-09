"""Measure native macOS copy/link metadata and CJK rendering using only fresh owned sources."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QSettings, Qt, qVersion  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from je_file_tree.core.copy_platform import mac_xattrs  # noqa: E402
from je_file_tree.core.duplicate_link_ops import execute_links  # noqa: E402
from je_file_tree.core.duplicate_links import prepare_links  # noqa: E402
from je_file_tree.core.duplicates import find_duplicates  # noqa: E402
from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.core.scanner import scan  # noqa: E402
from je_file_tree.core.verified_copy import copy_folders, prepare_copy, verify_copy  # noqa: E402
from je_file_tree.gui.app import create_workspace  # noqa: E402
from je_file_tree.gui.charts import MODES  # noqa: E402

_ALIAS_COUNT = 2


def require(condition: bool, message: str) -> None:
    """Retain a visible failure instead of writing a completed native proof."""
    if not condition:
        raise RuntimeError(message)


def _set_attributes(path: Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    library.setxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                                ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
    library.setxattr.restype = ctypes.c_int
    for name, value in ((b"com.apple.ResourceFork", b"owned resource fork" * 128),
                        (b"com.filetree.validation", b"owned metadata" * 32)):
        if library.setxattr(os.fsencode(path), name, value, len(value), 0, 0):
            raise OSError(ctypes.get_errno(), "Owned native extended attribute failed")


def _proof(path: Path) -> dict:
    with path.open("rb") as stream:
        attributes = mac_xattrs(stream.fileno(), 64 * 1024 * 1024, total_limit=64 * 1024 * 1024)
        digest = hashlib.sha256(stream.read()).hexdigest()
        info = os.fstat(stream.fileno())
    require(all(value is not None for _name, _size, value in attributes), "Incomplete attribute payload")
    return {"sha256": digest, "identity": [info.st_dev, info.st_ino], "links": info.st_nlink,
            "bytes": info.st_size, "mode": info.st_mode, "modified_ns": info.st_mtime_ns,
            "attributes": {name.decode("utf-8"): {"bytes": length, "sha256": hashlib.sha256(value).hexdigest()}
                           for name, length, value in attributes}}


def _sources(owned: Path) -> tuple[Path, Path]:
    source, target = owned / "來源", owned / "已驗證複本"
    (source / "資料夾" / "空資料夾").mkdir(parents=True)
    target.mkdir()
    for name in ("保留.bin", "額外複本.bin"):
        path = source / "資料夾" / name
        path.write_bytes(b"fresh owned macOS payload" * 1024)
        _set_attributes(path)
        path.chmod(0o640)
    return source, target


def _copy_and_link(source: Path, target: Path) -> dict:
    folder = source / "資料夾"
    before = {path.name: _proof(path) for path in folder.iterdir() if path.is_file()}
    root = scan(source).root
    plan = prepare_copy(root, root.children, str(target))
    require(plan is not None and all(not item.reason for item in plan.items), "Native copy preview refused")
    copied = copy_folders(plan)
    require(not copied.failed and not copied.partial and len(copied.verified) == 1, "Native copy failed")
    verify_copy(copied.verified[0])
    require((target / folder.name / "空資料夾").is_dir(), "Empty folder lost")
    for name, original in before.items():
        require(_proof(folder / name) == original, "Native copy changed original payload/identity/metadata")
        actual = _proof(target / folder.name / name)
        require(all(actual[key] == original[key] for key in ("sha256", "bytes", "mode", "modified_ns", "attributes")),
                "Native copied content/resource fork/metadata differs")
    root = scan(source).root
    groups = find_duplicates(root, min_size=1, workers=1).groups
    require(len(groups) == 1, "Owned native duplicate group unavailable")
    group = replace(groups[0], kept=next(node for node in groups[0].files if node.name == "保留.bin"))
    links = prepare_links(root, [group])
    require(links is not None and all(not pair.reason for pair in links.pairs), "Native linking preview refused")
    result = execute_links(links)
    require(len(result.outcomes) == 1 and all(item.linked and not item.error and not item.retained
                                             for item in result.outcomes), "Native duplicate linking failed")
    after = {name: _proof(folder / name) for name in before}
    require(after["保留.bin"]["identity"] == after["額外複本.bin"]["identity"] and
            after["保留.bin"]["identity"] == before["保留.bin"]["identity"], "Native aliases/keeper identity differ")
    require(all(item["links"] == _ALIAS_COUNT and item["sha256"] == before[name]["sha256"] and
                item["attributes"] == before[name]["attributes"] for name, item in after.items()),
            "Native alias payload/resource fork/metadata differs")
    return {"copy": "native_fcopyfile_verified", "copy_scope": "same-volume",
            "source_preserved_after_copy": True, "empty_folder_preserved": True,
            "duplicate_link": "native_verified", "before": before, "after": after}


def _render(app: QApplication, owned: Path, source: Path, evidence: Path) -> dict:
    settings = QSettings(str(owned / "owned-settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("language", "zh-TW")
    window = create_workspace(settings)
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1200, 800)
    try:
        window.show()
        window.current.start_scan(str(source))
        deadline = time.monotonic() + 30
        while window.current._worker is not None:
            require(time.monotonic() < deadline, "Native owned GUI scan timed out")
            app.processEvents()
            time.sleep(0.01)
        require(window.current.results.outcome is not None, "Native scan did not publish results")
        for mode in MODES:
            window.current.results.charts.set_mode(mode)
            app.processEvents()
            require(not window.current.results.charts._charts[mode].grab().isNull(), "Native chart did not render")
        require(window.grab().save(str(evidence / "macos-sources-zh-TW.png")), "Native CJK PNG could not be saved")
        return {"qt_platform": app.platformName(), "language": "zh-TW", "charts": list(MODES),
                "scan_bytes": window.current.results.outcome.result.root.size}
    finally:
        window.close()
        deadline = time.monotonic() + 30
        while not window._close_ready:
            require(time.monotonic() < deadline, "Native owned GUI shutdown timed out")
            app.processEvents()
            time.sleep(.01)


def main() -> None:
    """Refuse other platforms and host-bin operations; preserve phase JSON even if a later check fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise ValueError("Native macOS required")
    if os.environ.get("QT_QPA_PLATFORM"):
        raise ValueError("Native cocoa rendering required, not an overridden Qt platform")
    args.evidence.mkdir(parents=True, exist_ok=True)
    output = args.evidence / "macos-sources.json"
    proof = {"phase": "started", "macos": platform.mac_ver()[0], "machine": platform.machine(), "qt": qVersion(),
             "finder_automation_verified": False, "trash_verified": False, "cross_volume_verified": False}
    app = QApplication.instance() or QApplication([])
    try:
        with tempfile.TemporaryDirectory(prefix="filetree-macos-owned-") as scratch:
            owned = Path(scratch).resolve(strict=True)
            source, target = _sources(owned)
            proof["native_metadata"] = _copy_and_link(source, target)
            proof["phase"] = "metadata_verified"
            captured = {str(path): _proof(path) for path in source.rglob("*.bin")}
            proof["render"] = _render(app, owned, source, args.evidence)
            require(captured == {str(path): _proof(path) for path in source.rglob("*.bin")}, "GUI changed sources")
            proof["gui_source_preservation"] = True
        proof["owned_fixture_cleanup"] = True
        proof["phase"] = "complete"
    finally:
        with _atomic_file(output, encoding="utf-8") as stream:
            json.dump(proof, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()
