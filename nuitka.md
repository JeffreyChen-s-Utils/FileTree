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

Archive previews lazily import `py7zr` and `rarfile` outside the stdlib-only core. Install `requirements.txt` before compiling; Nuitka follows the adapter imports and their decoder dependencies. Native Windows/Linux/macOS Python 3.12 release wheels are pinned with verified hashes in `.github/requirements/archives.txt`. External RAR tools are not bundled: `unrar` or `bsdtar` must be on PATH; previews never run them or extract files.

Similar-photo search imports `Pillow` only when requested, outside the stdlib-only core. Nuitka follows the image adapter and its native decoders. The native Windows/Linux/macOS Python 3.12 build pins its verified binary wheels in `.github/requirements/photos.txt`; install `requirements.txt` before local compilation. No external image programs or model assets are bundled.

Regenerate compiler runtime hashes with py -3 tools/lock_compiler_wheels.py: every exact dependency version is retained, published wheel hashes cover native platforms, and source/yanked distributions are excluded. This does not change the isolated PyPI publishing lock.

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

On Windows with the .NET 8 SDK, build an x64 MSI from the same complete standalone output:

```bash
dotnet tool install wix --global --version 6.0.2
python tools/build_msi.py --version 0.1.0
python tools/prepare_packages.py --version 0.1.0
```

This writes `FileTree-0.1.0-windows-x64.msi`. The compiler version is checked; payload links,
unsupported MSI versions, changed runtime inventories and failed builds refuse publication. WiX
validation remains enabled. The per-machine package includes all runtime files and a Start-menu
shortcut, supports major upgrades, and uses no custom actions/startup registration. Its installer
requires administrator approval; the builder only compiles. The release workflow attaches it from
the same tag. The Desktop builds workflow shares the release's pinned tooling through
`tools/install_compiler.py`; it compiles a standalone program and retains its ZIP/MSI plus native
install/upgrade/removal evidence. Package-version upgrade validation copies the compiled payload
to fresh runner scratch and adds only an owned marker; the original output is preserved and never
launched. Native install/upgrade/removal checks passed for all 104 upgraded files; these checks do
not prove GUI launch or OS consent. The draft command requires the matching MSI and standalone ZIP
in the current directory. It creates a fresh `package-drafts` folder with actual hashes/ProductCode,
winget manifests, a Scoop manifest and a Chocolatey package source. Read-only MSI inspection never
installs anything. Native winget validation passed; no store is submitted. CI retains the drafts and
release attaches their ZIP. Store accounts and matching published release URLs remain required.

### 2.2 A single file

```bash
python tools/build_nuitka.py --onefile
```

The result is one file, `build/onefile/FileTree.exe` (`build/onefile/FileTree` elsewhere). It is easier to hand around,
but every start unpacks it to a temporary folder first, so it opens a little more slowly.

### 2.3 A macOS app bundle

```bash
python tools/build_nuitka.py --app
python tools/package_posix.py --platform macos --source build/app/FileTree.app --version 0.1.0
```

The bundle is `build/app/FileTree.app`. The package command writes its complete ZIP and proof into
a fresh `desktop-package` folder. Native ditto extraction must preserve every ordinary file and
internal framework link. Bundle identity/version/executable are checked; external links are refused.

The program gets FileTree's own icon on Windows, Linux and macOS (the script draws it into `build/`). Any other
option is passed on to Nuitka unchanged, for example a different icon:
`python tools/build_nuitka.py --windows-icon-from-ico=icon.ico` (Windows), `--linux-icon=icon.png` or
`--macos-app-icon=icon.icns` (Nuitka converts the generated PNG for macOS by default).

### 2.4 A Linux AppImage

```bash
python tools/build_nuitka.py --jobs=2
python tools/package_posix.py --platform linux --source build/standalone/start_file_tree.dist --version 0.1.0
```

Use the actual sole `.dist` folder from your build if its name differs. Native x86_64 Linux packaging
preserves the whole Qt runtime and translations in the AppDir, with a literal AppRun launcher and
generated icon. Packaging tool 1.9.1 and runtime 20251108 are SHA-256 pinned; the runtime is supplied
explicitly instead of downloading latest. No FUSE mount is needed during packaging. Native image
extraction must reproduce the complete runtime, and source hashes/identities must remain unchanged.
The AppImage and proof publish together into a fresh `desktop-package`; existing arrivals are refused.

Desktop builds CI uses Ubuntu 22.04 x86_64 and macOS 15 arm64 and retains these development artifacts
for seven days without a release token or application launch. Release reuse is gated by repository
variable `FILETREE_POSIX_RELEASE_VERIFIED=true`, to be set only after progress item #4 is verified.
This change does not set that variable, provide Developer ID signing/notarization or prove Finder/OS
consent. AppImage login registration uses its original executable outside the mount.

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
| `--windows-icon-from-ico=build/FileTree.ico` / `--linux-icon=build/FileTree.png` / `--macos-app-icon=build/FileTree.png` | FileTree's icon, drawn by the script (left out when you pass an icon yourself) |
| `--macos-app-name=FileTree` (with `--app` only) | The name shown in Finder and the Dock |
| `--macos-signed-app-name=io.github.jechen.FileTree` (with `--app` only) | Stable bundle identity; this does not provide a Developer ID certificate |
| `--macos-app-version=<checked-in version>` (with `--app` only) | Bundle version matches the program without a manual bump |

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
