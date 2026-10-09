"""Compile FileTree into a stand-alone program with Nuitka (see nuitka.md).

    python tools/build_nuitka.py             # a program folder: build/standalone/start_file_tree.dist/
    python tools/build_nuitka.py --onefile   # one file: build/onefile/FileTree.exe
    python tools/build_nuitka.py --app       # macOS: build/app/start_file_tree.app

Any other option is passed on to Nuitka unchanged (for example
``--windows-icon-from-ico=icon.ico``). The script exists because one option
depends on where PySide6 is installed: Nuitka does not copy Qt's own
translation catalogues, so without them the Yes / No / Close buttons of the
compiled program stay in English. They are copied to the place Qt looks for
them inside the build, which mirrors where Qt keeps them in the installed
package (``PySide6/translations`` on Windows, ``PySide6/Qt/translations`` on
Linux, so both ends are asked from Qt rather than written here). Each form gets its own
output folder, because a one-file build stages its files in (and then
deletes) the same ``start_file_tree.dist`` folder a folder build produces.
"""

from __future__ import annotations

import argparse
import subprocess  # nosec B404 - runs Nuitka from this interpreter, no shell
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import PySide6  # noqa: E402
from PySide6.QtCore import QLibraryInfo  # noqa: E402

from je_file_tree.gui.icon import draw, icns_bytes, ico_bytes, png_bytes  # noqa: E402
from je_file_tree.gui.qt_translation import CATALOGUES  # noqa: E402
from je_file_tree import __version__  # noqa: E402

ENTRY_POINT = ROOT / "start_file_tree.py"
PROGRAM_NAME = "FileTree"


def qt_translations_folder() -> Path:
    """Where the installed Qt keeps its translation catalogues."""
    return Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))


def translation_options(translations: Path, packages: Path) -> list[str]:
    """``--include-data-files`` options that copy Qt's catalogues for every language FileTree offers.

    ``translations`` is Qt's catalogue folder and ``packages`` the folder holding
    the ``PySide6`` package; inside the build the catalogues keep the same place
    relative to the package, which is where the compiled Qt looks for them.
    """
    target = translations.resolve().relative_to(packages.resolve()).as_posix()
    options = []
    for catalogue in CATALOGUES.values():
        source = translations / f"{catalogue}.qm"
        if not source.is_file():
            raise FileNotFoundError(f"Qt translation catalogue missing: {source}")
        options.append(f"--include-data-files={source}={target}/{catalogue}.qm")
    return options


def icon_options(folder: Path, extra: list[str]) -> list[str]:
    """Write the program icon into ``folder`` and return the Nuitka option that uses it.

    Windows gets a multi-size ``.ico``, macOS a native multi-size ``.icns`` and Linux a PNG.
    No external conversion dependency is required. Nothing is added when ``extra`` already
    names an icon.
    """
    if any(option.split("=")[0].endswith("-icon") or "-icon-" in option for option in extra):
        return []
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        path = folder / f"{PROGRAM_NAME}.ico"
        path.write_bytes(ico_bytes())
        return [f"--windows-icon-from-ico={path}"]
    if sys.platform == "darwin":
        path = folder / f"{PROGRAM_NAME}.icns"
        path.write_bytes(icns_bytes())
        return [f"--macos-app-icon={path}"]
    if sys.platform.startswith("linux"):
        path = folder / f"{PROGRAM_NAME}.png"
        path.write_bytes(png_bytes(draw(256)))
        return [f"--linux-icon={path}"]
    return []


def nuitka_command(mode: str, extra: list[str]) -> list[str]:
    """The full Nuitka command line for ``mode`` (``standalone``, ``onefile`` or ``app``)."""
    command = [
        sys.executable, "-m", "nuitka", f"--mode={mode}", "--enable-plugin=pyside6",
        "--windows-console-mode=disable", f"--output-dir=build/{mode}", f"--output-filename={PROGRAM_NAME}",
        "--assume-yes-for-downloads",
        *translation_options(qt_translations_folder(), Path(PySide6.__file__).parent.parent),
    ]
    if mode == "app":
        command.extend((f"--macos-app-name={PROGRAM_NAME}", "--macos-signed-app-name=io.github.jechen.FileTree",
                        f"--macos-app-version={__version__}"))
    if sys.platform == "win32":
        command.extend((f"--product-name={PROGRAM_NAME}", f"--file-description={PROGRAM_NAME}",
                        f"--product-version={__version__}", f"--file-version={__version__}"))
    return [*command, *extra, str(ENTRY_POINT)]


def main(argv: list[str]) -> int:
    """Parse the options, show the command and run Nuitka; returns Nuitka's exit code."""
    parser = argparse.ArgumentParser(description="Compile FileTree with Nuitka.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--onefile", action="store_true", help="build a single executable file")
    group.add_argument("--app", action="store_true", help="build a macOS app bundle")
    options, extra = parser.parse_known_args(argv)
    mode = "onefile" if options.onefile else "app" if options.app else "standalone"
    command = nuitka_command(mode, [*icon_options(ROOT / "build", extra), *extra])
    sys.stdout.write(" ".join(command) + "\n")
    return subprocess.run(command, cwd=ROOT, check=False).returncode  # noqa: S603 # nosec B603


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
