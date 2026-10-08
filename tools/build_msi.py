"""Build a WiX 6 x64 MSI from the complete Windows standalone folder; never install it locally."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.package_standalone import _linked  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_WIX_VERSION = "6.0.2"
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
_LIMITS = (255, 255, 65535)


def _version(version: str) -> None:
    if (_VERSION.fullmatch(version) is None
            or any(value > limit for value, limit in zip(map(int, version.split(".")), _LIMITS, strict=True))):
        raise ValueError("MSI version must be major.minor.patch within 255.255.65535")


def _inventory(folder: Path) -> dict[str, tuple]:
    result = {}
    pending = [folder]
    while pending:
        path = pending.pop()
        info = path.lstat()
        if _linked(path) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("MSI payload must not contain links, junctions or other reparse entries")
        if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
            raise ValueError("MSI payload must contain only ordinary files/directories")
        digest = None
        if stat.S_ISDIR(info.st_mode):
            pending.extend(sorted(path.iterdir(), reverse=True))
        else:
            checksum = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    checksum.update(block)
            digest = checksum.hexdigest()
        result[path.relative_to(folder).as_posix()] = (info.st_dev, info.st_ino, info.st_size, digest)
    return result


def build_msi(source: Path, version: str, output: Path) -> Path:
    """Validate and hash a single complete build, then atomically publish only a successful WiX MSI.

    WiX 6.0.2 must already be on PATH. This tool never elevates, installs/uninstalls a product,
    changes a version or suppresses Windows Installer validation. The package installs machine-wide
    under Program Files with a Start-menu shortcut; it contains no custom actions or startup entry.
    Compilation and inventory checks are observations, not protection against malicious build inputs.
    """
    _version(version)
    folders = [folder for folder in source.glob("*.dist") if (folder / "FileTree.exe").is_file()]
    if len(folders) != 1:
        raise ValueError("expected exactly one standalone .dist folder containing FileTree.exe")
    folder = folders[0].absolute()
    if output.resolve().is_relative_to(folder.resolve()):
        raise ValueError("MSI output must be outside the standalone folder")
    before = _inventory(folder)
    wix = shutil.which("wix")
    if wix is None:
        raise FileNotFoundError("WiX 6.0.2 is required on PATH")
    observed = subprocess.run([wix, "--version"], check=True, capture_output=True, encoding="utf-8",  # noqa: S603
                              timeout=30).stdout.strip()
    if observed.split("+")[0] != _WIX_VERSION:
        raise ValueError(f"WiX {_WIX_VERSION} required; found {observed}")
    target = output / f"FileTree-{version}-windows-x64.msi"
    with tempfile.TemporaryDirectory(prefix="filetree-msi-", dir=output) as temporary:
        compiled = Path(temporary) / target.name
        command = [wix, "build", str(_ROOT / "tools/installer/FileTree.wxs"), "-arch", "x64",
                   "-d", f"Version={version}", "-d", f"Payload={folder}", "-out", str(compiled)]
        subprocess.run(command, check=True, timeout=180)  # noqa: S603
        if not compiled.is_file() or compiled.stat().st_size == 0:
            raise OSError("WiX did not produce a complete MSI")
        if _inventory(folder) != before:
            raise OSError("Standalone payload changed during MSI compilation")
        compiled.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    """Build from a completed standalone output; print the artifact path without installing it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", type=Path, default=Path("build/standalone"))
    parser.add_argument("--output", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        target = build_msi(args.source, args.version, args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    sys.stdout.write(str(target) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
