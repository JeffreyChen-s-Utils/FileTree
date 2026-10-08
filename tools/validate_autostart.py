"""Validate native registration APIs only in fresh private registry/filesystem fixtures, never login paths."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.export import _atomic_file  # noqa: E402
from je_file_tree.gui import autostart, startup_posix, startup_windows  # noqa: E402

_PRIVATE_MODE = 0o600


def require(condition: bool, detail: str) -> None:
    """Do not claim complete evidence when a native contract fails."""
    if not condition:
        raise RuntimeError(detail)


def _windows(arguments: tuple[str, ...]) -> dict:
    import winreg  # noqa: PLC0415 - native owned HKCU fixture only

    root = "Software\\FileTreeValidation\\" + uuid.uuid4().hex
    original = startup_windows.RUN_KEY, startup_windows.RECEIPT_KEY
    run_key, receipt_key = root + r"\RunFixture", root + r"\ReceiptFixture"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, root):
            raise OSError("Fresh UUID registry fixture already exists")
    except FileNotFoundError:
        pass  # Claim below writes the owner only when RegCreateKeyEx reports a newly created key.
    try:
        startup_windows.RECEIPT_KEY = root
        with startup_windows._claim():
            pass  # Own the fresh fixture parent before creating its child scopes.
        # A new UUID scope only; no production Run key is opened by this probe.
        startup_windows.RUN_KEY, startup_windows.RECEIPT_KEY = run_key, receipt_key
        require(not startup_windows.inspect().installed, "Fresh registry fixture was occupied")
        require(startup_windows.apply(True, arguments).installed, "Native Run fixture installation failed")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key) as key:
            command, kind = winreg.QueryValueEx(key, startup_windows.VALUE)
        require(kind == winreg.REG_SZ and command == autostart.windows_command(arguments), "Native command differs")
        require(not startup_windows.apply(False, arguments).installed, "Native removal failed")
        require(startup_windows.apply(True, arguments).installed, "Native reinstallation failed")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, startup_windows.VALUE, 0, winreg.REG_SZ, "owned collision fixture")
        refused = []
        for enabled in (True, False):
            try:
                startup_windows.apply(enabled, arguments)
            except OSError:
                refused.append(enabled)
        require(refused == [True, False], "Changed native registration was not refused")
        return {"backend": "HKCU private non-startup keys", "install_remove_reinstall": True,
                "changed_entry_refused": True, "quoted_command": command, "host_login_entry_modified": False}
    finally:
        startup_windows.RUN_KEY, startup_windows.RECEIPT_KEY = original
        # Remove only the exact fresh UUID fixture keys with their bounded known shape.
        for path, names in ((run_key, {startup_windows.VALUE}), (receipt_key, {"Owner", "Command"})):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                children, count, _ = winreg.QueryInfoKey(key)
                require(not children and count <= len(names), "Unexpected native fixture registry contents")
                actual = {winreg.EnumValue(key, index)[0] for index in range(count)}
                require(actual <= names, "Foreign registry fixture value; retained")
                if path == receipt_key:
                    require(startup_windows._receipt(key) == autostart.windows_command(arguments),
                            "Native fixture receipt changed; retained")
                else:
                    value, kind = winreg.QueryValueEx(key, startup_windows.VALUE)
                    require(kind == winreg.REG_SZ and value in (autostart.windows_command(arguments),
                                                                "owned collision fixture"),
                            "Native fixture command changed; retained")
                for name in actual:
                    winreg.DeleteValue(key, name)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, root, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            require(startup_windows._receipt(key) is None, "Native fixture parent changed; retained")
            winreg.DeleteValue(key, "Owner")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root)


def _posix(owned: Path, arguments: tuple[str, ...]) -> dict:
    target = owned / "private-config" / ("owned.plist" if sys.platform == "darwin" else "owned.desktop")
    original = startup_posix._target
    try:
        startup_posix._target = lambda: target
        require(not startup_posix.inspect().installed and not target.parent.exists(), "Inspection created metadata")
        require(startup_posix.apply(True, arguments).installed, "Native owned metadata installation failed")
        require(target.stat().st_mode & 0o777 == _PRIVATE_MODE, "Native metadata is not private")
        require(not startup_posix.apply(False, arguments).installed, "Native metadata removal failed")
        target.write_text("owned collision fixture", encoding="utf-8")
        refused = []
        for enabled in (True, False):
            try:
                startup_posix.apply(enabled, arguments)
            except OSError:
                refused.append(enabled)
        require(refused == [True, False] and target.read_text(encoding="utf-8") == "owned collision fixture",
                "Native foreign-shape fixture was overwritten or removed")
        return {"backend": "private POSIX metadata", "install_remove": True, "private_mode": True,
                "changed_entry_refused": True, "host_login_entry_modified": False}
    finally:
        startup_posix._target = original


def main() -> None:
    """Preserve partial phase evidence and verify native APIs without actually registering a login job."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    proof = {"phase": "started", "platform": sys.platform, "host_login_entry_modified": False,
             "actual_login_launch_verified": False}
    try:
        with tempfile.TemporaryDirectory(prefix="filetree-autostart-owned-") as scratch:
            owned = Path(scratch).resolve(strict=True)
            arguments = (str(owned / "FileTree 保留 with space"), "--background")
            proof["registration"] = _windows(arguments) if os.name == "nt" else _posix(owned, arguments)
        proof["owned_fixture_cleanup"] = True
        proof["phase"] = "complete"
    finally:
        with _atomic_file(args.output, encoding="utf-8") as stream:
            json.dump(proof, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()
