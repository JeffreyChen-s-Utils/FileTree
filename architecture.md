# FileTree Architecture

Short overview of how FileTree is put together. Keep it current: a change to any section below updates
this file in the same commit.

## 1. Purpose

A disk-usage viewer: scan a folder or drive, add up every file, and show where the space goes — a folder
tree sorted largest first, a squarified treemap, the largest files and the space per file type — with a
safe way to free space (move to the Recycle Bin / Trash, never a permanent delete).

## 2. Layers and directories

| Layer | Path | Depends on | Holds |
|---|---|---|---|
| Core | `file_tree/core/` | standard library only | `node.py` (the tree), `scanner.py` (parallel scan), `allocation.py` (size on disk), `analysis.py` (largest files, per-type and per-age totals), `search.py` (find by name), `treemap.py` (layout), `formatting.py`, `export.py` (CSV / JSON) |
| GUI | `file_tree/gui/` | PySide6, core | `app.py` (start-up), `main_window.py`, `welcome.py`, `scan_bar.py`, `results_view.py`, `search_panel.py`, `tree_model.py`, `tables.py`, `treemap_widget.py`, `delegates.py`, `scan_worker.py`, `file_actions.py`, `help_dialog.py`, `i18n.py` + `strings.py`, `qt_translation.py`, `elevation.py`, `icon.py` (drawn in code) |
| Entry script | `start_file_tree.py` | GUI | Starts the window from a source copy; the file Nuitka compiles |
| Tools | `tools/` | GUI | `make_screenshots.py` (README pictures), `build_nuitka.py` (stand-alone builds, see `nuitka.md`) |
| Tests | `test/` | both | one file per area; Qt tests on the offscreen platform |

The core never imports Qt or the GUI (`test/test_layers.py`).

## 3. Entry points and public interfaces

- `file-tree [folder]` (the `gui-scripts` entry `file_tree.gui.app:run`), `python start_file_tree.py [folder]`
  and `python -m file_tree [folder]`: all three call `app.run()`, which opens the window and scans `folder`
  right away if given (`test/test_start_script.py`).
- `python tools/build_nuitka.py [--onefile | --app] [Nuitka options]`: compiles `start_file_tree.py` into
  `build/<mode>/`, copying Qt's translation catalogues listed in `qt_translation.CATALOGUES`.
- `file_tree.core.scanner.scan(path, *, options, progress, cancel)` → `ScanResult(root, errors, elapsed)`.
- `file_tree.core.analysis.summarise(root, limit)` → largest files and per-extension totals in one pass.
- `file_tree.core.treemap.layout(root, rect, ...)` → `Tile`s; `export.export_*` write CSV / JSON.

## 4. Main flows

**Scan.** `MainWindow.start_scan` opens the results page with its `ScanBar` and starts a `ScanWorker` (a
`QThread`) running `scan()`: worker threads (default 4, measured) share one stack of folders; each lists a
folder with `os.scandir`, turns entries into `Node`s without following links, and pushes subfolders back.
A file's size on disk (`Node.allocated`) comes from `allocation.allocation_for(root)`: `st_blocks` on POSIX;
on Windows the size rounded up to the volume's clusters, the system asked only for compressed or sparse
files, 0 for files whose data is elsewhere (cloud placeholders, offline), never opening those.
Each finished folder's files are added to the running totals of every folder above it. The root is handed
out first (`started`), so `FolderTreeModel` shows the tree in live mode while it grows: each folder's
children are a sorted copy frozen until the next `refresh()`, which the window calls every 700 ms (a layout
change that moves persistent indexes, so expanded folders, selection and scroll position survive). The
calling thread reports progress about ten times a second and watches the cancel event. When every folder
is read, totals are added up again bottom-up and children sorted largest first; `analyse()` (largest
files, per-type totals) runs still off the GUI thread and `succeeded(ScanOutcome)` ends live mode. Stop
raises `ScanCancelledError` carrying the partial tree (unread folders marked `NOT_SCANNED`), shown as an
incomplete outcome. Signals of a replaced worker are ignored.

**Show.** `ResultsView.show_outcome` hands the tree to `FolderTreeModel` (which wraps the `Node`s, sorts
per folder lazily, and never copies), the tables to their models, and the root to `TreemapWidget` (layout
and drawing cached in a pixmap, recomputed on resize or zoom). Selecting anything selects it in the tree and
outlines it in the treemap.

**Free space.** Context menu or Delete → one confirmation → `QFile.moveToTrash` per entry →
`ResultsView.forget`. The tree and the largest-files list allow several rows to be selected; the entries acted
on are `node.outermost` of the selection without the scanned folder (an entry inside a chosen folder goes with
it). `FolderTreeModel.remove` detaches each node and subtracts its totals from every folder above; the
largest files, per-type and per-age totals and treemap are updated once, without a rescan. Entries the system
refuses stay and are named in a warning.

**Rescan one folder.** The context menu's *Rescan this folder* runs a `ScanWorker` on that branch alone,
then `FolderTreeModel.replace` swaps it in (`Node.replace_with` corrects every total above it; persistent
indexes inside the old branch are dropped, the rest follow their nodes) and an `AnalyseWorker` recomputes
the largest files and per-type and per-age totals of the whole tree off the GUI thread.

**Search.** The Search tab (`SearchPanel`, Ctrl+F) waits for typing to pause, then runs `core.search.search`
on a `SearchWorker` thread: names are matched case-insensitively (plain text anywhere in the name, `*`/`?`
patterns against the whole name, several separated by `;`) and the 1,000 largest matches are shown with the
count and size of all. A new search stops the one before (it checks once per folder) and only the latest
result is shown. The box is disabled while a scan fills the tree; the search runs again after a scan, a
move to the Recycle Bin or a folder rescan.

**Administrator rights (Windows).** Before the window opens, `app.main` asks `elevation.relaunch_elevated`
to start a second copy through the "runas" verb (the UAC prompt) unless the `ask_admin_at_start` setting is
off or FileTree already is elevated; if that copy starts, this one exits, and a declined prompt just
continues. The File menu and the Problems tab (shown when folders were denied) offer the same restart, with
the scanned folder as its argument. A built program restarts itself; from Python it is `-m file_tree`.

**Language.** `i18n.set_language` + `qt_translation.apply_qt_translation` (Qt's own buttons and dialogs),
then every widget's `retranslate()`. The choice is stored in `QSettings` with the unit, window layout and
recent folders.

## 5. Extension points

- **A language**: a table in `file_tree/gui/strings.py`, an entry in `i18n.LANGUAGES`, a Qt catalogue in
  `qt_translation.CATALOGUES`, a README translation and a screenshot (`tools/make_screenshots.py`).
- **A file-type group**: `analysis.CATEGORY_EXTENSIONS`, a colour in `treemap_widget.CATEGORY_COLOURS`
  and a `category_<name>` text in every language (tests check all three).
- **An export format**: a function in `core/export.py` (atomic write) and an action in `main_window.py`.
- **A result tab**: a widget added in `ResultsView._assemble`, fed from `ScanOutcome`.

## 6. Cross-project boundaries

None. FileTree is standalone: no other repository imports it or calls its command line, and it depends on
no other repository in the workspace — only on PySide6.

## 7. Design constraints

- Scanning speed, measured on an SSD with a warm cache: 62,000 files in 0.67 s with 4 threads (1.27 s with
  one); 740,000 entries in 6–8 s; analysis 0.65 s; treemap layout under 0.1 s (at most 20,000 tiles).
- Memory: about 250 bytes per entry (740,000 entries ≈ 185 MB); only the root stores a full path.
- Links are never followed; unreadable folders are recorded, never fatal.
- Nothing is deleted permanently; every move to the trash is confirmed.

## 8. When to update this file

When a module is added, removed or changes layer; when a flow in §4 changes; when an extension point or a
constraint changes; when another repository starts depending on FileTree (§6).
