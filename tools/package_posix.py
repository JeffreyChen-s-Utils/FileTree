"""Package complete Linux/macOS compiler output with owned native extraction and source hash checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from je_file_tree.core.no_replace import anchored_directory, directory_stamps, rename_no_replace  # noqa: E402
from tools.build_msi import _version  # noqa: E402

_ASSETS = {
    "appimagetool": ("AppImage/appimagetool/1.9.1/appimagetool-x86_64.AppImage",
                     "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"),
    "runtime": ("AppImage/type2-runtime/20251108/runtime-x86_64",
                "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"),
}
_MAX_DOWNLOAD = 64 * 1024 * 1024
_CATALOGUES = ("qtbase_zh_TW.qm", "qtbase_zh_CN.qm", "qtbase_ja.qm", "qtbase_ko.qm")


def _hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _inventory(root: Path, *, links: bool) -> dict[str, tuple]:
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("Compiler payload must be an ordinary directory")
    entries, pending = {}, [root]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            info = path.lstat()
            name, mode = path.relative_to(root).as_posix(), stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                if not links or not path.resolve(strict=True).is_relative_to(root.resolve()):
                    raise ValueError("External or unsupported payload link")
                value = ("link", mode, os.readlink(path))
            elif stat.S_ISDIR(info.st_mode):
                value = ("directory", mode)
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                value = ("file", mode, info.st_size, _hash(path))
            else:
                raise ValueError("Special compiler payload entry")
            entries[name] = value
    return entries


def _complete(root: Path, kind: str) -> dict[str, tuple]:
    entries = _inventory(root, links=kind == "macos")
    leaves = {Path(name).name for name in entries}
    required = {"FileTree", *_CATALOGUES, "libqcocoa.dylib" if kind == "macos" else "libqxcb.so"}
    cores = {"QtCore", "libQt6Core.6.dylib"} if kind == "macos" else {"libQt6Core.so.6"}
    if not required <= leaves or not leaves & cores:
        raise ValueError("Compiler payload lacks the program, Qt runtime/plugin or translations")
    program = root / ("Contents/MacOS/FileTree" if kind == "macos" else "FileTree")
    if not stat.S_ISREG(program.lstat().st_mode):
        raise ValueError("Compiler program must be an ordinary executable")
    if os.name != "nt" and not program.stat().st_mode & 0o111:
        raise ValueError("Compiler program lacks native executable permission")
    return entries


def _identities(root: Path, names: dict) -> dict[str, tuple]:
    captured = {}
    for name in (".", *names):
        info = (root / name).lstat()
        captured[name] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return captured


def _download(name: str, folder: Path) -> Path:
    asset, checksum = _ASSETS[name]
    organization, repository, version, filename = asset.split("/")
    url = f"https://github.com/{organization}/{repository}/releases/download/{version}/{filename}"
    target, total, deadline = folder / name, 0, time.monotonic() + 120
    with urlopen(url, timeout=30) as source, target.open("xb") as output:  # noqa: S310 - fixed HTTPS assets
        for block in iter(lambda: source.read(1024 * 1024), b""):
            total += len(block)
            if total > _MAX_DOWNLOAD or time.monotonic() > deadline:
                raise OSError("Pinned AppImage tool download exceeded its bound")
            output.write(block)
    if _hash(target) != checksum:
        raise ValueError("Pinned AppImage tool checksum mismatch")
    target.chmod(0o755)
    return target


def _run(arguments: list[str], directory: Path, environment: dict | None = None) -> None:
    subprocess.run(arguments, cwd=directory, env=environment, check=True, timeout=300)  # noqa: S603


def _appimage(source: Path, scratch: Path, version: str, before: dict) -> Path:
    appdir = scratch / "FileTree.AppDir"
    payload = appdir / "usr/bin/filetree"
    shutil.copytree(source, payload)
    if _inventory(payload, links=False) != before:
        raise OSError("Copied Linux runtime differs from compiler output")
    icon = source.parent.parent / "FileTree.png"
    if not stat.S_ISREG(icon.lstat().st_mode):
        raise ValueError("Generated program icon is missing or linked")
    for name in ("filetree.png", ".DirIcon"):
        shutil.copyfile(icon, appdir / name)
    (appdir / "filetree.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=FileTree\nExec=FileTree\nIcon=filetree\n"
        "Terminal=false\nCategories=Utility;System;\n", encoding="utf-8")
    (appdir / "AppRun").write_text(
        '#!/bin/sh\nset -eu\nexec "$APPDIR/usr/bin/filetree/FileTree" "$@"\n', encoding="utf-8")
    (appdir / "AppRun").chmod(0o755)
    tool, runtime = _download("appimagetool", scratch), _download("runtime", scratch)
    target = scratch / f"FileTree-{version}-linux-x86_64.AppImage"
    environment = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1", "VERSION": version}
    _run([str(tool), "--no-appstream", "--runtime-file", str(runtime), str(appdir), str(target)],
         scratch, environment)
    extracted = scratch / "extracted"
    extracted.mkdir()
    _run([str(target), "--appimage-extract"], extracted)
    if _inventory(extracted / "squashfs-root", links=False) != _inventory(appdir, links=False):
        raise OSError("Native AppImage extraction differs from the complete AppDir")
    return target


def _macos(source: Path, scratch: Path, version: str, before: dict) -> Path:
    metadata = plistlib.loads((source / "Contents/Info.plist").read_bytes())
    if (metadata.get("CFBundleIdentifier") != "io.github.jechen.FileTree"
            or metadata.get("CFBundleShortVersionString") != version
            or metadata.get("CFBundleExecutable") != "FileTree"):
        raise ValueError("Compiled macOS bundle metadata differs from the program contract")
    target = scratch / f"FileTree-{version}-macos-{platform.machine()}.zip"
    bundle = scratch / "FileTree.app"
    _run(["/usr/bin/ditto", str(source), str(bundle)], scratch)
    if _inventory(bundle, links=True) != before:
        raise OSError("Native macOS staging differs from the complete compiler bundle")
    _run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(target)], scratch)
    extracted = scratch / "extracted"
    extracted.mkdir()
    _run(["/usr/bin/ditto", "-x", "-k", str(target), str(extracted)], scratch)
    if _inventory(extracted / bundle.name, links=True) != before:
        raise OSError("Native macOS extraction differs from the complete bundle")
    return target


def package_posix(kind: str, source: Path, version: str, output: Path) -> Path:
    """Exclusively publish a complete native desktop archive after extraction/source checks.

    Linux executes only fixed SHA-256-pinned packaging tools and the owned image's extraction mode.
    macOS runs fixed ditto only. Neither launches FileTree, signs/notarizes or releases an artifact.
    Internal macOS framework links are preserved; external links and Linux payload links are refused.
    """
    _version(version)
    if kind not in ("linux", "macos") or sys.platform != ("linux" if kind == "linux" else "darwin"):
        raise OSError("Desktop packaging requires its matching native platform")
    if kind == "linux" and platform.machine() != "x86_64":
        raise OSError("The pinned AppImage tools support x86_64 only")
    before = _complete(source, kind)
    identities = _identities(source, before)
    output = output.absolute().parent.resolve() / output.name
    if output.is_relative_to(source.resolve()):
        raise ValueError("Archive output must be outside the compiler payload")
    if output.exists():
        raise FileExistsError("Desktop package output must be a fresh directory")
    with (anchored_directory(directory_stamps(str(source.absolute()))),
          anchored_directory(directory_stamps(str(output.parent))) as descriptor,
          tempfile.TemporaryDirectory(prefix="filetree-posix-package-", dir=output.parent) as temporary):
        scratch = Path(temporary)
        artifact = (_appimage if kind == "linux" else _macos)(source.absolute(), scratch, version, before)
        if (_inventory(source, links=kind == "macos") != before
                or _identities(source, before) != identities):
            raise OSError("Compiler output changed during native packaging")
        if not stat.S_ISREG(artifact.lstat().st_mode) or not artifact.stat().st_size:
            raise ValueError("Native packaging produced no ordinary artifact")
        proof = {"platform": kind, "architecture": platform.machine(), "version": version,
                 "source_entries": len(before), "source_preserved": True, "extraction_verified": True,
                 "app_launched": False, "published": False, "sha256": _hash(artifact)}
        ready = scratch / "ready"
        ready.mkdir()
        artifact.rename(ready / artifact.name)
        (ready / "proof.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        with anchored_directory(directory_stamps(str(scratch))) as source_descriptor:
            rename_no_replace(str(ready), str(output), source_descriptor, descriptor)
        destination = output / artifact.name
    return destination


def main() -> None:
    """Package a completed native build without installation or release actions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=("linux", "macos"))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=Path("desktop-package"))
    options = parser.parse_args()
    try:
        result = package_posix(options.platform, options.source, options.version, options.output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    sys.stdout.write(str(result) + "\n")


if __name__ == "__main__":
    main()
