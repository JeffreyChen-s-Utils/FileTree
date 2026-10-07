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
| Core | `je_file_tree/core/` | standard library only | `node.py` (the tree), `scanner.py` (parallel scan), `allocation.py` (size on disk), `protected.py` (system and program folders), `exclusions.py` (folders to skip), `analysis.py` (largest files, per-type and per-age totals), `search.py` (find by name), `duplicates.py` (same content), `cleanup.py` (clean-up suggestions), `compare.py` (against a saved scan), `pacing.py` (background work gives way to the window), `treemap.py` (layout), `sunburst.py` (rings), `tree_layout.py` (bounded hierarchy rows), `formatting.py`, `export.py` (CSV / JSON) |
| GUI | `je_file_tree/gui/` | PySide6, core | `app.py` (start-up), `main_window.py`, `welcome.py`, `scan_bar.py`, `results_view.py`, `charts.py` + `bar_chart.py` + `sunburst_widget.py` + `tree_diagram.py`, `search_panel.py`, `cleanup_panel.py`, `duplicates_panel.py`, `grouped_list.py`, `changes_panel.py`, `tree_model.py`, `tables.py`, `treemap_widget.py`, `delegates.py`, `scan_worker.py`, `file_actions.py`, `help_dialog.py`, `i18n.py` + `strings.py`, `qt_translation.py`, `elevation.py`, `icon.py` (drawn in code) |
| Entry script | `start_file_tree.py` | GUI | Starts the window from a source copy; the file Nuitka compiles |
| Tools | `tools/` | GUI | `make_screenshots.py` (README pictures), `build_nuitka.py` (stand-alone builds, see `nuitka.md`) |
| Tests | `test/` | both | one file per area; Qt tests on the offscreen platform |

The core never imports Qt or the GUI (`test/test_layers.py`).

`core/coverage.py` surveys folder coverage on the cleanup worker, marking incomplete branches and all
their ancestors unsafe to remove as a whole. Unseen bytes remain unknown.

`core/savings.py` (also exported from `allocation`) estimates reviewed selections without reading file
contents: outermost paths, logical bytes, unique hard-link allocation, conservative recoverable file-data
range after emptying Trash, and current free space. A hard-linked file whose other names remain offers
zero recoverable data. Unknown identities/coverage make recovery unknown; shared extents and directory
metadata remain outside the estimate. Windows cluster-rounded allocation is explicitly an estimate.

`duplicates.estimate_duplicate_savings` applies the same allocation/recovery rules to the extra copies
of every group, matching the current oldest-first list, with separate per-group estimates for the
listed groups. `DuplicateSavingsWorker` keeps this work off the UI thread and supports Stop; replaced
or pruned groups cancel and discard stale estimates. Every active search/estimate thread is joined on
close. The displayed extra-copy sum is explicitly logical size. Kept-copy choice and pre-move group
rehashing remain outstanding; the accounting assumption is visible and does not approve a move.

`core/capacity.py` builds a worker-computed estimated capacity ledger: OS total/used/available free,
unique allocation on the root device, hard-link overcount, included Trash allocation seen, foreign
allocation excluded and mount-boundary counts. Only complete whole-volume scans with known identities
can compute an unaccounted remainder; omitted bytes, filesystem metadata and other-volume totals remain
unknown. `gui/capacity_panel.py` shows the ledger and its limits. Tree edits invalidate it immediately;
whole-tree analysis after a branch rescan refreshes it. Replaced analysis signals are ignored and all
analysis threads are joined at close. CLI scan JSON includes the same ledger. Accuracy validation on
isolated NTFS/ext4/APFS volumes is outstanding. Different-device directory mounts are listed without
traversal; same-device POSIX bind mounts still need boundary detection.

## 3. Entry points and public interfaces

- `je-file-tree [folder]` (the `gui-scripts` entry `je_file_tree.gui.app:run`), `python start_file_tree.py [folder]`
  and `python -m je_file_tree [folder]`: all three call `app.run()`, which opens the window and scans `folder`
  right away if given (`test/test_start_script.py`).
- `je-file-tree-cli scan <root>` (`project.scripts`: `je_file_tree.cli:main`) and `python -m je_file_tree.cli`
  scan/export/compare without Qt imports or a display. Stdout/stderr use fixed newline-delimited JSON;
  exit codes are 0 complete, 1 partial, 2 arguments, 3 I/O/invalid saved scan, 130 interrupted. SIGINT
  cancellation returns and exports the partial snapshot; a second signal aborts. Each export is atomic
  independently. The console offers no filesystem removal.
- `python tools/build_nuitka.py [--onefile | --app] [Nuitka options]`: compiles `start_file_tree.py` into
  `build/<mode>/`, copying Qt's translation catalogues listed in `qt_translation.CATALOGUES`.
- `je_file_tree.core.scanner.scan(path, *, options, progress, cancel)` → `ScanResult(root, errors, elapsed)`.
- `je_file_tree.core.analysis.summarise(root, limit)` → largest files and per-extension totals in one pass.
- `je_file_tree.core.treemap.layout(root, rect, ...)` → `Tile`s; `export.export_*` write CSV / JSON.
- `python tools/measure_scale.py <root>` measures real scans with explicit memory/time budgets, optional
  Qt painting/live-model refresh and bounded duplicate hashing. Partial measurements are identified.

## 4. Main flows

**Scan.** `MainWindow.start_scan` opens the results page with its `ScanBar` and starts a `ScanWorker` (a
`QThread`) running `scan()`: worker threads (default 4, measured) share one stack of folders; each lists a
folder with `os.scandir`, turns entries into `Node`s without following links, and pushes subfolders back.
Folders matching `ScanOptions.exclude` (`exclusions.exclusion_test`: name patterns, or one folder by path;
the setting `exclusions`) are listed with `error == EXCLUDED`, size 0, and never read or counted as folders.
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

**Background work gives way.** In CPython one thread runs Python at a time, and every call Qt makes into
Python (each cell the folder tree paints, every event handler) needs that lock, so a worker walking the
tree used to make the window queue behind it. `core.pacing.WINDOW` is a gate: `scan_worker.pace_workers`
(called once by `app.main`) closes it when the GUI thread's event loop wakes (`awake`) and opens it when the
loop is about to wait (`aboutToBlock`). Every walk over the tree calls `pacing.give_way()` once per folder
(the scan's workers, `_add_up`, the analysis, clean-up, search, compare, export, each file hashed), which
waits while the gate is closed, at most `PAUSE_LIMIT` (50 ms) and never on the thread that closed it, so
nothing can hang on it. The window blocks on a worker only through `scan_worker.wait_for`, which opens the
gate first.

**Show.** `ResultsView.show_outcome` hands the tree to `FolderTreeModel` (which wraps the `Node`s, sorts
per folder lazily, and never copies), the tables to their models, and the root to `TreemapWidget` (layout
and drawing cached in a pixmap, recomputed on resize or zoom). Selecting anything selects it in the tree and
outlines it in the treemap.

**Free space.** Context menu or Delete → a first question when system or program folders are among the entries
(`protected.protection_of` against `protected_places()`, read once from the environment; the most specific
place decides, temporary folders are free) → one confirmation → background validation and
`QFile.moveToTrash` per entry → `ResultsView.forget` → affected-parent rescans. The tree and the largest-files
list allow several rows to be selected; the entries acted
on are `node.outermost` of the selection without the scanned folder (an entry inside a chosen folder goes with
it). `FolderTreeModel.remove` detaches each node and subtracts its totals from every folder above; the
largest files, per-type and per-age totals and treemap are updated once before the rescans. Entries the system
refuses stay and are named in a warning.

`Node.snapshot` holds compact packed device/file identity, kind, size, nanosecond timestamps, attributes
and link count (`core/snapshot.py`). Windows listings lack identity, so the scanner makes an additional
no-follow stat (10k calls measured at 0.67 s). After confirmation, `TrashWorker` runs `core.operations`:
ancestors must keep their identity and not become links; resolved protection must match the approval;
each selected entry and all folder descendants must retain metadata and child names. A changed/missing
or incomplete entry is skipped; successful, skipped and platform-failed entries are reported separately.
The GUI detaches only moved entries, keeps failed entries and queues rescans of affected parents. Scans
and model changes are blocked during the batch; Stop cancels remaining entries and close waits for it.
These are immediate no-follow checks; Qt's path-based Trash call is not an atomic transaction with the
identity check, so it does not provide an OS guarantee against concurrent malicious path substitution.

**Chart tab.** `ChartStack` holds the treemap, the bar chart (`BarChartWidget`: the `MAX_BARS` largest
entries of one folder, the rest on one line), the sunburst (`SunburstWidget`: `core.sunburst.layout`
gives arcs as fractions of the circle, at most `RINGS` rings, arcs thinner than `min_span` and past
`max_segments` left out, drawn into a cached pixmap), and the hierarchy tree (`TreeDiagramWidget`:
`core.tree_layout.layout` returns at most 240 folder cards, expands branches and pages wide sibling lists;
the GUI caches that layout and scrolls/zooms it). It shows one at a time, the treemap first
(`charts.DEFAULT_MODE`); the mode and tree direction are saved in `chart_mode` / `tree_orientation`.
All views offer the same interface (`set_view_root`, `zoom_out`, `set_selected`, `invalidate`,
`node_clicked`, `view_root_changed`, `context_menu_requested`); when one moves to another folder the stack
moves the others and signals the page once, so the results page drives the stack as a single chart.
The treemap draws `levels` levels (2 unless chosen, saved as `treemap_levels`); `treemap.layout(header=…)`
keeps a strip at the top of every opened folder that is at least three strips wide and tall, where the
widget prints the folder's name and size; colours come from the file type or, with `treemap_colours` =
`folder`, from a hue per top-level folder (the legend is hidden then). No tile is narrower than `min_side`
(the widget passes `MIN_SIDE`, 14 px): a folder's entries too small for that share one *group* tile
(`Tile.grouped` entries, `Tile.grouped_size` bytes, its node the folder), drawn grey and hatched, and a
folder opens only when at least one entry in it gets a tile of its own.

**Lists for one folder.** *Largest files*, *File types* and *Age* show the outcome's whole-scan lists, or,
with *Selected folder only* (the tab bar's corner), `analysis.summarise` of the folder selected in the tree,
run on an `AnalyseWorker` 250 ms after the selection settles. The outcome keeps the whole scan's totals up to
date after a move to the Recycle Bin, so switching back needs no recount.

**Rescan one folder.** The context menu's *Rescan this folder* runs a `ScanWorker` on that branch alone,
then `FolderTreeModel.replace` swaps it in (`Node.replace_with` corrects every total above it; persistent
indexes inside the old branch are dropped, the rest follow their nodes) and an `AnalyseWorker` recomputes
the largest files and per-type and per-age totals of the whole tree off the GUI thread.

**Search.** The Search tab (`SearchPanel`, Ctrl+F; conditions in `SearchFilters`, saved searches as JSON in the
`saved_searches` setting) waits for typing to pause, then runs `core.search.search` with a `Query`
on a `SearchWorker` thread: names are matched case-insensitively (plain text anywhere in the name, `*`/`?`
patterns against the whole name, several separated by `;`) and the 1,000 largest matches are shown with the
count and size of all. A new search stops the one before (it checks once per folder) and only the latest
result is shown. The box is disabled while a scan fills the tree; the search runs again after a scan, a
move to the Recycle Bin or a folder rescan.

**Clean up.** The Clean up tab has two pages. *Suggestions* (`CleanupPanel`): after every scan a
`CleanupWorker` runs `core.cleanup.find_cleanup`, one walk that tests each folder against the rules' path
endings (indexed by their last name) and each file against their name patterns, suggesting a matching
folder whole without looking inside it, then adds `empty_folders` (only folders known to be empty, the
outermost); it runs again after a move to the Recycle Bin or a folder rescan. The rules are data
(`cleanup.RULES`). *Duplicates* is the page below; both list their groups with `grouped_list`.

Before matching, `coverage_of` checks excluded, unread and inaccessible folders and propagates unknown
coverage to ancestors. Folder nodes start with `NOT_SCANNED`; successful reads clear it, hidden omissions
and failed entry stats leave the parent incomplete. A matching incomplete folder is never proposed whole;
empty-folder detection also requires successful reads. The worker returns coverage with its groups;
the panel displays a coverage banner and disables bulk selection on partial scans. Refresh discards old
rows immediately and ignores replaced workers; acting on incomplete branches requires their rescan.

Group selection emits `CleanupPanel.review_requested`; `MainWindow.move_to_trash` also intercepts manual
selections containing a current suggestion. `gui/cleanup_review.py` shows a lazy checkbox table of all
outermost proposed entries, their rules/reasons/consequences, metadata and protection. Unchecked entries
never reach the existing protection and Trash questions; rejection does nothing. A cancellable estimate
worker updates the count and logical/allocated/recovery/free-space fields; Continue waits for that result.
Full row explanations appear below the table and containing folders can be opened from the dialog.

**Duplicates.** The Duplicates page (`DuplicatesPanel`) runs `core.duplicates.find_duplicates` on a
`DuplicatesWorker` only when asked: files of the same size (1 MB and up unless another size is chosen) are
hashed on a thread pool, first their first 64 KB, then, for those still alike, the whole file; hard links
(same device and file number) count once. Progress reaches the window at most ten times a second; Stop is
checked before every file and every 1 MB. The groups are dropped on a new scan and pruned (`Node.is_in`)
after a move to the Recycle Bin or a folder rescan.

**Compare with a saved scan.** A saved scan is the Folder tree JSON export (`"format": "file-tree/1"`, with
`"saved"`, the time it was written). *Compare with a saved scan…* hands the file to a `CompareWorker`, which
reads it (`compare.load_saved` checks every field and raises `SavedScanError` with the reason) and
matches folders by their path below the scanned folder (`folder_key`, case-insensitive where the file
system is). The Changes tab, hidden until then, lists changed, new and gone folders; the comparison runs
again after each scan, move to the Recycle Bin and folder rescan until *Stop comparing*. Reading and
comparing took 0.68 s and 0.49 s on 86,000 folders, hence the worker.

**Export.** CSV rows and nested folder JSON stream into a temporary sibling. JSON uses an iterator stack
proportional to depth, never a second folder tree or a recursive JSON encoder. Only a successful close
replaces the destination; failure preserves its existing contents and removes the temporary file.

**Taskbar (Windows).** `app.main` first gives the process FileTree's own AppUserModelID (`icon.claim_taskbar_button`), so run from Python its windows get their own taskbar button with FileTree's
icon instead of being filed under `python.exe`.

**Administrator rights (Windows).** Before the window opens, `app.main` asks `elevation.relaunch_elevated`
to start a second copy through the "runas" verb (the UAC prompt) unless the `ask_admin_at_start` setting is
off or FileTree already is elevated; if that copy starts, this one exits, and a declined prompt just
continues. The File menu and the Problems tab (shown when folders were denied) offer the same restart, with
the scanned folder as its argument. A built program restarts itself; from Python it is `-m je_file_tree`.

**Language.** `i18n.set_language` + `qt_translation.apply_qt_translation` (Qt's own buttons and dialogs),
then every widget's `retranslate()`. The choice is stored in `QSettings` with the unit, window layout and
recent folders.

## 5. Extension points

- **A language**: a table in `je_file_tree/gui/strings.py`, an entry in `i18n.LANGUAGES`, a Qt catalogue in
  `qt_translation.CATALOGUES`, a README translation and a screenshot (`tools/make_screenshots.py`).
- **A file-type group**: `analysis.CATEGORY_EXTENSIONS`, a colour in `treemap_widget.CATEGORY_COLOURS`
  and a `category_<name>` text in every language (tests check all three).
- **An export format**: a function in `core/export.py` (atomic write) and an action in `main_window.py`.
- **A result tab**: a widget added in `ResultsView._assemble`, fed from `ScanOutcome`.
- **A chart view**: a widget with the treemap's interface, added to `charts.MODES` and `ChartStack`, with
  `chart_<mode>` and `chart_<mode>_tip` texts in every language (the mode button appears by itself).

## 6. Cross-project boundaries

None. FileTree is standalone: no other repository imports it or calls its command line, and it depends on
no other repository in the workspace — only on PySide6.

Outside the workspace it is published as `je_file_tree` on PyPI (command `je-file-tree`): the names
`file_tree` and `file-tree` belong to FSL's `file-tree`, which installs a module and a command of that
name, so they must not come back. `.github/workflows/release.yml` releases on every pull request merged
into `main`: `tools/bump_version.py` raises the version in `pyproject.toml` and
`je_file_tree/__init__.py` together, the sdist and wheel go to PyPI (secret `PYPI_API_TOKEN`; the job
stops before pushing anything when it is missing), and a Windows runner builds `FileTree-<version>.exe`
with `tools/build_nuitka.py --onefile` for the GitHub release. The job that holds the token installs
nothing but `.github/requirements/publish.txt` (`build`, `twine`, the build backend `setuptools` and
what they need): wheels only, at locked hashes, generated from `publish.in` beside it, before the
version is pushed. It builds with `python -m build --no-isolation`, so the backend is that locked
`setuptools` and nothing is downloaded during the build; the lock has to satisfy
`build-system.requires` in `pyproject.toml`. `test/test_workflow_actions.py` fails when that job runs
any other `pip install`, builds with isolation, or when the lock does not satisfy
`build-system.requires`. The source distribution carries no tests (`MANIFEST.in`,
`test/test_sdist_manifest.py`).

## 7. Design constraints

- Scanning speed, measured on an SSD with a warm cache: 62,000 files in 0.67 s with 4 threads (1.27 s with
  one); 740,000 entries in 6–8 s; analysis 0.65 s; treemap layout under 0.1 s (at most 20,000 tiles).
- The window during a scan (125,000 entries, the folder tree repainted every 50 ms): 37 ms per repaint as
  when idle, against 80 ms, and up to 2.1 s while the clean-up suggestions ran, before the workers gave way;
  the scan itself took as long either way with an idle window (2.6 s).
- Memory: about 250 bytes per entry (740,000 entries ≈ 185 MB); only the root stores a full path.
- System-drive check (U-20261007-01): 2.02 million entries / 57.95 s with two workers, 634 MB resident
  memory (about 301 incremental bytes/entry); 768 MiB diagnostic budget. Analysis/search about 2 s;
  compact streaming folder JSON 92.8 MB / 4.33 s. Unreadable branches remain unaccounted.
- With identity snapshots (U-20261007-03), the same system drive takes 207.60 s for 2.02 million entries
  with two workers, 872 MB resident memory (419 incremental bytes/entry). Snapshot storage is 76 packed
  bytes / 109-byte Python bytes object plus an 8-byte Node slot. Diagnostic budget: 1 GiB / 240 s.
- Links are never followed; unreadable folders are recorded, never fatal.
- Nothing is deleted permanently; every move to the trash is confirmed.

## 8. When to update this file

When a module is added, removed or changes layer; when a flow in §4 changes; when an extension point or a
constraint changes; when another repository starts depending on FileTree (§6).
