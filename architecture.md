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
| Core | `file_tree/core/` | standard library only | `node.py` (the tree), `scanner.py` (parallel scan), `analysis.py` (largest files, per-type totals), `treemap.py` (layout), `formatting.py`, `export.py` (CSV / JSON) |
| GUI | `file_tree/gui/` | PySide6, core | `app.py` (start-up), `main_window.py`, `welcome.py`, `scan_page.py`, `results_view.py`, `tree_model.py`, `tables.py`, `treemap_widget.py`, `delegates.py`, `scan_worker.py`, `file_actions.py`, `help_dialog.py`, `i18n.py` + `strings.py`, `qt_translation.py` |
| Tools | `tools/` | GUI | `make_screenshots.py` (README pictures) |
| Tests | `test/` | both | one file per area; Qt tests on the offscreen platform |

The core never imports Qt or the GUI (`test/test_layers.py`).

## 3. Entry points and public interfaces

- `file-tree [folder]` (the `gui-scripts` entry `file_tree.gui.app:run`) and `python -m file_tree [folder]`: open
  the window, scanning `folder` right away if given.
- `file_tree.core.scanner.scan(path, *, options, progress, cancel)` → `ScanResult(root, errors, elapsed)`.
- `file_tree.core.analysis.summarise(root, limit)` → largest files and per-extension totals in one pass.
- `file_tree.core.treemap.layout(root, rect, ...)` → `Tile`s; `export.export_*` write CSV / JSON.

## 4. Main flows

**Scan.** `MainWindow.start_scan` → `ScanWorker` (a `QThread`) runs `scan()`: worker threads (default
4, measured) share one stack of folders; each lists a folder with `os.scandir`, turns entries into `Node`s
without following links, and pushes subfolders back. The calling thread reports progress about ten times a
second and watches the cancel event. When every folder is read, totals are added bottom-up and children
sorted largest first. The worker then runs `analyse()` (largest files, per-type totals) still off the GUI
thread and emits `succeeded(ScanOutcome)`. Signals of a replaced worker are ignored.

**Show.** `ResultsView.show_outcome` hands the tree to `FolderTreeModel` (which wraps the `Node`s, sorts
per folder lazily, and never copies), the tables to their models, and the root to `TreemapWidget` (layout
and drawing cached in a pixmap, recomputed on resize or zoom). Selecting anything selects it in the tree and
outlines it in the treemap.

**Free space.** Context menu or Delete → confirmation → `QFile.moveToTrash` → `ResultsView.forget`:
`FolderTreeModel.remove` detaches the node and subtracts its totals from every folder above; the largest
files, per-type totals and treemap are updated without a rescan.

**Language.** `i18n.set_language` + `qt_translation.apply_qt_translation` (Qt's own buttons and dialogs),
then every widget's `retranslate()`. The choice is stored in `QSettings` with the unit, window layout and
recent folders.

## 5. Extension points

- **A language**: a table in `file_tree/gui/strings.py`, an entry in `i18n.LANGUAGES`, a Qt catalogue in
  `qt_translation._CATALOGUES`, a README translation and a screenshot (`tools/make_screenshots.py`).
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
