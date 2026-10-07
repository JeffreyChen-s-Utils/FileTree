"""Archive a complete Windows Nuitka folder for release without publishing a partial ZIP."""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
import tempfile
import zipfile
from pathlib import Path

_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


def package_standalone(source: Path, version: str, output: Path) -> Path:
    """Package the sole complete ``*.dist`` directory under ``source`` into an atomic versioned ZIP."""
    if _VERSION.fullmatch(version) is None:
        raise ValueError("version must have three numeric components")
    folders = [folder for folder in source.glob("*.dist") if (folder / "FileTree.exe").is_file()]
    if len(folders) != 1:
        raise ValueError("expected exactly one standalone .dist folder containing FileTree.exe")
    folder = folders[0]
    if _linked(folder):
        raise ValueError("standalone folder must not be a link or junction")
    if output.resolve().is_relative_to(folder.resolve()):
        raise ValueError("archive output must be outside the standalone folder")
    name = f"FileTree-{version}-windows-standalone"
    target = output / f"{name}.zip"
    descriptor, scratch = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=output)
    os.close(descriptor)
    temporary = Path(scratch)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.rglob("*")):
                if _linked(path):
                    raise ValueError(f"standalone contents must not be links or junctions: {path.name}")
                archive.write(path, f"{name}/{path.relative_to(folder).as_posix()}")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or getattr(info, "st_reparse_tag", 0) in (0xA0000003, 0xA000000C)


def main(argv: list[str] | None = None) -> int:
    """Package a completed build and print its destination; fail before an incomplete archive is published."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", type=Path, default=Path("build/standalone"))
    parser.add_argument("--output", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        target = package_standalone(args.source, args.version, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    sys.stdout.write(str(target) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
