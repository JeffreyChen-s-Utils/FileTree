# Building FileTree with Nuitka

[English](nuitka.md) | [繁體中文](nuitka.zh-TW.md) | [简体中文](nuitka.zh-CN.md)

[Nuitka](https://nuitka.net/) turns FileTree into a native program that runs on computers without
Python. It translates the Python code to C and compiles it, so the program starts quickly; the price is a
longer build. The entry point it compiles is `start_file_tree.py` in the repository root.

> Nuitka builds for the system it runs on: build on Windows for Windows, on macOS for macOS, on Linux for
> Linux. It cannot cross-compile.

The chart SVG exporter imports PySide6.QtSvg; Nuitka follows this import and includes the Qt SVG library. It uses the same PySide6 dependency as the window.

Printing and view PDF export import PySide6.QtPrintSupport, collected by the existing PySide6 plugin. Native printing needs the system printer service; PDF output uses Qt's PDF engine.

## 1. Prepare

Excel reports import `openpyxl` outside the stdlib-only core. Install `requirements.txt` before compiling; Nuitka follows this import and its `et-xmlfile` dependency. The executable release installs the universal wheels at verified hashes from `.github/requirements/reports.txt`, independently of the publishing job's tooling lock. HTML embeds Qt-encoded PNGs and needs no browser or image dependency.

Archive previews lazily import `py7zr` and `rarfile` outside the stdlib-only core. Install `requirements.txt` before compiling; Nuitka follows the adapter imports and their decoder dependencies. Windows Python 3.12 release wheels are pinned with verified hashes in `.github/requirements/archives.txt`. External RAR tools are not bundled: `unrar` or `bsdtar` must be on PATH; previews never run them or extract files.

Similar-photo search imports `Pillow` only when requested, outside the stdlib-only core. Nuitka follows the image adapter and its native decoders. The Windows Python 3.12 executable build pins its verified binary wheel in `.github/requirements/photos.txt`; install `requirements.txt` before local compilation. No external image programs or model assets are bundled.

### 1.1 Python packages (every system)

Use a virtual environment so the build contains only what FileTree needs:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install nuitka ordered-set zstandard
```

On macOS and Linux activate it with `source .venv/bin/activate` instead.

### 1.2 A C compiler

| System | What to install |
|---|---|
| Windows | Visual Studio Build Tools with the "Desktop development with C++" workload. Without it, Nuitka offers to download MinGW64 on the first build (`--assume-yes-for-downloads` answers yes). |
| Linux | `build-essential` and `patchelf` (Debian / Ubuntu: `sudo apt install build-essential patchelf`) |
| macOS | The Command Line Tools: `xcode-select --install` |

## 2. Build

Run these from the repository root with the virtual environment active. `tools/build_nuitka.py` finds
where PySide6 is installed and runs Nuitka with the options in §3; it also prints the full command.

### 2.1 A program folder (recommended)

```bash
python tools/build_nuitka.py
```

The result is the folder `build/standalone/start_file_tree.dist/`, with `FileTree.exe` (on Linux and macOS
`FileTree`) inside. Copy the **whole folder** to another computer and start the program from it. This
form starts the fastest.

For a Windows release, package the complete folder (use the release's version):

```bash
python tools/package_standalone.py --version 0.1.0
```

This writes `FileTree-0.1.0-windows-standalone.zip` in the repository root, containing a versioned
folder with the EXE, all libraries, plugins and translation catalogues. It requires exactly one
completed `.dist` folder with `FileTree.exe` under `build/standalone`, rejects links/junctions and
writes the archive atomically. The release workflow builds both forms from the same tag and attaches
both the standalone ZIP and the single EXE.

### 2.2 A single file

```bash
python tools/build_nuitka.py --onefile
```

The result is one file, `build/onefile/FileTree.exe` (`build/onefile/FileTree` elsewhere). It is easier to hand around,
but every start unpacks it to a temporary folder first, so it opens a little more slowly.

### 2.3 A macOS app bundle

```bash
python tools/build_nuitka.py --app
```

The result is `build/app/FileTree.app`.

The program gets FileTree's own icon on Windows and Linux (the script draws it into `build/`). Any other
option is passed on to Nuitka unchanged, for example a different icon:
`python tools/build_nuitka.py --windows-icon-from-ico=icon.ico` (Windows), `--linux-icon=icon.png` or
`--macos-app-icon=icon.icns` (macOS has no icon otherwise).

## 3. What the script runs

| Option | Why |
|---|---|
| `--mode=standalone` / `--mode=onefile` / `--mode=app` | A folder, one file, or (on macOS) an app bundle |
| `--enable-plugin=pyside6` | Copies the Qt libraries and plugins the window needs |
| `--include-data-files=<Qt translations>/qtbase_zh_TW.qm=<same place in the build>` (and `qtbase_zh_CN.qm`) | Nuitka does not copy Qt's own translations; without them the Yes / No / Close buttons stay in English. The folder depends on the installation (`PySide6/translations` on Windows, `PySide6/Qt/translations` on Linux), which is why a script runs the build |
| `--windows-console-mode=disable` | No black console window next to FileTree on Windows (ignored elsewhere) |
| `--output-dir=build/standalone` (or `build/onefile`, `build/app`) | Everything Nuitka creates goes into `build/`, which Git ignores; each form has its own folder, so building one does not delete another |
| `--output-filename=FileTree` | The program is called FileTree instead of start_file_tree |
| `--assume-yes-for-downloads` | Lets Nuitka fetch helper tools it needs without asking |
| `--windows-icon-from-ico=build/FileTree.ico` / `--linux-icon=build/FileTree.png` | FileTree's icon, drawn by the script (left out when you pass an icon yourself) |
| `--macos-app-name=FileTree` (with `--app` only) | The name shown in Finder and the Dock |

The entry point is `start_file_tree.py`, the same program as `python -m je_file_tree`.

## 4. Check the build

1. Start the program from the build folder and scan a folder.
2. Switch to another language under **View → Language**, then move something to the Recycle Bin and
   cancel: the Yes / No buttons must be in that language too. If they stay in English, Qt's translation
   files are missing from the build.
3. Open **Help → How to use**.

## 5. Problems

| What you see | What to do |
|---|---|
| Yes / No / Close stay in English in the built program | Nuitka was run by hand without the translation files. Build with `python tools/build_nuitka.py`, which adds them. |
| Nuitka stops because there is no C compiler | Install the compiler from §1.2. On Windows, without Visual Studio, Nuitka downloads MinGW64 by itself (the script answers yes for you). |
| Other programs become slow while it builds | Nuitka compiles with every CPU core. Pass `--jobs=2` (`python tools/build_nuitka.py --jobs=2`) to leave the rest of the computer room. |
| The first build takes a long time | Normal: Nuitka compiles Qt's Python bindings once and reuses the result, so later builds are faster. |
| An antivirus program quarantines the new `.exe` | New, unsigned executables are sometimes flagged. Allow the build folder, or sign the program. |
| `patchelf` not found (Linux) | `sudo apt install patchelf`, then build again. |
