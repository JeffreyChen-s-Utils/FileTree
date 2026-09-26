# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed. Priority: **P1** next, **P2** worth doing, **P3** only if wanted.
Suggested order: #36 (know the limits first), #30, #26, #19 and #20, #39, then the P2 items.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#4** [UNVERIFIED] Linux: "Show in file manager" asks the file manager over D-Bus (`org.freedesktop.FileManager1.ShowItems`, `je_file_tree/gui/file_actions.py` `show_items`) and falls back to opening the folder, but has not run against a real session bus: whether PySide6 sends the list of URIs as the `as` the interface expects is unchecked. Also unchecked on Linux: moving to the Trash (`QFile.moveToTrash`, freedesktop trash spec), a real drag from a file manager, CJK text under X11. The Docker check described in U-20260926-23 (Debian, Xvfb, `dbus-run-session`, a stand-in file manager with the strict `(as, s)` signature, a logging `xdg-open`) was stopped when the machine ran low on memory; rebuild it under `tools/` and run it when memory allows. macOS [BLOCKED]: no Mac or macOS VM on this machine.

### Freeing space

- **#19** (P1) Clean-up suggestions: a tab that lists, after a scan, the known reclaimable places found inside it with their sizes: temporary folders (`%TEMP%`, `C:\Windows\Temp`, `/tmp`), browser caches (the `Cache` folders of Chrome, Edge and Firefox profiles), thumbnail caches, crash dumps (`*.dmp`, `%LOCALAPPDATA%\CrashDumps`), package caches (pip, npm, yarn, Gradle, Maven `.m2`, NuGet), build output (`node_modules`, `__pycache__`, `.pytest_cache`, `target`, `build`, `dist`) and old installers in Downloads (`*.msi`, `*.exe`, `*.dmg` untouched for 90 days). The rules are data in a Qt-free `je_file_tree/core/cleanup.py` (a path or name pattern, a group, a one-line note on what deleting it does), matched in one walk of the tree on a worker thread like `core/search.py`. Nothing is deleted: a suggestion is selected and goes through the existing one-question Recycle Bin path (`je_file_tree/gui/main_window.py:237`). Tests: every rule against a built sample tree; no rule may match inside a system folder that is not a cache.
- **#20** (P1) Empty folders: list folders with no file anywhere beneath (`file_count == 0` is already known for every folder, so no extra reading), in the Clean-up tab of #19, with *Select all* → Recycle Bin. Folders that only hold empty folders are listed once, at the outermost (`node.outermost`).
- **#21** (P2) [DECIDE] Recycle Bin size and emptying: show how much each drive's Recycle Bin holds (Windows `SHQueryRecycleBinW`; the freedesktop Trash folders on Linux) on the welcome page and in the Clean-up tab. Emptying it is a permanent delete, which `CLAUDE.md` rules out ("Nothing is ever deleted permanently"): decide between allowing it after a second, explicit question, or only opening the system's own Recycle Bin window.
- **#22** (P2) [DECIDE] Move to another drive: move the selected folders to a folder on another drive, with a progress dialog, a check that sizes and file counts match before the originals go to the Recycle Bin, and optionally a junction or symbolic link left behind so programs still find their files (as SteamMover does). Risks: files held open, permissions, programs that do not follow junctions. Decide whether FileTree should move data at all.
- **#23** (P3) [DECIDE] NTFS compression: estimate and apply compression per folder (`FSCTL_SET_COMPRESSION` or `compact /c /s`) for folders of compressible types (logs, text, code, uncompressed images), showing size on disk before and after (`je_file_tree/core/allocation.py` already reads compressed sizes). Windows only and changes files in place: decide.
- **#24** (P3) [DECIDE] Duplicates to hard links: turn the extra copies of a duplicate group (`je_file_tree/core/duplicates.py`) into hard links to the kept file, on the same volume only; the space is freed and every path keeps working. Risk: editing one "copy" then changes all of them. Decide.
- **#25** (P2) Duplicate folders: folders whose files are all duplicates of another folder's files (same relative names, sizes and hashes), shown as one line ("Photos 2019 (copy) = Photos 2019") above the file groups; built from the hashes `find_duplicates` already computes, with no extra reading.

### Finding things

- **#26** (P1) Filters in Search: combine conditions with the name pattern (`je_file_tree/core/search.py:44`, `je_file_tree/gui/search_panel.py`): size at least / at most, modified before / after, file-type group, files only or folders only; saved filters with a name ("Videos over 1 GB untouched for a year") kept in the settings. Core: a `Query` dataclass matched in the same walk; the name matcher stays as it is.
- **#27** (P2) Last access and creation time: columns and an age mode "not opened since…" from `st_atime` and the creation time. Windows may not update the last access time (`NtfsDisableLastAccessUpdate`); detect that and say so instead of showing misleading dates. Two more values per `Node`: measure the memory first (the current cost per entry is in U-20260926-14) and consider keeping them for files only.
- **#28** (P2) Space per owner: a Users tab with the size owned by each user. On POSIX `st_uid` comes with the stat the scan already makes; Windows needs `GetNamedSecurityInfoW` per file, an extra call: measure it as #2 was measured and make it an option if it slows the scan.
- **#29** (P2) Cloud-only and special files: list OneDrive/Dropbox placeholders (the recall attributes `je_file_tree/core/allocation.py` already reads), compressed, sparse and offline files, with what they would take once downloaded; today they only count as 0 on disk without a word.

### Scanning

- **#30** (P1) Exclusions: folders and name patterns to skip while scanning (`node_modules`, a backup drive mounted inside a folder, `$Recycle.Bin`), set in a View → Options dialog and kept in the settings. `ScanOptions` (`je_file_tree/core/scanner.py:71`) gets `exclude`, checked in `_read_folder` (`:264`) before a subfolder is queued; an excluded folder is listed like a link (size 0, marked, with a tooltip saying why).
- **#31** (P2) Several folders in one scan: scan a list of roots (for example every drive) under one virtual root, so the charts and lists cover them together; the welcome page (`je_file_tree/gui/welcome.py:22` lists the drives already) gets *Scan all drives*. The virtual root has no path: `Node.path`, the exports and the saved-scan format (`core/compare.py`) must handle it.
- **#32** (P2) Hard links counted once: a file with several names (`st_nlink > 1`) counts in full under each name today, so totals can exceed the drive. On Windows `DirEntry.stat()` leaves `st_nlink` and `st_ino` at 0, so knowing them needs `os.stat` per file, an extra call: measure it and make it an option if it slows the scan; POSIX gets both from the stat already made.
- **#33** (P3) [DECIDE] Read the NTFS master file table directly (as WizTree does): a whole drive in seconds instead of minutes, but it needs administrator rights and a large Windows-only parser (MFT records, attribute lists, `$DATA` runs, hard links, reparse points). Decide after #36 shows how long a full drive takes today.
- **#34** (P2) Follow changes: watch the scanned tree and rescan only the folders that changed, so the numbers stay true without a full rescan. `QFileSystemWatcher` watches each folder separately and does not scale to a whole drive; the USN change journal (Windows) or inotify/fanotify (Linux) do. Reuses the branch rescan (`FolderTreeModel.replace`).
- **#35** (P2) Network shares: check scans of UNC paths (`\\server\share`) and mapped drives: the worker count (`ScanOptions.workers`) may want to be higher on slow links, `allocation.cluster_size` on a share root, access-denied folders, a share that disconnects halfway. Add a hint for UNC paths on the welcome page.
- **#36** (P1) Scale check: scan a full system drive (a few million entries) and record the time and memory in `docs/updates/`; set a budget and fix what breaks: memory per `Node`, the live refresh, the treemap and sunburst limits, search and duplicate times, the JSON export size. Should come before #31 and #33.

### Over time

- **#37** (P2) [DECIDE] Scan history: keep each scan's folder tree (the saved-scan JSON of `core/compare.py`) in a history folder per scanned root, trimmed to a size limit, and show a folder's size over time plus "what grew since last week" without picking a file. Decide where to keep it (`%LOCALAPPDATA%\FileTree\history`?) and how much.
- **#38** (P3) [DECIDE] Background monitor: a tray icon that warns when a drive falls below a free-space threshold and runs scheduled scans for #37. It turns FileTree from a window you open into a program that always runs: decide.

### Reports and automation

- **#39** (P1) Command line without a window: `je-file-tree-cli scan D:\ --folders folders.csv --largest largest.csv --json tree.json` (and `--compare old.json` printing the biggest changes), for scheduled tasks and scripts. Uses only `je_file_tree.core`, so it runs without a display; a console entry in `pyproject.toml` `[project.scripts]` and a new `je_file_tree/cli.py`; documented exit codes; README section in the three languages.
- **#40** (P2) Report: one self-contained HTML file with the summary, the top folders, the largest files, types, ages and the three charts as images (the chart widgets' `grab()`), to send to someone. [DECIDE] whether to add an Excel (.xlsx) export, which needs a dependency such as `openpyxl`.
- **#41** (P3) Print and PDF of the view on screen (`QPrinter`).

### Everyday use

- **#42** (P2) Drive overview: a page with every volume's file system, size, used, free, cluster size and Recycle Bin size (#21), with a free-space bar; double-click scans it. Grows out of the welcome page's drive buttons (`je_file_tree/gui/welcome.py`).
- **#43** (P2) Column chooser and share of the drive: show or hide tree columns from the header's context menu (remembered), and add a "% of drive" column next to "% of parent" (`je_file_tree/gui/tree_model.py` `COLUMN_KEYS`).
- **#44** (P2) Windows shell integration: *Scan with FileTree* in Explorer's folder menu (a verb under `HKCU\Software\Classes\Directory\shell`, added and removed from the Options dialog, no administrator rights needed) and *Properties* in FileTree's context menu (`ShellExecuteExW` with the `properties` verb, `je_file_tree/gui/main_window.py:171`).
- **#45** (P3) Light theme: check the charts and the bar chart's text on a light system theme (every screenshot so far is dark) and offer a light/dark switch.
- **#46** (P3) Accessibility: the chart widgets are painted, so screen readers see nothing: give them accessible names and descriptions, and keyboard navigation (arrow keys between entries, Enter to open a folder, Backspace to go up).

### Distribution

- **#47** (P2) [DECIDE] Sign `FileTree.exe`: an unsigned one-file executable triggers SmartScreen and some antivirus programs. Needs a code-signing certificate (a yearly cost) or Azure Trusted Signing; the release workflow (`.github/workflows/release.yml` `build-exe`) would sign before uploading. Decide.
- **#48** (P3) [DECIDE] Store listings and updates: winget, Scoop or Chocolatey manifests (or an MSI), and an update check that asks GitHub or PyPI for the latest version, a network call FileTree does not make today. Decide.
- **#49** (P2) Linux and macOS builds: an AppImage (or Flatpak) and a macOS `.app` from `tools/build_nuitka.py --app` built on CI runners and attached to the release, after #4 is verified.
