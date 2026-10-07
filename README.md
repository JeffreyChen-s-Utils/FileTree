# FileTree

**See where your disk space goes.** FileTree scans a folder or a whole drive, adds up every file inside
it, and shows you the biggest folders and files first — in a folder tree, a colourful treemap and a list
of the largest files. When you find something you no longer need, move it to the Recycle Bin right from
the window.

[English](README.md) | [繁體中文](README/README_zh-TW.md) | [简体中文](README/README_zh-CN.md)

![FileTree showing a home folder: the folder tree on the left, the treemap on the right](docs/images/main_window_en.png)

## Features

- **One click to start**: pick a folder, click a drive, drag a folder onto the window, or paste a path.
- **Parallel, and live**: several folders are read at once; a two-million-entry Windows system drive
  took about 208 seconds with file-identity snapshots and two workers. The tree fills in while the scan runs,
  biggest folders first, and Stop keeps
  what was read so far.
- **Folder tree** sorted largest first, with the space each entry takes on disk, a bar showing its share of
  its folder, file and folder counts, and the last change inside it.
- **Chart**, four ways to see a folder, switched in the corner of the tab (the treemap first): the **treemap** (every file
  a rectangle sized by the space it takes; a folder's files too small to see share one hatched tile), **bars** (one bar per entry of the folder, largest first, with
  its size and share: easiest to read exactly) and the **sunburst** (the folder in the centre, each deeper
  level a ring: the whole hierarchy at a glance), and the **tree diagram** (expandable folder branches,
  left-to-right or top-to-bottom, with size and parent share on each card). Click to find an entry in the
  folder tree, double-click to focus a folder; all four views follow.
- **Largest files**: the 1,000 biggest files anywhere in the scan, with a filter box.
- **Search** (Ctrl+F): find files and folders by name, or by a pattern such as `*.mp4`, anywhere in the scan.
- **Clean up**: suggestions of what can usually go — temporary files, browser caches, crash dumps, package
  caches, build output that can be rebuilt, old installers in Downloads and empty folders — grouped, with
  what deleting each kind does.
- **Duplicates** (in *Clean up*): files with the same content, grouped, with the space the extra copies take; select the
  extra copies with one click and move them to the Recycle Bin.
- **Compare with an earlier scan**: save a scan as JSON, and later see which folders grew, shrank,
  appeared or disappeared since.
- **File types** and **Age**: space used per extension and kind (pictures, videos, archives…) and by when
  files last changed; double-click a row to list its largest files.
- **Free space safely**: *Move to Recycle Bin* always asks first and never deletes permanently; entries
  are revalidated on a worker before moving and affected folders are rescanned.
- **Export** the folder list or the largest files to CSV (opens in Excel), or the folder tree to JSON.
- **English, 繁體中文 and 简体中文**, switchable at any time; a built-in *How to use* guide.
- Links and junctions are listed but never followed, so nothing is counted twice and a link loop cannot
  trap a scan. Folders that cannot be read are listed under *Problems* instead of stopping the scan.

## Install

FileTree runs on Windows, macOS and Linux.

**Windows, without Python**: download `FileTree-<version>.exe` from the [Releases](https://github.com/JeffreyChen-s-Utils/FileTree/releases) page and run it;
there is nothing to install.

**With Python 3.10 or newer**, from PyPI:

```bash
pip install je_file_tree
je-file-tree
```

Or run it from a copy of the source:

```bash
git clone https://github.com/JeffreyChen-s-Utils/FileTree.git
cd FileTree
pip install -r requirements.txt
python start_file_tree.py
```

`python -m je_file_tree` does the same.

### Build a stand-alone program

To give FileTree to someone without Python, compile it with Nuitka into a program folder or a single
`.exe`: see [nuitka.md](nuitka.md) for the commands and what each option does.

## How to use

1. **Choose what to scan**: click *Choose a folder…* or one of the drives on the start page, drag a
   folder onto the window, or type a path in the box at the top and press Enter. You can also start a
   scan from the command line: `je-file-tree D:\Projects` (or `python start_file_tree.py D:\Projects`).
2. **Watch it fill in**: the tree appears right away and the biggest folders move to the top while
   FileTree works; the largest files and file types follow when the scan ends. *Stop* (or Esc) ends the
   scan at any time and keeps what was read so far, marked as incomplete.
3. **Find what takes the space**: the biggest folders are at the top of the tree. Open a folder with the
   arrow next to it, or explore the chart on the right.

### Reading the results

| Where | What it tells you |
|---|---|
| Folder tree | Size, *On disk* (the space really taken: whole clusters, so usually a little more; less for compressed files, nothing for files kept only online), *% of parent* (the share of the folder above), number of files and folders inside, last change |
| Chart | *Treemap*: one rectangle per file, sized by space used; each folder has a strip with its name and size, and tiles show their size. The files of a folder too small to see or point at share one grey, hatched tile (*12 more*, with their size); double-click it to show that folder on its own. *Levels* sets how many levels are drawn (2 at first, up to all), *Colours* colours by file type (the legend is under it) or by top-level folder. *Bars*: one bar per entry of the folder shown, largest first, with its size and share of the folder. *Sunburst*: the folder in the centre and each deeper level as a ring, the angles by size, each top-level folder in its own colour; click the centre to go up. *Tree*: expandable folder cards with allocated size and parent share; click the plus sign to open a branch or an “other folders” card to reveal more, choose horizontal or vertical direction, Ctrl+wheel to zoom and use scroll bars to pan. Double-click a folder to focus it and *Up* to go back; all four views follow the same folder, and FileTree remembers the chosen view and tree direction |
| Largest files | The 1,000 biggest files; type in the filter box to narrow the list, double-click to find a file in the tree |
| Search | Files and folders whose name contains what you type; a pattern (`*.mp4`) must match the whole name, several are separated by `;` (`*.iso;*.zip`); conditions under the box narrow it down or search on their own: larger or smaller than a size, changed within a week / month / year or not for one, two or five years, a file type, files only or folders only; a search can be saved under a name and chosen again later; the 1,000 largest matches are listed with the count and total size of all |
| Clean up → Suggestions | Found after every scan: temporary files, browser caches, thumbnail caches, crash dumps, package caches (pip, npm, Gradle…), build output that can be rebuilt (`node_modules`, `__pycache__`, `target` beside `Cargo.toml`…), installers in Downloads untouched for 90 days, and empty folders; one group per kind, the largest first, with a tooltip on what deleting it does. *Select this group* or *Select all*, then Delete |
| Clean up → Duplicates | Press *Find duplicates*: files of the same size are compared, first by their first 64 KB, then by their whole content (hard links count once). Files under 1 MB are left out unless you choose a smaller size, because reading takes time. Each group lists its copies oldest first; *Select extra copies* selects all but the oldest, ready for Delete |
| File types | Space per extension; choose a kind above the table to see only that kind, double-click a row to list the largest files of that type |
| Age | Space by when files last changed (within a month … over two years ago); double-click a row to list its largest files |
| Problems | Folders FileTree was not allowed to read; their contents are not counted |

### Freeing space

Right-click any entry to open it, show it in your file manager, copy its path, show it in the chart,
rescan that folder after changes made outside FileTree (the rest of the results stay), scan that folder on
its own, or move it to the Recycle Bin (the Trash on macOS and Linux). To move several entries at once,
pick them with Ctrl+click or Shift+click in the folder tree, the Largest files list or the search results:
FileTree asks once, listing them with their total size. It always asks before moving anything and never
deletes permanently. System and program folders (the Windows folder, Program Files, programs' settings in
AppData, a user's profile folder, and their counterparts on macOS and Linux) are asked about twice, with the
reason; temporary folders and caches are not, since they are what a clean-up is for.

Before each move, FileTree checks the scan's file identity, kind, size and timestamps, current parents,
resolved protection and a folder's contents. Changed, missing or incomplete entries are skipped with
reasons; moved, skipped and failed counts are separate. *Stop* cancels remaining entries; affected
parents are rescanned. The status reports bytes moved: free space increases only after emptying the
Recycle Bin. Recording file identities costs additional scan time and memory, especially on Windows.

### Seeing what grew

Save a scan with **File → Export → Folder tree (JSON)**. Later, after a new scan, choose **File → Compare with a
saved scan…** and open that file: a **Changes** tab lists every folder that changed, with its size then and
now, the biggest growth first; new folders say *new* and removed ones *gone*. The comparison follows further
rescans until you press *Stop comparing*. Folders are matched by their path below the scanned folder, so a
scan can also be compared with a copy of the same tree elsewhere, such as a backup.

### Keyboard shortcuts

| Key | Action |
|---|---|
| Ctrl+O | Choose a folder |
| F5 | Rescan |
| Esc | Stop the scan |
| Ctrl+F | Search by name |
| Delete | Move the selected entries to the Recycle Bin |
| F1 | How to use |
| Ctrl+Q | Quit |

On macOS use ⌘ instead of Ctrl (⌘R rescans).

### Good to know

- Sizes are real file sizes in binary units (1 KB = 1,024 bytes), the same as Windows Explorer. Pick a
  fixed unit under *View → Size unit*.
- On Windows, FileTree asks for administrator rights when it starts, like TreeSize, so it can read protected
  folders too. Say no and it runs normally; folders it could not read are listed under *Problems*, with a
  *Restart as administrator* button (also in the *File* menu). Turn the question off under
  *View → Ask for administrator rights at start*.
- *Largest files*, *File types* and *Age* cover the whole scan; *Selected folder only*, at the top right of
  those tabs, makes them follow the folder selected in the tree.
- Hidden files are counted. Turn off *View → Include hidden files* to leave them out of the next scan.
- Clean-up shows known bytes and counts of skipped, inaccessible and unread folders; omitted bytes are
  unknown. An incomplete branch is never suggested as a whole or as empty. *Select all* is disabled for
  incomplete scans; rescan the relevant branch before cleaning it. Refreshing clears stale suggestions.
- To leave folders out of every scan, list them in *View → Skip while scanning*: a name such as
  `node_modules` or `*.cache` skips every folder of that name, a path skips one folder. Skipped folders are
  listed greyed out, with size 0.
- Your language, size unit, window layout and recently scanned folders are remembered (on Windows in the
  registry under `HKEY_CURRENT_USER\Software\JE-Chen\FileTree`).

## Development

```bash
pip install -r dev_requirements.txt
python -m pytest
python -m ruff check .
python tools/make_screenshots.py
```

`tools/make_screenshots.py` redraws the README pictures from a made-up folder, in every language. The
code layout, the main flows and the design rules are described in [architecture.md](architecture.md).

Measure a whole-drive scan with explicit resource budgets (two workers, 512 MB and 180 seconds by
default). The report marks a stopped scan as partial; duplicate hashing is limited separately. CSV and
JSON exports stream to a temporary sibling, keeping additional memory small even for large scans.

```bash
python tools/measure_scale.py C:\ --gui --memory-mb 768 --duplicates-seconds 10 --output scale.json
```

## License

MIT — see [LICENSE](LICENSE).
